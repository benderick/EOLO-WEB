"""
GPU队列调度器模块
负责管理实验排队和自动调度
"""
import threading
import time
import logging
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from .models import Experiment
from .gpu_utils import check_gpu_availability
from .process_manager import process_manager

logger = logging.getLogger(__name__)


class GPUQueueScheduler:
    """
    GPU队列调度器
    管理实验排队序列并自动调度
    """
    
    def __init__(self):
        self.scheduler_thread = None
        self.running = False
        
        # 从配置获取参数
        scheduler_config = getattr(settings, 'QUEUE_SCHEDULER_CONFIG', {})
        self.check_interval = scheduler_config.get('CHECK_INTERVAL', 30)
        self.thread_name = scheduler_config.get('THREAD_NAME', 'GPUQueueScheduler')
        
        self._lock = threading.Lock()
        
    def start_scheduler(self):
        """
        启动调度器线程
        """
        with self._lock:
            if self.running:
                logger.warning("调度器已经在运行中")
                return
            
            self.running = True
            self.scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                daemon=True,
                name=self.thread_name
            )
            self.scheduler_thread.start()
            logger.info("GPU队列调度器已启动")
    
    def stop_scheduler(self):
        """
        停止调度器线程
        """
        with self._lock:
            if not self.running:
                return
            
            self.running = False
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                self.scheduler_thread.join(timeout=5)
            logger.info("GPU队列调度器已停止")
    
    def _scheduler_loop(self):
        """
        调度器主循环
        """
        logger.info("调度器主循环开始")
        
        while self.running:
            try:
                self._process_queue()
            except Exception as e:
                logger.error(f"调度器处理队列时出错: {str(e)}")
            
            # 等待下一次检查
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)
        
        logger.info("调度器主循环结束")
    
    def _process_queue(self):
        """
        处理排队中的实验
        """
        try:
            # 获取所有排队中的实验，按创建时间排序
            queued_experiments = Experiment.objects.filter(
                status='queued'
            ).order_by('created_at')
            
            if not queued_experiments:
                return
            
            logger.debug(f"发现 {queued_experiments.count()} 个排队实验")
            
            # 按GPU设备分组处理
            device_groups = {}
            for exp in queued_experiments:
                device = exp.device or 'auto'
                if device not in device_groups:
                    device_groups[device] = []
                device_groups[device].append(exp)
            
            # 为每个设备组检查GPU可用性并启动实验
            for device, experiments in device_groups.items():
                self._process_device_queue(device, experiments)
                
        except Exception as e:
            logger.error(f"处理队列时出错: {str(e)}")
    
    def _process_device_queue(self, device, experiments):
        """
        处理特定设备的实验队列
        
        Args:
            device: 设备字符串
            experiments: 该设备的排队实验列表
        """
        try:
            # 检查GPU可用性
            gpu_check = check_gpu_availability(device)
            
            if not gpu_check['available']:
                logger.debug(f"设备 {device} 仍在使用中: {gpu_check['message']}")
                return
            
            # 获取设备对应的GPU索引，用于冲突检测
            device_gpu_indices = self._get_device_gpu_indices(device)
            
            # 检查是否有其他实验正在使用相同的GPU
            if self._has_gpu_conflict(device_gpu_indices):
                logger.debug(f"设备 {device} 的GPU正被其他实验使用")
                return
            
            # 按创建时间顺序处理，每次只启动一个实验
            for exp in experiments:
                try:
                    # 分别处理以避免事务冲突
                    success = self._try_start_experiment(exp, device)
                    
                    if success:
                        logger.info(f"从队列自动启动实验: {exp.name} (ID: {exp.id})")
                        
                        # 如果设备是独占性的，停止处理该设备的其他实验
                        if self._is_exclusive_device(device):
                            logger.debug(f"设备 {device} 为独占模式，停止处理其他排队实验")
                            break
                        
                        # 非独占设备，也要检查GPU数量限制
                        if self._should_stop_for_device(device, device_gpu_indices):
                            logger.debug(f"设备 {device} 已达到并发限制")
                            break
                    else:
                        # 启动失败，继续处理下一个（可能是临时问题）
                        logger.debug(f"启动实验 {exp.id} 失败，继续处理下一个")
                        continue
                        
                except Exception as e:
                    logger.error(f"处理排队实验时出错 (ID: {exp.id}): {str(e)}")
                    # 标记实验为错误状态，但不影响其他实验
                    self._mark_experiment_failed(exp.id, f"队列调度异常: {str(e)}")
                    continue
                        
        except Exception as e:
            logger.error(f"处理设备 {device} 队列时出错: {str(e)}")
    
    def _try_start_experiment(self, experiment, device):
        """
        尝试启动单个实验，避免事务冲突
        
        Args:
            experiment: 实验对象
            device: 设备字符串
            
        Returns:
            bool: 是否启动成功
        """
        try:
            # 使用独立的事务检查和更新状态
            with transaction.atomic():
                fresh_exp = Experiment.objects.select_for_update().get(id=experiment.id)
                
                if fresh_exp.status != 'queued':
                    logger.debug(f"实验 {experiment.id} 状态已改变: {fresh_exp.status}")
                    return False
                
                # 在事务中再次快速检查GPU（避免竞争条件）
                gpu_check = check_gpu_availability(device)
                if not gpu_check['available']:
                    logger.debug(f"最终检查: 设备 {device} 不可用")
                    return False
                
                # 这里不启动进程，只是预留状态，避免事务冲突
                fresh_exp.status = 'pending'  # 临时设为pending，准备启动
                fresh_exp.save()
            
            # 在事务外启动进程
            success, message = process_manager.start_experiment(
                experiment.id, 
                force_start=True
            )
            
            if success:
                # 记录调度日志
                process_manager._log_to_experiment(
                    experiment, 
                    'INFO', 
                    f"队列调度器自动启动实验 (设备: {device})"
                )
                return True
            else:
                logger.warning(f"启动实验失败: {experiment.name} - {message}")
                # 启动失败，恢复为排队状态或标记为错误
                self._handle_start_failure(experiment.id, message)
                return False
                
        except Exception as e:
            logger.error(f"启动实验时出错 (ID: {experiment.id}): {str(e)}")
            self._mark_experiment_failed(experiment.id, f"启动异常: {str(e)}")
            return False
    
    def _get_device_gpu_indices(self, device):
        """
        获取设备对应的GPU索引列表
        
        Args:
            device: 设备字符串
            
        Returns:
            set: GPU索引集合
        """
        from .gpu_utils import parse_device_string
        gpu_indices = parse_device_string(device)
        return set(gpu_indices)
    
    def _has_gpu_conflict(self, device1, device2=None):
        """
        检查是否有GPU冲突
        
        Args:
            device1: 第一个设备字符串或GPU索引集合
            device2: 第二个设备字符串（可选）
            
        Returns:
            bool: 是否有冲突
        """
        # 如果只有一个参数，检查与正在运行的实验的冲突
        if device2 is None:
            if isinstance(device1, set):
                device_gpu_indices = device1
            else:
                device_gpu_indices = self._get_device_gpu_indices(device1)
                
            if not device_gpu_indices:  # auto, cpu等
                return False
                
            # 检查所有正在运行的实验
            try:
                running_experiments = Experiment.objects.filter(status='running')
                
                for exp in running_experiments:
                    if exp.device:
                        running_gpu_indices = self._get_device_gpu_indices(exp.device)
                        # 检查GPU索引是否有重叠
                        if device_gpu_indices & running_gpu_indices:
                            return True
                return False
            except:
                return True  # 出错时保守处理
        
        # 如果有两个参数，检查两个设备之间的冲突
        device1_indices = self._get_device_gpu_indices(device1)
        device2_indices = self._get_device_gpu_indices(device2)
        
        # 如果任一设备不是GPU，则无冲突
        if not device1_indices or not device2_indices:
            return False
            
        # 检查GPU索引是否有重叠
        return bool(device1_indices & device2_indices)
    
    def _should_stop_for_device(self, device, device_gpu_indices):
        """
        判断是否应该停止为该设备启动更多实验
        
        Args:
            device: 设备字符串
            device_gpu_indices: 设备的GPU索引集合
            
        Returns:
            bool: 是否应该停止
        """
        # 对于单GPU设备，启动一个后就停止
        if len(device_gpu_indices) == 1:
            return True
            
        # 对于多GPU设备，检查是否已有实验在使用
        return self._has_gpu_conflict(device_gpu_indices)
    
    def _handle_start_failure(self, experiment_id, message):
        """
        处理启动失败的情况
        """
        try:
            with transaction.atomic():
                exp = Experiment.objects.select_for_update().get(id=experiment_id)
                # 根据失败原因决定是恢复排队还是标记错误
                if "GPU" in message or "显存" in message:
                    # GPU相关问题，恢复排队状态
                    exp.queue_experiment()
                    logger.info(f"实验 {experiment_id} 因GPU问题启动失败，恢复排队状态")
                else:
                    # 其他问题，标记为错误
                    exp.fail_experiment(f"队列调度启动失败: {message}")
        except Exception as e:
            logger.error(f"处理启动失败时出错: {str(e)}")
    
    def _mark_experiment_failed(self, experiment_id, reason):
        """
        标记实验为失败状态
        """
        try:
            with transaction.atomic():
                exp = Experiment.objects.select_for_update().get(id=experiment_id)
                exp.fail_experiment(reason)
                process_manager._log_to_experiment(exp, 'ERROR', reason)
        except Exception as e:
            logger.error(f"标记实验失败时出错: {str(e)}")
    
    def _is_exclusive_device(self, device):
        """
        判断设备是否是独占性的
        
        Args:
            device: 设备字符串
            
        Returns:
            bool: 如果是单个GPU设备返回True，多GPU或auto返回False
        """
        if not device or device.lower() in ['auto', 'cpu']:
            return False
        
        try:
            # 获取GPU索引
            gpu_indices = self._get_device_gpu_indices(device)
            
            # 单GPU设备是独占的
            if len(gpu_indices) == 1:
                return True
            
            # 多GPU设备一般也是独占的（一个训练任务占用多个GPU）
            # 除非明确配置为可共享
            return True
            
        except:
            return True  # 出错时保守处理
    
    def get_queue_status(self):
        """
        获取队列状态
        
        Returns:
            dict: 队列状态信息
        """
        try:
            queued_experiments = Experiment.objects.filter(
                status='queued'
            ).order_by('created_at')
            
            # 按设备分组统计
            device_stats = {}
            for exp in queued_experiments:
                device = exp.device or 'auto'
                if device not in device_stats:
                    device_stats[device] = {
                        'count': 0,
                        'experiments': []
                    }
                device_stats[device]['count'] += 1
                device_stats[device]['experiments'].append({
                    'id': exp.id,
                    'name': exp.name,
                    'user': exp.user.username,
                    'created_at': exp.created_at,
                    'queued_time': (timezone.now() - exp.created_at).total_seconds()
                })
            
            return {
                'scheduler_running': self.running,
                'total_queued': queued_experiments.count(),
                'device_groups': device_stats,
                'check_interval': self.check_interval
            }
            
        except Exception as e:
            logger.error(f"获取队列状态时出错: {str(e)}")
            return {
                'scheduler_running': self.running,
                'total_queued': 0,
                'device_groups': {},
                'check_interval': self.check_interval,
                'error': str(e)
            }
    
    def add_to_queue(self, experiment_id):
        """
        手动将实验添加到队列
        
        Args:
            experiment_id: 实验ID
            
        Returns:
            tuple: (success, message)
        """
        try:
            experiment = Experiment.objects.get(id=experiment_id)
            
            if experiment.status not in ['pending', 'error', 'interrupted']:
                return False, f"实验状态不允许加入队列: {experiment.status}"
            
            experiment.queue_experiment()
            
            # 记录队列日志
            process_manager._log_to_experiment(
                experiment, 
                'INFO', 
                f"实验手动加入队列 (设备: {experiment.device})"
            )
            
            logger.info(f"实验 {experiment.name} (ID: {experiment_id}) 已加入队列")
            return True, "实验已加入队列"
            
        except Experiment.DoesNotExist:
            return False, "实验不存在"
        except Exception as e:
            logger.error(f"添加实验到队列时出错 (ID: {experiment_id}): {str(e)}")
            return False, f"添加到队列失败: {str(e)}"


# 全局调度器实例
gpu_scheduler = GPUQueueScheduler()
