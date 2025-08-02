"""
实验进程管理模块
处理实验的启动、监控、停止和日志收集
"""
import os
import subprocess
import threading
import time
import signal
import psutil
import re
import json
from pathlib import Path
from django.utils import timezone
from django.conf import settings
from .models import Experiment, ExperimentLog
import logging

logger = logging.getLogger(__name__)


class ExperimentProcessManager:
    """
    实验进程管理器
    """
    
    def __init__(self):
        self.running_processes = {}  # {experiment_id: process_info}
        self.log_threads = {}       # {experiment_id: log_thread}
        self.eolo_dir = settings.EOLO_DIR  # EOLO目录路径
        
        # 从配置获取参数
        self.monitor_config = getattr(settings, 'PROCESS_MONITOR_CONFIG', {})
        self.log_config = getattr(settings, 'EXPERIMENT_LOG_CONFIG', {})
        
        # 进程状态持久化文件路径
        self.pid_file_dir = Path(settings.BASE_DIR) / "tmp" / "experiment_pids"
        self.pid_file_dir.mkdir(parents=True, exist_ok=True)
        
        # 启动时恢复监控
        self._restore_process_monitoring()
    
    def start_experiment(self, experiment_id, force_start=False):
        """
        启动实验进程
        """
        try:
            experiment = Experiment.objects.get(id=experiment_id)
            
            # 检查实验状态
            if experiment.status not in ['pending', 'queued']:
                raise ValueError(f"实验状态不允许启动: {experiment.status}")
            
            # 检查GPU可用性（如果不是强制启动）
            if not force_start:
                from .gpu_utils import check_gpu_availability
                gpu_check = check_gpu_availability(experiment.device)
                if not gpu_check['available']:
                    experiment.queue_experiment()
                    self._log_to_experiment(experiment, 'WARNING', 
                        f"GPU繁忙，实验加入排队: {gpu_check['message']}")
                    return False, "GPU繁忙，实验已加入排队"
            
            # 更新实验状态为运行中
            experiment.start_experiment()
            
            # 构建完整的训练命令
            command = self._build_training_command(experiment)
            
            # 启动进程
            process_info = self._start_process(experiment, command)
            
            # 保存进程信息
            self.running_processes[experiment_id] = process_info
            
            # 启动日志监控线程（根据进程类型决定）
            if process_info.get('independent'):
                # 独立进程：通过日志文件监控
                self._start_file_log_monitoring(experiment, process_info)
            else:
                # 传统方式：通过stdout监控
                self._start_log_monitoring(experiment, process_info)
            
            # 启动进程监控线程
            self._start_process_monitoring(experiment, process_info)
            
            self._log_to_experiment(experiment, 'INFO', 
                f"实验进程已启动 (PID: {process_info['process'].pid})")
            
            return True, "实验启动成功"
            
        except Exception as e:
            logger.error(f"启动实验失败 (ID: {experiment_id}): {str(e)}")
            try:
                experiment = Experiment.objects.get(id=experiment_id)
                experiment.fail_experiment(f"启动失败: {str(e)}")
                self._log_to_experiment(experiment, 'ERROR', f"启动失败: {str(e)}")
            except:
                pass
            return False, f"启动失败: {str(e)}"
    
    def stop_experiment(self, experiment_id, user_initiated=True):
        """
        停止实验进程
        """
        try:
            experiment = Experiment.objects.get(id=experiment_id)
            
            # 如果是用户手动停止，立即更新状态，避免监控线程再次处理
            if user_initiated:
                experiment.interrupt_experiment("用户手动停止实验")
                self._log_to_experiment(experiment, 'INFO', "实验被用户手动停止")
            
            # 首先通过环境变量查找并杀死所有相关的训练进程
            killed_pids = self._kill_all_experiment_processes(experiment_id)
            
            if experiment_id in self.running_processes:
                process_info = self.running_processes[experiment_id]
                process = process_info['process']
                
                # 标记为手动停止，避免监控线程重复处理
                process_info['user_stopped'] = user_initiated
                
                # 终止进程树（包括启动进程和所有子进程）
                try:
                    # 先杀死进程树
                    self._kill_process_tree(process.pid)
                    
                    # 然后尝试温和地终止主进程
                    process.terminate()
                    
                    # 等待进程退出（从配置获取超时时间）
                    timeout = self.monitor_config.get('TERMINATION_TIMEOUT', 5)
                    try:
                        process.wait(timeout=timeout)
                    except (subprocess.TimeoutExpired, AttributeError):
                        # 如果进程不响应，强制杀死
                        try:
                            process.kill()
                            process.wait()
                        except AttributeError:
                            # mock process没有wait方法，跳过
                            pass
                    
                except (psutil.NoSuchProcess, AttributeError):
                    pass  # 进程已经不存在或mock process
                
                # 清理监控线程
                self._cleanup_threads(experiment_id)
                
                # 从运行列表中移除
                del self.running_processes[experiment_id]
                
                # 删除进程信息文件
                self._remove_process_info(experiment_id)
            
            return True, "实验已停止"
            
        except Exception as e:
            logger.error(f"停止实验失败 (ID: {experiment_id}): {str(e)}")
            return False, f"停止失败: {str(e)}"
    
    def get_experiment_status(self, experiment_id):
        """
        获取实验运行状态
        """
        try:
            experiment = Experiment.objects.get(id=experiment_id)
            
            if experiment_id in self.running_processes:
                process_info = self.running_processes[experiment_id]
                process = process_info['process']
                
                # 首先检查进程是否还在运行
                exit_code = process.poll()
                if exit_code is None:
                    # subprocess认为进程还在运行，用psutil双重验证
                    try:
                        psutil_process = psutil.Process(process.pid)
                        if psutil_process.is_running():
                            return {
                                'status': 'running',
                                'pid': process.pid,
                                'start_time': process_info['start_time'],
                                'running_time': time.time() - process_info['start_time']
                            }
                        else:
                            # psutil说进程不在运行，但subprocess还没检测到
                            logger.warning(f"进程状态不一致 (实验 {experiment_id}): subprocess={exit_code}, psutil=not_running")
                            # 清理状态
                            self._cleanup_experiment_process(experiment_id, "进程状态不一致")
                            return {
                                'status': 'finished',
                                'exit_code': -1,
                                'start_time': process_info['start_time'],
                                'end_time': time.time(),
                                'message': '进程意外终止'
                            }
                    except psutil.NoSuchProcess:
                        # 进程确实不存在
                        logger.warning(f"进程不存在 (实验 {experiment_id}, PID: {process.pid})")
                        self._cleanup_experiment_process(experiment_id, "进程不存在")
                        return {
                            'status': 'finished',
                            'exit_code': -1,
                            'start_time': process_info['start_time'],
                            'end_time': time.time(),
                            'message': '进程意外消失'
                        }
                    except Exception as e:
                        logger.error(f"检查进程状态时出错 (实验 {experiment_id}): {str(e)}")
                        return {
                            'status': 'running',
                            'pid': process.pid,
                            'start_time': process_info['start_time'],
                            'running_time': time.time() - process_info['start_time'],
                            'warning': f'状态检查异常: {str(e)}'
                        }
                else:
                    # 进程已经结束，检查是否有实际退出码
                    actual_exit_code = process_info.get('actual_exit_code')
                    if actual_exit_code is not None:
                        final_exit_code = actual_exit_code
                        logger.debug(f"状态查询：使用实际退出码 {actual_exit_code} (实验 {experiment_id})")
                    else:
                        final_exit_code = exit_code
                        logger.debug(f"状态查询：使用shell退出码 {exit_code} (实验 {experiment_id})")
                    
                    return {
                        'status': 'finished',
                        'exit_code': final_exit_code,
                        'actual_exit_code': actual_exit_code,  # 额外返回实际退出码信息
                        'shell_exit_code': exit_code,  # 额外返回shell退出码信息
                        'start_time': process_info['start_time'],
                        'end_time': time.time()
                    }
            else:
                return {
                    'status': experiment.status,
                    'message': '进程未在监控中'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _cleanup_experiment_process(self, experiment_id, reason):
        """
        清理实验进程状态（当检测到进程意外终止时使用）
        """
        try:
            # 更新数据库状态
            experiment = Experiment.objects.get(id=experiment_id)
            experiment.fail_experiment(f"进程监控检测到异常: {reason}")
            self._log_to_experiment(experiment, 'ERROR', f"进程异常: {reason}")
            
            # 清理内存中的进程信息
            self._cleanup_threads(experiment_id)
            if experiment_id in self.running_processes:
                del self.running_processes[experiment_id]
                
        except Exception as e:
            logger.error(f"清理实验进程状态失败 (实验 {experiment_id}): {str(e)}")
    
    def _build_training_command(self, experiment):
        """
        构建训练命令（使用uv run）
        """
        # 将python命令替换为uv run
        command = experiment.command
        if command.startswith('python '):
            command = command.replace('python ', 'uv run ', 1)
        elif command.startswith('python3 '):
            command = command.replace('python3 ', 'uv run ', 1)
        
        # 基础命令：切换到EOLO目录并运行训练
        base_cmd = f"cd {self.eolo_dir} && {command}"
        
        return base_cmd
    
    def _start_process(self, experiment, command):
        """
        启动训练进程（使用nohup确保进程独立运行）
        """
        # 设置环境变量
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'  # 确保输出不被缓冲
        env['EOLO_EXPERIMENT_ID'] = str(experiment.id)  # 添加实验ID环境变量用于识别
        
        # 创建日志文件路径
        log_dir = Path(settings.BASE_DIR) / "tmp" / "experiment_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"exp_{experiment.id}_{int(time.time())}.log"
        
        # 使用nohup启动进程，确保进程独立于Django服务器
        # 修改nohup命令，让它能正确传递退出码
        nohup_command = f"nohup bash -c '({command}); echo \"EOLO_EXIT_CODE:$?\" >> {log_file}' > {log_file} 2>&1 &"
        
        logger.info(f"启动训练进程: {nohup_command}")
        logger.info(f"工作目录: {self.eolo_dir}")
        logger.info(f"日志文件: {log_file}")
        
        # 启动进程
        process = subprocess.Popen(
            nohup_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=self.eolo_dir,
            start_new_session=True  # 创建新的会话，确保进程独立
        )
        
        # 等待nohup命令完成（实际的训练进程会在后台继续运行）
        stdout, stderr = process.communicate()
        
        if stderr:
            logger.warning(f"nohup命令有错误输出: {stderr}")
        
        # 获取实际训练进程的PID（从ps命令中查找）
        logger.info("等待训练进程启动...")
        time.sleep(3)  # 增加等待时间，确保进程完全启动
        actual_pid = self._find_training_process_pid(experiment.id, command)
        
        if actual_pid is None:
            # 检查日志文件是否有错误信息
            error_msg = "无法找到启动的训练进程"
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        log_content = f.read()
                        if log_content:
                            error_msg += f"\n日志内容: {log_content[:500]}"
                            logger.error(f"训练进程启动失败，日志内容: {log_content}")
                except Exception as read_e:
                    logger.error(f"读取日志文件失败: {str(read_e)}")
            
            # 列出所有python和uv进程用于调试
            logger.info("当前所有Python和UV进程:")
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and ('python' in proc.info['name'].lower() or 'uv' in proc.info['name'].lower()):
                        cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                        logger.info(f"  PID {proc.info['pid']}: {cmdline}")
                except:
                    pass
                    
            raise RuntimeError(error_msg)
        
        logger.info(f"成功找到训练进程 PID: {actual_pid}")
        
        # 创建mock process对象来兼容现有代码
        class TrainingProcess:
            def __init__(self, pid, manager, experiment_id):
                self.pid = pid
                self._manager = manager
                self._experiment_id = experiment_id
                self.stdout = None  # 日志通过文件读取
                self._exit_code = None  # 缓存退出码
                self._process_ended = False  # 标记进程是否已结束
            
            def poll(self):
                """
                检查训练进程的状态并返回退出码
                返回None表示进程仍在运行，返回数字表示退出码
                优先使用从日志中提取的实际退出码
                """
                if self._process_ended and self._exit_code is not None:
                    return self._exit_code
                
                try:
                    psutil_process = psutil.Process(self.pid)
                    if psutil_process.is_running():
                        return None  # 进程仍在运行
                    else:
                        # 进程已结束，首先尝试从process_info中获取实际退出码
                        if not self._process_ended:
                            process_info = self._manager.running_processes.get(self._experiment_id)
                            if process_info and 'actual_exit_code' in process_info:
                                # 使用从日志中提取的实际训练进程退出码
                                self._exit_code = process_info['actual_exit_code']
                                logger.info(f"使用从日志提取的实际退出码: {self._exit_code} (PID: {self.pid})")
                            else:
                                # 如果没有实际退出码，回退到系统方法（但可能不准确）
                                try:
                                    # 尝试获取进程状态
                                    status = psutil_process.status()
                                    if status == psutil.STATUS_ZOMBIE:
                                        # 僵尸进程，等待父进程回收并获取退出码
                                        try:
                                            self._exit_code = psutil_process.wait(timeout=2)
                                            logger.warning(f"使用系统退出码（可能不准确）: {self._exit_code} (PID: {self.pid})")
                                        except psutil.TimeoutExpired:
                                            logger.warning(f"无法在超时内获取进程退出码 (PID: {self.pid})")
                                            self._exit_code = -1  # 超时，无法获取退出码
                                    else:
                                        # 进程已完全结束，尝试获取退出码
                                        try:
                                            self._exit_code = psutil_process.returncode
                                            if self._exit_code is None:
                                                # 如果仍无法获取，检查进程是否正常结束
                                                self._exit_code = 0
                                            logger.warning(f"使用系统退出码（可能不准确）: {self._exit_code} (PID: {self.pid})")
                                        except AttributeError:
                                            # psutil版本可能不支持returncode
                                            self._exit_code = 0
                                            logger.warning(f"无法获取退出码，默认为0 (PID: {self.pid})")
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    # 进程已不存在或无法访问
                                    logger.warning(f"训练进程已不存在，默认退出码为0 (PID: {self.pid})")
                                    self._exit_code = 0
                            
                            self._process_ended = True
                        
                        return self._exit_code
                        
                except psutil.NoSuchProcess:
                    # 进程不存在，标记为已结束
                    if not self._process_ended:
                        # 尝试从process_info获取实际退出码
                        process_info = self._manager.running_processes.get(self._experiment_id)
                        if process_info and 'actual_exit_code' in process_info:
                            self._exit_code = process_info['actual_exit_code']
                            logger.info(f"进程不存在，使用从日志提取的退出码: {self._exit_code} (PID: {self.pid})")
                        else:
                            logger.warning(f"训练进程不存在，未找到实际退出码，默认为0 (PID: {self.pid})")
                            self._exit_code = 0  # 默认正常退出
                        self._process_ended = True
                    return self._exit_code
                except Exception as e:
                    logger.debug(f"检查训练进程状态时出错 (PID: {self.pid}): {str(e)}")
                    return None  # 出错时假设进程仍在运行
            
            def terminate(self):
                # 首先尝试通过环境变量杀死所有相关进程
                self._manager._kill_all_experiment_processes(self._experiment_id)
                # 然后终止主进程
                return self._manager._terminate_process_by_pid(self.pid)
            
            def kill(self):
                # 首先尝试通过环境变量杀死所有相关进程
                self._manager._kill_all_experiment_processes(self._experiment_id)
                # 然后强制杀死主进程
                return self._manager._kill_process_by_pid(self.pid)
            
            def wait(self, timeout=None):
                return self._manager._wait_process_by_pid(self.pid, timeout)
        
        mock_process = TrainingProcess(actual_pid, self, experiment.id)
        
        process_info = {
            'process': mock_process,
            'command': command,
            'start_time': time.time(),
            'experiment_id': experiment.id,
            'log_file': str(log_file),
            'independent': True  # 标记为独立进程
        }
        
        # 保存进程信息到文件
        self._save_process_info(experiment.id, process_info)
        
        return process_info
    
    def _find_training_process_pid(self, experiment_id, command):
        """
        查找训练进程的实际PID
        """
        try:
            import re
            # 从命令中提取关键信息用于匹配（支持uv run和python）
            if "src/train.py" in command:
                pattern = r"(uv run|python).*src/train\.py"
            else:
                pattern = r"(uv run|python).*train\.py"
            
            # 多次尝试查找进程（因为进程启动可能需要时间）
            for attempt in range(10):  # 增加尝试次数
                logger.debug(f"第 {attempt + 1} 次查找训练进程...")
                
                # 搜索匹配的进程
                for proc in psutil.process_iter(['pid', 'cmdline', 'create_time', 'environ']):
                    try:
                        cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                        
                        # 首先检查环境变量（最可靠的方法）
                        try:
                            environ = proc.info.get('environ', {})
                            if environ and environ.get('EOLO_EXPERIMENT_ID') == str(experiment_id):
                                logger.info(f"通过环境变量找到匹配的训练进程 (PID: {proc.info['pid']}, 命令: {cmdline})")
                                return proc.info['pid']
                        except (psutil.AccessDenied, psutil.ZombieProcess):
                            # 无法访问环境变量，继续使用其他方法
                            pass
                        
                        # 检查是否匹配训练脚本
                        if re.search(pattern, cmdline):
                            # 如果是最近启动的进程（10秒内），可能是我们的进程
                            current_time = time.time()
                            if current_time - proc.info['create_time'] < 10:
                                # 进一步检查命令行参数
                                if any(keyword in cmdline for keyword in ['train', 'experiment', 'src/train.py']):
                                    logger.info(f"通过命令行找到可能的训练进程 (PID: {proc.info['pid']}, 命令: {cmdline})")
                                    return proc.info['pid']
                                    
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
                
                # 如果没找到，等待一下再试
                if attempt < 9:
                    logger.debug(f"第 {attempt + 1} 次查找失败，等待重试...")
                    time.sleep(0.5)  # 减少等待时间，但增加尝试次数
            
            logger.warning(f"经过10次尝试仍未找到训练进程 (实验 {experiment_id})")
            return None
        except Exception as e:
            logger.error(f"查找训练进程PID失败: {str(e)}")
            return None
    
    def _terminate_process_by_pid(self, pid):
        """
        通过PID终止进程
        """
        try:
            process = psutil.Process(pid)
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    
    def _kill_process_by_pid(self, pid):
        """
        通过PID强制杀死进程
        """
        try:
            process = psutil.Process(pid)
            process.kill()
        except psutil.NoSuchProcess:
            pass
    
    def _wait_process_by_pid(self, pid, timeout=None):
        """
        等待进程结束
        """
        try:
            process = psutil.Process(pid)
            return process.wait(timeout)
        except psutil.NoSuchProcess:
            return 0
    
    def _start_log_monitoring(self, experiment, process_info):
        """
        启动日志监控线程
        """
        def log_reader():
            process = process_info['process']
            experiment_id = experiment.id
            last_progress_line_id = None  # 用于跟踪进度条日志ID
            
            try:
                # 使用简单的逐行读取，但加上超时检查
                buffer = ""
                
                while True:
                    try:
                        # 设置较短的超时来读取一行
                        import select
                        import sys
                        
                        # 检查是否有数据可读
                        ready, _, _ = select.select([process.stdout], [], [], 0.1)
                        
                        if ready:
                            # 逐字符读取，直到遇到换行符或回车符
                            while True:
                                char = process.stdout.read(1)
                                if not char:
                                    break
                                
                                if char in ['\n', '\r']:
                                    # 遇到行结束符，处理当前行
                                    if buffer.strip():
                                        result = self._process_log_line(
                                            buffer, 
                                            experiment_id, 
                                            last_progress_line_id, 
                                            char == '\r'
                                        )
                                        if result is not None:
                                            last_progress_line_id = result
                                    buffer = ""
                                    
                                    # 如果是回车符后面紧跟换行符，跳过换行符
                                    if char == '\r':
                                        next_char = process.stdout.read(1)
                                        if next_char and next_char != '\n':
                                            buffer = next_char  # 不是换行符，保存到缓冲区
                                    break
                                else:
                                    buffer += char
                        
                        # 检查进程是否结束
                        if process.poll() is not None:
                            # 处理最后的缓冲区内容
                            if buffer.strip():
                                self._process_log_line(buffer, experiment_id, last_progress_line_id, False)
                            break
                            
                        # 短暂休眠
                        time.sleep(0.01)
                        
                    except (OSError, IOError, ValueError) as e:
                        # 处理读取错误
                        if process.poll() is not None:
                            break
                        time.sleep(0.1)
                        
            except Exception as e:
                logger.error(f"日志监控线程错误 (实验 {experiment_id}): {str(e)}")
                # 记录监控线程异常
                try:
                    exp = Experiment.objects.get(id=experiment_id)
                    self._create_log_entry(exp, 'ERROR', f"日志监控异常: {str(e)}")
                except:
                    pass
            finally:
                if process.stdout:
                    process.stdout.close()
        
        # 启动日志监控线程
        log_thread = threading.Thread(target=log_reader, daemon=True)
        log_thread.start()
        self.log_threads[experiment.id] = log_thread
    
    def _start_file_log_monitoring(self, experiment, process_info):
        """
        启动基于文件的日志监控（用于独立进程）
        """
        def file_log_reader():
            experiment_id = experiment.id
            log_file = Path(process_info['log_file'])
            last_position = 0
            last_progress_line_id = None
            
            try:
                while True:
                    try:
                        if log_file.exists():
                            with open(log_file, 'r', encoding='utf-8') as f:
                                f.seek(last_position)
                                new_content = f.read()
                                
                                if new_content:
                                    lines = new_content.split('\n')
                                    for line in lines[:-1]:  # 排除最后的空行
                                        if line.strip():
                                            last_progress_line_id = self._process_log_line(
                                                line, experiment_id, last_progress_line_id, True
                                            )
                                    
                                    last_position = f.tell()
                        
                        # 检查进程是否还在运行
                        if experiment_id not in self.running_processes:
                            break
                            
                        process = self.running_processes[experiment_id]['process']
                        if process.poll() is not None:
                            # 进程结束，读取剩余日志
                            if log_file.exists():
                                with open(log_file, 'r', encoding='utf-8') as f:
                                    f.seek(last_position)
                                    remaining_content = f.read()
                                    if remaining_content:
                                        lines = remaining_content.split('\n')
                                        for line in lines:
                                            if line.strip():
                                                self._process_log_line(
                                                    line, experiment_id, last_progress_line_id, False
                                                )
                            break
                        
                        time.sleep(1)  # 文件监控间隔更长一些
                        
                    except Exception as e:
                        logger.error(f"文件日志监控错误 (实验 {experiment_id}): {str(e)}")
                        time.sleep(5)  # 出错时等待更长时间
                        
            except Exception as e:
                logger.error(f"文件日志监控线程错误 (实验 {experiment_id}): {str(e)}")
        
        # 启动监控线程
        thread = threading.Thread(target=file_log_reader, daemon=True)
        thread.start()
        self.log_threads[experiment.id] = thread
    
    def _process_log_line(self, line_content, experiment_id, last_progress_line_id, is_carriage_return=False):
        """
        处理单行日志内容
        返回进度条日志的ID（如果是进度条）
        """
        # 去除ANSI转义序列（彩色字符）
        ansi_pattern = self.log_config.get('ANSI_ESCAPE_PATTERN', 
            r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        ansi_escape = re.compile(ansi_pattern)
        clean_line = ansi_escape.sub('', line_content).strip()
        
        if not clean_line:  # 跳过空行
            return last_progress_line_id
        
        # 检查是否是我们添加的退出码行
        if clean_line.startswith('EOLO_EXIT_CODE:'):
            try:
                exit_code = int(clean_line.split(':')[1])
                logger.info(f"从日志中提取到训练进程退出码: {exit_code} (实验 {experiment_id})")
                
                # 将退出码保存到进程信息中
                if experiment_id in self.running_processes:
                    process_info = self.running_processes[experiment_id]
                    process_info['actual_exit_code'] = exit_code
                    
                    # 如果退出码非零，说明训练失败
                    if exit_code != 0:
                        try:
                            exp = Experiment.objects.get(id=experiment_id)
                            if exp.status == 'running':
                                exp.fail_experiment(f"训练进程异常退出，退出码: {exit_code}")
                                self._log_to_experiment(exp, 'ERROR', 
                                    f"训练进程退出码: {exit_code}，标记为失败")
                        except Exception as e:
                            logger.error(f"处理退出码时更新实验状态失败: {str(e)}")
                
                return last_progress_line_id  # 不显示这行日志给用户
            except (ValueError, IndexError):
                logger.warning(f"无法解析退出码行: {clean_line}")
        
        # 简单的日志级别判断和严重错误检测
        level = 'INFO'
        line_lower = clean_line.lower()
        critical_error = False
        
        if any(keyword in line_lower for keyword in ['error', 'exception', 'failed', 'fatal']):
            level = 'ERROR'
            # 检查是否是严重错误，需要立即停止实验
            if any(keyword in line_lower for keyword in [
                'out of memory', 'oom', 'cuda out of memory',
                'cuda error', 'gpu error', 'runtimeerror',
                'traceback', 'fatal', 'abort'
            ]):
                critical_error = True
        elif any(keyword in line_lower for keyword in ['warning', 'warn', 'deprecated']):
            level = 'WARNING'
        elif any(keyword in line_lower for keyword in ['debug', 'verbose']):
            level = 'DEBUG'
        
        # 检查是否是进度条更新（tqdm特征）
        is_progress_line = any(pattern in clean_line for pattern in [
            '%|', '█', '▏', '▎', '▍', '▌', '▋', '▊', '▉',  # 进度条字符
            'it/s', 's/it', '/s',  # tqdm速度指示
            ' ETA ', ' eta ',  # 预计完成时间
        ]) or (clean_line.count('%') >= 1 and any(char.isdigit() for char in clean_line))
        
        try:
            exp = Experiment.objects.get(id=experiment_id)
            
            if is_progress_line and (is_carriage_return or last_progress_line_id):
                # 进度条更新：更新现有条目或创建新的
                if last_progress_line_id:
                    try:
                        last_log = ExperimentLog.objects.get(id=last_progress_line_id)
                        last_log.message = clean_line
                        last_log.timestamp = timezone.now()
                        last_log.save()
                        return last_progress_line_id
                    except ExperimentLog.DoesNotExist:
                        pass
                
                # 创建新的进度条日志
                log_entry = self._create_log_entry(exp, level, clean_line)
                return log_entry.id if log_entry else None
            else:
                # 普通日志：总是创建新条目
                log_entry = self._create_log_entry(exp, level, clean_line)
                # 如果不是进度条，重置进度条跟踪
                result = None if not is_progress_line else (log_entry.id if log_entry else None)
                
                # 检查是否是严重错误，需要立即标记实验失败
                if critical_error:
                    logger.warning(f"检测到严重错误，标记实验 {experiment_id} 为失败: {clean_line}")
                    try:
                        if exp.status == 'running':  # 只有运行中的实验才改为失败
                            exp.fail_experiment(f"训练过程中出现严重错误: {clean_line}")
                            self._log_to_experiment(exp, 'ERROR', "由于严重错误，实验已自动停止")
                            
                            # 尝试停止相关进程
                            try:
                                self._kill_all_experiment_processes(experiment_id)
                            except Exception as kill_e:
                                logger.error(f"停止错误实验进程失败 (实验 {experiment_id}): {str(kill_e)}")
                    except Exception as fail_e:
                        logger.error(f"标记实验失败时出错 (实验 {experiment_id}): {str(fail_e)}")
                
                return result
                
        except Exception as e:
            logger.error(f"处理日志行失败 (实验 {experiment_id}): {str(e)}")
            return last_progress_line_id
    
    def _start_process_monitoring(self, experiment, process_info, skip_log=False):
        """
        启动进程监控线程
        """
        def process_monitor():
            process = process_info['process']
            experiment_id = experiment.id
            
            try:
                # 使用轮询方式检查进程状态，避免阻塞
                while True:
                    # 检查进程是否还在运行
                    exit_code = process.poll()
                    
                    if exit_code is not None:
                        # 进程已经结束
                        logger.info(f"检测到进程结束 (实验 {experiment_id}, shell退出码: {exit_code})")
                        
                        # 检查是否是用户手动停止的实验
                        if process_info.get('user_stopped'):
                            logger.info(f"检测到用户手动停止的实验 {experiment_id}，跳过退出码判断")
                            # 清理资源即可，不更新实验状态（已在stop_experiment中更新）
                            self._cleanup_threads(experiment_id)
                            if experiment_id in self.running_processes:
                                del self.running_processes[experiment_id]
                            self._remove_process_info(experiment_id)
                            break
                        
                        # 检查是否有从日志中提取的实际退出码
                        actual_exit_code = process_info.get('actual_exit_code')
                        if actual_exit_code is not None:
                            # 使用从日志中提取的实际训练进程退出码
                            final_exit_code = actual_exit_code
                            logger.info(f"使用实际训练进程退出码: {actual_exit_code}")
                        else:
                            # 如果没有找到实际退出码，使用shell退出码（但这可能不准确）
                            final_exit_code = exit_code
                            logger.warning(f"未找到实际退出码，使用shell退出码: {exit_code}")
                        
                        # 检查日志文件中是否有错误信息
                        has_errors = False
                        error_message = ""
                        
                        try:
                            # 如果是独立进程，检查日志文件
                            if process_info.get('independent') and process_info.get('log_file'):
                                log_file = Path(process_info['log_file'])
                                if log_file.exists():
                                    has_errors, error_message = self._check_log_for_errors(log_file)
                        except Exception as log_check_e:
                            logger.error(f"检查日志文件错误 (实验 {experiment_id}): {str(log_check_e)}")
                        
                        # 更新实验状态（优先使用退出码判断）
                        try:
                            exp = Experiment.objects.get(id=experiment_id)
                            
                            # 再次检查实验状态，如果已经是终止状态，跳过更新
                            if exp.status in ['interrupted', 'failed', 'completed']:
                                logger.info(f"实验 {experiment_id} 已经是终止状态 ({exp.status})，跳过状态更新")
                                # 只清理资源
                                self._cleanup_threads(experiment_id)
                                if experiment_id in self.running_processes:
                                    del self.running_processes[experiment_id]
                                self._remove_process_info(experiment_id)
                                break
                            
                            # 优先根据退出码判断，只有在退出码为0但日志有明确错误时才标记为失败
                            if final_exit_code == 0:
                                # 退出码为0，检查日志是否有严重错误
                                if has_errors:
                                    # 日志中有错误但退出码为0，需要仔细判断
                                    logger.warning(f"退出码为0但日志中检测到错误 (实验 {experiment_id}): {error_message}")
                                    # 只有严重错误才覆盖退出码判断
                                    if any(keyword in error_message.lower() for keyword in ['out of memory', 'cuda error', 'traceback', 'exception']):
                                        exp.fail_experiment(f"训练过程中出现严重错误: {error_message}")
                                        self._log_to_experiment(exp, 'ERROR', 
                                            f"训练失败: {error_message} (退出码为0但检测到严重错误)")
                                    else:
                                        # 非严重错误，以退出码为准
                                        exp.complete_experiment()
                                        self._log_to_experiment(exp, 'INFO', 
                                            f"实验正常完成 (退出码: {final_exit_code}，忽略非严重日志警告)")
                                else:
                                    # 退出码为0且无错误：正常完成
                                    exp.complete_experiment()
                                    self._log_to_experiment(exp, 'INFO', 
                                        f"实验正常完成 (实际退出码: {final_exit_code})")
                            else:
                                # 退出码非0：直接标记为失败
                                exp.fail_experiment(f"训练进程异常退出，退出码: {final_exit_code}")
                                self._log_to_experiment(exp, 'ERROR', 
                                    f"实验异常退出 (实际退出码: {final_exit_code})")
                        except Exception as db_e:
                            logger.error(f"更新实验状态失败 (实验 {experiment_id}): {str(db_e)}")
                        
                        # 清理资源
                        self._cleanup_threads(experiment_id)
                        if experiment_id in self.running_processes:
                            del self.running_processes[experiment_id]
                        
                        # 删除进程信息文件
                        self._remove_process_info(experiment_id)
                        
                        break
                    
                    # 额外检查：使用psutil验证进程是否真的还存在
                    try:
                        psutil_process = psutil.Process(process.pid)
                        if not psutil_process.is_running():
                            logger.warning(f"psutil检测到进程不再运行 (实验 {experiment_id}, PID: {process.pid})")
                            
                            # 检查是否是用户手动停止的实验
                            if process_info.get('user_stopped'):
                                logger.info(f"用户手动停止的实验 {experiment_id}，进程已终止")
                            else:
                                # 进程意外终止，标记为失败
                                try:
                                    exp = Experiment.objects.get(id=experiment_id)
                                    if exp.status == 'running':  # 只有运行中的实验才标记为失败
                                        exp.fail_experiment("进程意外终止（通过psutil检测）")
                                        self._log_to_experiment(exp, 'ERROR', "进程意外终止")
                                except:
                                    pass
                            
                            # 清理资源
                            self._cleanup_threads(experiment_id)
                            if experiment_id in self.running_processes:
                                del self.running_processes[experiment_id]
                            break
                            
                    except psutil.NoSuchProcess:
                        logger.warning(f"进程不存在 (实验 {experiment_id}, PID: {process.pid})")
                        
                        # 检查是否是用户手动停止的实验
                        if process_info.get('user_stopped'):
                            logger.info(f"用户手动停止的实验 {experiment_id}，进程已不存在")
                        else:
                            # 进程确实不存在了，标记为失败
                            try:
                                exp = Experiment.objects.get(id=experiment_id)
                                if exp.status == 'running':  # 只有运行中的实验才标记为失败
                                    exp.fail_experiment("进程意外消失")
                                    self._log_to_experiment(exp, 'ERROR', "进程意外消失")
                            except:
                                pass
                        
                        # 清理资源
                        self._cleanup_threads(experiment_id)
                        if experiment_id in self.running_processes:
                            del self.running_processes[experiment_id]
                        break
                    except Exception as psutil_e:
                        # psutil检查失败，继续使用标准方法
                        logger.debug(f"psutil检查失败 (实验 {experiment_id}): {str(psutil_e)}")
                    
                    # 使用配置的检查间隔
                    check_interval = self.monitor_config.get('STATUS_CHECK_INTERVAL', 1.0)
                    time.sleep(check_interval)
                    
            except Exception as e:
                logger.error(f"进程监控线程错误 (实验 {experiment_id}): {str(e)}")
                # 出现异常时也要确保清理资源
                try:
                    exp = Experiment.objects.get(id=experiment_id)
                    exp.fail_experiment(f"进程监控异常: {str(e)}")
                    self._log_to_experiment(exp, 'ERROR', f"进程监控异常: {str(e)}")
                except:
                    pass
                
                self._cleanup_threads(experiment_id)
                if experiment_id in self.running_processes:
                    del self.running_processes[experiment_id]
        
        # 启动进程监控线程
        monitor_thread = threading.Thread(target=process_monitor, daemon=True)
        monitor_thread.start()
    
    def _cleanup_threads(self, experiment_id):
        """
        清理监控线程
        """
        if experiment_id in self.log_threads:
            # 日志线程会自动结束，这里只是清理引用
            del self.log_threads[experiment_id]
    
    def _kill_process_tree(self, pid):
        """
        杀死进程树（包括所有子进程）
        """
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            
            # 先终止子进程
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            
            # 等待子进程退出
            cleanup_timeout = self.monitor_config.get('CLEANUP_TIMEOUT', 5)
            gone, alive = psutil.wait_procs(children, timeout=cleanup_timeout)
            
            # 强制杀死仍然存活的进程
            for proc in alive:
                try:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
            
            # 最后处理父进程
            timeout = self.monitor_config.get('TERMINATION_TIMEOUT', 10) 
            try:
                parent.terminate()
                parent.wait(timeout=timeout)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                try:
                    parent.kill()
                except psutil.NoSuchProcess:
                    pass
                    
        except psutil.NoSuchProcess:
            pass  # 进程已经不存在
        except Exception as e:
            logger.error(f"终止进程树失败 (PID: {pid}): {str(e)}")
    
    def _kill_all_experiment_processes(self, experiment_id):
        """
        通过环境变量杀死所有相关的实验进程（包括训练进程）
        """
        killed_pids = []
        logger.info(f"正在查找并终止实验 {experiment_id} 的所有相关进程...")
        
        try:
            # 扫描所有进程，查找带有对应EOLO_EXPERIMENT_ID环境变量的进程
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'environ']):
                try:
                    environ = proc.info.get('environ', {})
                    if environ and environ.get('EOLO_EXPERIMENT_ID') == str(experiment_id):
                        pid = proc.info['pid']
                        cmdline = ' '.join(proc.info.get('cmdline', []))
                        
                        logger.info(f"发现实验 {experiment_id} 的相关进程: PID {pid}, 命令: {cmdline}")
                        
                        try:
                            # 先尝试温和终止
                            process = psutil.Process(pid)
                            process.terminate()
                            
                            # 等待进程退出
                            try:
                                process.wait(timeout=3)
                                logger.info(f"成功终止进程 PID {pid}")
                            except psutil.TimeoutExpired:
                                # 强制杀死
                                process.kill()
                                process.wait(timeout=2)
                                logger.info(f"强制杀死进程 PID {pid}")
                            
                            killed_pids.append(pid)
                            
                        except psutil.NoSuchProcess:
                            logger.debug(f"进程 PID {pid} 已经不存在")
                        except Exception as kill_e:
                            logger.error(f"终止进程 PID {pid} 失败: {str(kill_e)}")
                
                except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
                    continue
                except Exception as e:
                    logger.debug(f"检查进程时出错: {str(e)}")
                    continue
            
            if killed_pids:
                logger.info(f"已终止实验 {experiment_id} 的 {len(killed_pids)} 个相关进程: {killed_pids}")
            else:
                logger.info(f"未找到实验 {experiment_id} 的相关进程")
        
        except Exception as e:
            logger.error(f"查找实验进程时出错 (实验 {experiment_id}): {str(e)}")
        
        return killed_pids
    
    def _check_log_for_errors(self, log_file):
        """
        检查日志文件中是否包含错误信息
        返回 (has_errors: bool, error_message: str)
        """
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
            
            # 定义错误关键词和对应的错误消息（使用更精确的正则表达式）
            error_patterns = [
                # CUDA/GPU错误
                (r'(?i)\bout of memory\b|\bOOM\b|\bCUDA out of memory\b', '显存不足'),
                (r'(?i)\bcuda\b.*\berror\b|\bCUDA\b.*\bERROR\b', 'CUDA错误'),
                (r'(?i)\bgpu\b.*\berror\b|\bGPU\b.*\bERROR\b', 'GPU错误'),
                
                # Python异常（更精确匹配）
                (r'(?i)^Traceback \(most recent call last\)', 'Python异常'),
                (r'(?i)\bRuntimeError\b:', '运行时错误'),
                (r'(?i)\bValueError\b:', '数值错误'),
                (r'(?i)\bKeyError\b:', '键值错误'),
                (r'(?i)\bIndexError\b:', '索引错误'),
                (r'(?i)\bAttributeError\b:', '属性错误'),
                
                # 训练相关错误（更精确的匹配）
                (r'(?i)\bnan\b.*\bloss\b|\bloss\b.*\bnan\b', '损失函数为NaN'),
                (r'(?i)\binf\b.*\bloss\b|\bloss\b.*\binf\b', '损失函数为无穷大'),
                (r'(?i)\bloss\b.*=.*\bnan\b|\bloss\b.*:.*\bnan\b', '损失函数为NaN'),
                (r'(?i)\bloss\b.*=.*\binf\b|\bloss\b.*:.*\binf\b', '损失函数为无穷大'),
                (r'(?i)training.*failed|failed.*training', '训练失败'),
                
                # 一般错误（更精确匹配）
                (r'(?i)^ERROR:', '一般错误'),
                (r'(?i)\bFATAL\b:', '严重错误'),
                (r'(?i)\bException\b:', '异常'),
                (r'(?i)\bFAILED\b:', '操作失败'),
                (r'(?i)\bABORT\b:', '操作中止'),
            ]
            
            import re
            
            # 检查每个错误模式
            for pattern, error_type in error_patterns:
                matches = re.findall(pattern, log_content)
                if matches:
                    # 尝试提取更详细的错误信息
                    lines = log_content.split('\n')
                    for i, line in enumerate(lines):
                        if re.search(pattern, line):
                            # 获取错误行及其前后几行作为上下文
                            start_line = max(0, i - 2)
                            end_line = min(len(lines), i + 3)
                            context_lines = lines[start_line:end_line]
                            
                            # 清理ANSI转义序列
                            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                            clean_context = [ansi_escape.sub('', line).strip() for line in context_lines]
                            clean_context = [line for line in clean_context if line]
                            
                            if clean_context:
                                detailed_message = f"{error_type}: {' | '.join(clean_context[:2])}"
                                return True, detailed_message
                    
                    # 如果没有找到具体上下文，返回一般错误类型
                    return True, error_type
            
            # 额外检查：查看日志的最后几行是否有异常结束的迹象
            last_lines = log_content.split('\n')[-10:]  # 最后10行
            last_content = '\n'.join(last_lines).lower()
            
            if any(keyword in last_content for keyword in ['error', 'exception', 'failed', 'abort', 'traceback']):
                return True, "训练过程异常结束"
            
            return False, ""
            
        except Exception as e:
            logger.error(f"检查日志文件错误: {str(e)}")
            return False, ""
    
    def _create_log_entry(self, experiment, level, message):
        """
        创建日志条目并返回
        """
        try:
            return ExperimentLog.objects.create(
                experiment=experiment,
                level=level,
                message=message
            )
        except Exception as e:
            logger.error(f"写入实验日志失败: {str(e)}")
            return None
    
    def _log_to_experiment(self, experiment, level, message):
        """
        向实验添加日志记录（兼容性方法）
        """
        return self._create_log_entry(experiment, level, message)
    
    def list_running_experiments(self):
        """
        列出所有正在运行的实验
        """
        running = []
        for exp_id, process_info in self.running_processes.items():
            try:
                experiment = Experiment.objects.get(id=exp_id)
                running.append({
                    'experiment': experiment,
                    'process_info': process_info,
                    'status': self.get_experiment_status(exp_id)
                })
            except:
                pass
        return running
    
    def health_check(self):
        """
        健康检查：清理僵尸进程和不一致的状态
        """
        logger.info("开始进程健康检查...")
        
        # 检查所有正在监控的进程
        dead_experiments = []
        
        for exp_id, process_info in list(self.running_processes.items()):
            try:
                process = process_info['process']
                
                # 检查进程状态
                exit_code = process.poll()
                if exit_code is not None:
                    # 进程已死，但还在监控列表中
                    logger.warning(f"发现僵尸进程 (实验 {exp_id}, 退出码: {exit_code})")
                    dead_experiments.append((exp_id, exit_code, "僵尸进程"))
                    continue
                
                # 使用psutil双重检查
                try:
                    psutil_process = psutil.Process(process.pid)
                    if not psutil_process.is_running():
                        logger.warning(f"发现不一致进程状态 (实验 {exp_id})")
                        dead_experiments.append((exp_id, -1, "进程状态不一致"))
                except psutil.NoSuchProcess:
                    logger.warning(f"发现不存在的进程 (实验 {exp_id}, PID: {process.pid})")
                    dead_experiments.append((exp_id, -1, "进程不存在"))
                    
            except Exception as e:
                logger.error(f"健康检查进程时出错 (实验 {exp_id}): {str(e)}")
                dead_experiments.append((exp_id, -1, f"检查异常: {str(e)}"))
        
        # 清理发现的死进程
        for exp_id, exit_code, reason in dead_experiments:
            logger.info(f"清理死进程: 实验 {exp_id}, 原因: {reason}")
            self._cleanup_experiment_process(exp_id, reason)
        
        # 检查数据库中状态为running但不在监控列表中的实验
        try:
            from .models import Experiment
            orphaned_experiments = Experiment.objects.filter(status='running').exclude(
                id__in=self.running_processes.keys()
            )
            
            for exp in orphaned_experiments:
                logger.warning(f"发现孤儿实验 (ID: {exp.id}): 数据库状态为running但未在监控")
                exp.fail_experiment("进程监控丢失")
                self._log_to_experiment(exp, 'ERROR', "进程监控丢失，标记为失败")
                
        except Exception as e:
            logger.error(f"检查孤儿实验时出错: {str(e)}")
        
        logger.info(f"健康检查完成，清理了 {len(dead_experiments)} 个死进程")
        return {
            'cleaned_processes': len(dead_experiments),
            'details': dead_experiments
        }
    
    def _save_process_info(self, experiment_id, process_info):
        """
        将进程信息保存到文件，用于重启后恢复监控
        """
        try:
            import json
            pid_file = self.pid_file_dir / f"exp_{experiment_id}.json"
            
            # 保存完整的进程信息（不包含process对象）
            save_data = {
                'experiment_id': experiment_id,
                'pid': process_info['process'].pid,
                'command': process_info['command'],
                'start_time': process_info['start_time'],
                'log_file': process_info.get('log_file'),
                'independent': process_info.get('independent', False),
                'save_time': time.time()
            }
            
            with open(pid_file, 'w') as f:
                json.dump(save_data, f, indent=2)
                
            logger.debug(f"已保存实验 {experiment_id} 的进程信息到 {pid_file}")
            
        except Exception as e:
            logger.error(f"保存进程信息失败 (实验 {experiment_id}): {str(e)}")
    
    def _remove_process_info(self, experiment_id):
        """
        删除保存的进程信息文件
        """
        try:
            pid_file = self.pid_file_dir / f"exp_{experiment_id}.json"
            if pid_file.exists():
                pid_file.unlink()
                logger.debug(f"已删除实验 {experiment_id} 的进程信息文件")
        except Exception as e:
            logger.error(f"删除进程信息文件失败 (实验 {experiment_id}): {str(e)}")
    
    def _restore_process_monitoring(self):
        """
        Django重启后恢复对正在运行进程的监控
        """
        logger.info("正在恢复进程监控...")
        restored_count = 0
        
        try:
            import json
            
            # 遍历保存的进程信息文件
            for pid_file in self.pid_file_dir.glob("exp_*.json"):
                try:
                    with open(pid_file, 'r') as f:
                        process_data = json.load(f)
                    
                    experiment_id = process_data['experiment_id']
                    pid = process_data['pid']
                    
                    # 检查进程是否还在运行
                    try:
                        psutil_process = psutil.Process(pid)
                        if psutil_process.is_running():
                            # 验证这个进程确实是我们的训练进程
                            is_our_process = False
                            try:
                                # 检查环境变量
                                environ = psutil_process.environ()
                                if environ.get('EOLO_EXPERIMENT_ID') == str(experiment_id):
                                    is_our_process = True
                                    logger.info(f"通过环境变量确认进程 {pid} 属于实验 {experiment_id}")
                            except (psutil.AccessDenied, psutil.ZombieProcess):
                                # 无法访问环境变量，通过命令行检查
                                try:
                                    cmdline = ' '.join(psutil_process.cmdline())
                                    if ('train.py' in cmdline or 'train' in cmdline) and ('python' in cmdline or 'uv run' in cmdline):
                                        is_our_process = True
                                        logger.info(f"通过命令行确认进程 {pid} 可能属于实验 {experiment_id}")
                                except:
                                    pass
                            
                            if is_our_process:
                                # 进程还在运行，恢复监控
                                experiment = Experiment.objects.get(id=experiment_id)
                                
                                # 创建新的process_info对象
                                class RestoredProcess:
                                    def __init__(self, pid, psutil_proc, manager, experiment_id):
                                        self.pid = pid
                                        self._psutil_proc = psutil_proc
                                        self._manager = manager
                                        self._experiment_id = experiment_id
                                        self._exit_code = None
                                        self._process_ended = False
                                    
                                    def poll(self):
                                        """
                                        检查恢复的训练进程状态并返回退出码
                                        优先使用从日志中提取的实际退出码
                                        """
                                        if self._process_ended and self._exit_code is not None:
                                            return self._exit_code
                                        
                                        try:
                                            if self._psutil_proc.is_running():
                                                return None  # 进程仍在运行
                                            else:
                                                # 进程已结束，首先尝试从process_info中获取实际退出码
                                                if not self._process_ended:
                                                    process_info = self._manager.running_processes.get(self._experiment_id)
                                                    if process_info and 'actual_exit_code' in process_info:
                                                        # 使用从日志中提取的实际训练进程退出码
                                                        self._exit_code = process_info['actual_exit_code']
                                                        logger.info(f"恢复进程使用从日志提取的实际退出码: {self._exit_code} (PID: {self.pid})")
                                                    else:
                                                        # 如果没有实际退出码，回退到系统方法（但可能不准确）
                                                        try:
                                                            status = self._psutil_proc.status()
                                                            if status == psutil.STATUS_ZOMBIE:
                                                                try:
                                                                    self._exit_code = self._psutil_proc.wait(timeout=2)
                                                                    logger.warning(f"恢复进程使用系统退出码（可能不准确）: {self._exit_code} (PID: {self.pid})")
                                                                except psutil.TimeoutExpired:
                                                                    logger.warning(f"恢复进程无法在超时内获取退出码 (PID: {self.pid})")
                                                                    self._exit_code = -1
                                                            else:
                                                                try:
                                                                    self._exit_code = self._psutil_proc.returncode
                                                                    if self._exit_code is None:
                                                                        self._exit_code = 0
                                                                    logger.warning(f"恢复进程使用系统退出码（可能不准确）: {self._exit_code} (PID: {self.pid})")
                                                                except AttributeError:
                                                                    self._exit_code = 0
                                                                    logger.warning(f"恢复进程无法获取退出码，默认为0 (PID: {self.pid})")
                                                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                                                            logger.warning(f"恢复的训练进程已不存在，默认退出码为0 (PID: {self.pid})")
                                                            self._exit_code = 0
                                                    self._process_ended = True
                                                return self._exit_code
                                        except psutil.NoSuchProcess:
                                            if not self._process_ended:
                                                # 尝试从process_info获取实际退出码
                                                process_info = self._manager.running_processes.get(self._experiment_id)
                                                if process_info and 'actual_exit_code' in process_info:
                                                    self._exit_code = process_info['actual_exit_code']
                                                    logger.info(f"恢复进程不存在，使用从日志提取的退出码: {self._exit_code} (PID: {self.pid})")
                                                else:
                                                    logger.warning(f"恢复的训练进程不存在，未找到实际退出码，默认为0 (PID: {self.pid})")
                                                    self._exit_code = 0
                                                self._process_ended = True
                                            return self._exit_code
                                    
                                    def terminate(self):
                                        try:
                                            # 首先杀死所有相关进程
                                            self._manager._kill_all_experiment_processes(self._experiment_id)
                                            return self._psutil_proc.terminate()
                                        except psutil.NoSuchProcess:
                                            pass
                                    
                                    def kill(self):
                                        try:
                                            # 首先杀死所有相关进程
                                            self._manager._kill_all_experiment_processes(self._experiment_id)
                                            return self._psutil_proc.kill()
                                        except psutil.NoSuchProcess:
                                            pass
                                    
                                    def wait(self, timeout=None):
                                        try:
                                            return self._psutil_proc.wait(timeout)
                                        except psutil.NoSuchProcess:
                                            return 0
                                
                                process_info = {
                                    'process': RestoredProcess(pid, psutil_process, self, experiment_id),
                                    'command': process_data['command'],
                                    'start_time': process_data['start_time'],
                                    'experiment_id': experiment_id,
                                    'log_file': process_data.get('log_file'),
                                    'independent': process_data.get('independent', False),
                                    'restored': True  # 标记为恢复的进程
                                }
                                
                                # 恢复到监控列表
                                self.running_processes[experiment_id] = process_info
                                
                                # 确保实验状态正确
                                if experiment.status != 'running':
                                    experiment.status = 'running'
                                    experiment.save()
                                
                                # 重新启动进程监控
                                self._start_process_monitoring(experiment, process_info, skip_log=True)
                                
                                # 如果有日志文件，启动文件日志监控
                                if process_data.get('log_file') and process_data.get('independent'):
                                    self._start_file_log_monitoring(experiment, process_info)
                                
                                restored_count += 1
                                logger.info(f"已恢复对实验 {experiment_id} (PID: {pid}) 的监控")
                                
                                # 记录恢复日志
                                self._log_to_experiment(experiment, 'INFO', 
                                    f"Django重启后恢复进程监控 (PID: {pid})")
                            else:
                                logger.warning(f"进程 {pid} 不属于实验 {experiment_id}，跳过恢复")
                                # 清理无关的文件
                                pid_file.unlink()
                        else:
                            # 进程已不存在，清理文件
                            logger.warning(f"实验 {experiment_id} 的进程 {pid} 已不存在，清理状态文件")
                            pid_file.unlink()
                            
                            # 更新数据库状态
                            try:
                                experiment = Experiment.objects.get(id=experiment_id)
                                if experiment.status == 'running':
                                    experiment.fail_experiment("进程在Django重启期间意外终止")
                                    self._log_to_experiment(experiment, 'ERROR', 
                                        "检测到进程在Django重启期间意外终止")
                            except Experiment.DoesNotExist:
                                pass
                                
                    except psutil.NoSuchProcess:
                        # 进程不存在
                        logger.warning(f"实验 {experiment_id} 的进程 {pid} 不存在，清理状态文件")
                        pid_file.unlink()
                        
                        # 更新数据库状态
                        try:
                            experiment = Experiment.objects.get(id=experiment_id)
                            if experiment.status == 'running':
                                experiment.fail_experiment("进程已不存在")
                                self._log_to_experiment(experiment, 'ERROR', 
                                    "检测到进程已不存在")
                        except Experiment.DoesNotExist:
                            pass
                            
                except Exception as e:
                    logger.error(f"恢复进程监控失败 ({pid_file}): {str(e)}")
                    # 删除有问题的文件
                    try:
                        pid_file.unlink()
                    except:
                        pass
        
        except Exception as e:
            logger.error(f"恢复进程监控时出错: {str(e)}")
        
        logger.info(f"进程监控恢复完成，共恢复 {restored_count} 个进程的监控")
        
        # 额外检查：查找可能遗漏的训练进程
        self._scan_for_orphaned_processes()

    def _scan_for_orphaned_processes(self):
        """
        扫描系统中可能遗漏的训练进程（通过环境变量识别）
        """
        logger.info("扫描可能遗漏的训练进程...")
        found_count = 0
        
        try:
            # 扫描所有进程，查找带有EOLO_EXPERIMENT_ID环境变量的进程
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'environ', 'create_time']):
                try:
                    environ = proc.info.get('environ', {})
                    eolo_exp_id = environ.get('EOLO_EXPERIMENT_ID')
                    
                    if eolo_exp_id:
                        experiment_id = int(eolo_exp_id)
                        
                        # 检查这个实验是否已经在监控中
                        if experiment_id not in self.running_processes:
                            logger.info(f"发现遗漏的训练进程: 实验 {experiment_id}, PID {proc.info['pid']}")
                            
                            try:
                                experiment = Experiment.objects.get(id=experiment_id)
                                
                                # 创建进程信息
                                class OrphanedProcess:
                                    def __init__(self, pid, manager, experiment_id):
                                        self.pid = pid
                                        self._psutil_proc = psutil.Process(pid)
                                        self._manager = manager
                                        self._experiment_id = experiment_id
                                    
                                    def poll(self):
                                        try:
                                            return None if self._psutil_proc.is_running() else 0
                                        except psutil.NoSuchProcess:
                                            return -1
                                    
                                    def terminate(self):
                                        try:
                                            # 首先杀死所有相关进程
                                            self._manager._kill_all_experiment_processes(self._experiment_id)
                                            return self._psutil_proc.terminate()
                                        except psutil.NoSuchProcess:
                                            pass
                                    
                                    def kill(self):
                                        try:
                                            # 首先杀死所有相关进程
                                            self._manager._kill_all_experiment_processes(self._experiment_id)
                                            return self._psutil_proc.kill()
                                        except psutil.NoSuchProcess:
                                            pass
                                    
                                    def wait(self, timeout=None):
                                        try:
                                            return self._psutil_proc.wait(timeout)
                                        except psutil.NoSuchProcess:
                                            return 0
                                
                                # 估算命令（从cmdline重构）
                                cmdline = proc.info.get('cmdline', [])
                                estimated_command = ' '.join(cmdline) if cmdline else 'unknown'
                                
                                process_info = {
                                    'process': OrphanedProcess(proc.info['pid'], self, experiment_id),
                                    'command': estimated_command,
                                    'start_time': proc.info.get('create_time', time.time()),
                                    'experiment_id': experiment_id,
                                    'independent': True,
                                    'orphaned': True  # 标记为孤儿进程
                                }
                                
                                # 添加到监控列表
                                self.running_processes[experiment_id] = process_info
                                
                                # 确保实验状态正确
                                if experiment.status != 'running':
                                    experiment.status = 'running'
                                    experiment.save()
                                
                                # 启动监控
                                self._start_process_monitoring(experiment, process_info, skip_log=True)
                                
                                # 保存进程信息文件
                                self._save_process_info(experiment_id, process_info)
                                
                                found_count += 1
                                logger.info(f"已将孤儿进程加入监控: 实验 {experiment_id}, PID {proc.info['pid']}")
                                
                                # 记录恢复日志
                                self._log_to_experiment(experiment, 'INFO', 
                                    f"发现并恢复遗漏的训练进程 (PID: {proc.info['pid']})")
                                    
                            except Experiment.DoesNotExist:
                                logger.warning(f"实验 {experiment_id} 不存在，但有对应的训练进程 {proc.info['pid']}")
                            except Exception as e:
                                logger.error(f"处理孤儿进程失败 (实验 {experiment_id}, PID {proc.info['pid']}): {str(e)}")
                
                except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
                    # 无法访问进程信息，跳过
                    continue
                except Exception as e:
                    # 其他错误，记录但继续
                    logger.debug(f"检查进程时出错: {str(e)}")
                    continue
        
        except Exception as e:
            logger.error(f"扫描孤儿进程时出错: {str(e)}")
        
        if found_count > 0:
            logger.info(f"孤儿进程扫描完成，发现并恢复了 {found_count} 个遗漏的训练进程")
        else:
            logger.info("孤儿进程扫描完成，未发现遗漏的训练进程")

    def scan_and_cleanup_orphaned_processes(self):
        """
        手动扫描并清理孤儿进程（用于管理界面调用）
        """
        logger.info("开始手动扫描和清理孤儿进程...")
        results = {
            'found_processes': [],
            'cleaned_processes': [],
            'restored_processes': [],
            'errors': []
        }
        
        try:
            # 扫描所有进程，查找训练相关的进程
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'environ', 'create_time']):
                try:
                    # 安全获取进程信息
                    proc_info = proc.info
                    if not proc_info:
                        continue
                    
                    environ = proc_info.get('environ')
                    eolo_exp_id = environ.get('EOLO_EXPERIMENT_ID') if environ else None
                    cmdline_list = proc_info.get('cmdline')
                    cmdline = ' '.join(cmdline_list) if cmdline_list else ''
                    
                    # 如果有EOLO_EXPERIMENT_ID环境变量
                    if eolo_exp_id:
                        experiment_id = int(eolo_exp_id)
                        process_info = {
                            'pid': proc_info['pid'],
                            'experiment_id': experiment_id,
                            'cmdline': cmdline,
                            'create_time': proc_info.get('create_time'),
                            'identification_method': 'environment_variable'
                        }
                        results['found_processes'].append(process_info)
                        
                        # 检查实验是否存在
                        try:
                            experiment = Experiment.objects.get(id=experiment_id)
                            
                            # 检查是否已经在监控中
                            if experiment_id not in self.running_processes:
                                # 恢复监控
                                self._restore_single_process(experiment, proc_info['pid'], cmdline)
                                results['restored_processes'].append(process_info)
                                logger.info(f"恢复实验 {experiment_id} 的监控 (PID: {proc_info['pid']})")
                            else:
                                logger.debug(f"实验 {experiment_id} 已在监控中 (PID: {proc_info['pid']})")
                        
                        except Experiment.DoesNotExist:
                            # 实验不存在，这是个孤儿进程
                            logger.warning(f"发现孤儿进程: PID {proc_info['pid']}, 对应不存在的实验 {experiment_id}")
                            try:
                                psutil.Process(proc_info['pid']).terminate()
                                results['cleaned_processes'].append(process_info)
                                logger.info(f"已终止孤儿进程 PID {proc_info['pid']}")
                            except Exception as clean_e:
                                error_msg = f"终止孤儿进程失败 (PID {proc_info['pid']}): {str(clean_e)}"
                                results['errors'].append(error_msg)
                                logger.error(error_msg)
                    
                    # 或者通过命令行特征识别训练进程（支持python和uv run）
                    elif ('train.py' in cmdline or 'EOLO' in cmdline) and ('python' in cmdline or 'uv run' in cmdline):
                        process_info = {
                            'pid': proc.info['pid'],
                            'experiment_id': 'unknown',
                            'cmdline': cmdline,
                            'create_time': proc.info.get('create_time'),
                            'identification_method': 'cmdline_pattern'
                        }
                        results['found_processes'].append(process_info)
                        logger.info(f"发现可能的训练进程 (通过命令行): PID {proc.info['pid']}, 命令: {cmdline}")
                
                except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
                    continue
                except Exception as e:
                    error_msg = f"检查进程时出错 (PID {proc.info.get('pid', 'unknown')}): {str(e)}"
                    results['errors'].append(error_msg)
                    logger.debug(error_msg)
        
        except Exception as e:
            error_msg = f"扫描进程时出错: {str(e)}"
            results['errors'].append(error_msg)
            logger.error(error_msg)
        
        logger.info(f"孤儿进程扫描完成: 发现 {len(results['found_processes'])} 个训练进程, "
                   f"恢复 {len(results['restored_processes'])} 个, 清理 {len(results['cleaned_processes'])} 个")
        
        return results

    def _restore_single_process(self, experiment, pid, cmdline):
        """
        恢复单个进程的监控
        """
        try:
            psutil_process = psutil.Process(pid)
            
            class RestoredSingleProcess:
                def __init__(self, pid, manager, experiment_id):
                    self.pid = pid
                    self._psutil_proc = psutil.Process(pid)
                    self._manager = manager
                    self._experiment_id = experiment_id
                
                def poll(self):
                    try:
                        return None if self._psutil_proc.is_running() else 0
                    except psutil.NoSuchProcess:
                        return -1
                
                def terminate(self):
                    try:
                        # 首先杀死所有相关进程
                        self._manager._kill_all_experiment_processes(self._experiment_id)
                        return self._psutil_proc.terminate()
                    except psutil.NoSuchProcess:
                        pass
                
                def kill(self):
                    try:
                        # 首先杀死所有相关进程
                        self._manager._kill_all_experiment_processes(self._experiment_id)
                        return self._psutil_proc.kill()
                    except psutil.NoSuchProcess:
                        pass
                
                def wait(self, timeout=None):
                    try:
                        return self._psutil_proc.wait(timeout)
                    except psutil.NoSuchProcess:
                        return 0
            
            process_info = {
                'process': RestoredSingleProcess(pid, self, experiment.id),
                'command': cmdline,
                'start_time': psutil_process.create_time(),
                'experiment_id': experiment.id,
                'independent': True,
                'restored': True
            }
            
            # 添加到监控列表
            self.running_processes[experiment.id] = process_info
            
            # 确保实验状态正确
            if experiment.status != 'running':
                experiment.status = 'running'
                experiment.save()
            
            # 启动监控
            self._start_process_monitoring(experiment, process_info, skip_log=True)
            
            # 保存进程信息
            self._save_process_info(experiment.id, process_info)
            
            # 记录日志
            self._log_to_experiment(experiment, 'INFO', 
                f"手动扫描后恢复进程监控 (PID: {pid})")
        
        except Exception as e:
            logger.error(f"恢复单个进程监控失败 (实验 {experiment.id}, PID {pid}): {str(e)}")
            raise

    def force_cleanup_all_training_processes(self):
        """
        强制清理所有训练进程（紧急情况使用）
        """
        logger.warning("开始强制清理所有训练进程...")
        cleaned_count = 0
        
        try:
            # 扫描所有带有EOLO_EXPERIMENT_ID的进程
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'environ']):
                try:
                    environ = proc.info.get('environ', {})
                    if environ.get('EOLO_EXPERIMENT_ID'):
                        logger.info(f"强制终止训练进程 PID {proc.info['pid']}")
                        psutil.Process(proc.info['pid']).terminate()
                        cleaned_count += 1
                except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
                    continue
                except Exception as e:
                    logger.error(f"终止进程失败 (PID {proc.info.get('pid')}): {str(e)}")
            
            # 清理所有进程信息文件
            for pid_file in self.pid_file_dir.glob("exp_*.json"):
                try:
                    pid_file.unlink()
                except Exception as e:
                    logger.error(f"删除进程信息文件失败 ({pid_file}): {str(e)}")
            
            # 清理内存中的进程信息
            self.running_processes.clear()
            
            # 更新所有运行中实验的状态
            from .models import Experiment
            running_experiments = Experiment.objects.filter(status='running')
            for exp in running_experiments:
                exp.fail_experiment("手动强制清理所有训练进程")
                self._log_to_experiment(exp, 'WARNING', "训练进程被手动强制清理")
        
        except Exception as e:
            logger.error(f"强制清理训练进程时出错: {str(e)}")
        
        logger.warning(f"强制清理完成，共清理 {cleaned_count} 个训练进程")
        return cleaned_count


# 全局进程管理器实例
process_manager = ExperimentProcessManager()
