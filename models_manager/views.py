"""
模型管理器视图
"""
import json
import subprocess
import os
import threading
import time
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
from .models import model_file_manager, setting_file_manager


@login_required
def model_manager_view(request):
    """
    模型管理器主页面
    """
    response = render(request, 'models_manager/model_manager.html')
    # 添加禁用缓存的头部
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@method_decorator(login_required, name='dispatch')
class ModelTreeAPIView(View):
    """
    模型文件树API视图
    """
    
    def get(self, request):
        """
        获取模型文件树结构
        """
        try:
            username = request.user.username
            
            # 确保用户文件夹存在
            user_path = model_file_manager.ensure_user_folder(username)
            
            # 获取common文件夹树
            common_tree = model_file_manager.get_directory_tree(model_file_manager.common_path)
            
            # 获取用户文件夹树
            user_tree = model_file_manager.get_directory_tree(user_path)
            
            return JsonResponse({
                'success': True,
                'data': {
                    'common': common_tree,
                    'user': user_tree,
                    'username': username
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f"获取文件树失败: {str(e)}"
            })


@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class FileContentAPIView(View):
    """
    文件内容API视图
    """
    
    def get(self, request):
        """
        获取文件内容
        """
        try:
            file_path = request.GET.get('path', '')
            
            if not file_path:
                return JsonResponse({
                    'success': False,
                    'error': '文件路径不能为空'
                })
            
            content = model_file_manager.get_file_content(file_path)
            
            if content is None:
                return JsonResponse({
                    'success': False,
                    'error': '文件不存在或无法读取'
                })
            
            return JsonResponse({
                'success': True,
                'data': {
                    'content': content,
                    'path': file_path
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f"读取文件失败: {str(e)}"
            })
    
    def post(self, request):
        """
        保存文件内容
        """
        try:
            data = json.loads(request.body)
            file_path = data.get('path', '')
            content = data.get('content', '')
            
            if not file_path:
                return JsonResponse({
                    'success': False,
                    'error': '文件路径不能为空'
                })
            
            success, message = model_file_manager.save_file_content(
                file_path, content, request.user.username
            )
            
            return JsonResponse({
                'success': success,
                'message': message
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': '请求数据格式错误'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f"保存文件失败: {str(e)}"
            })


@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class FileOperationAPIView(View):
    """
    文件操作API视图（创建、删除等）
    """
    
    def post(self, request):
        """
        执行文件操作
        """
        try:
            data = json.loads(request.body)
            operation = data.get('operation', '')
            
            if operation == 'create_folder':
                return self._create_folder(data, request.user.username)
            elif operation == 'delete':
                return self._delete_file(data, request.user.username)
            else:
                return JsonResponse({
                    'success': False,
                    'error': '不支持的操作类型'
                })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': '请求数据格式错误'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f"操作失败: {str(e)}"
            })
    
    def _create_folder(self, data, username):
        """
        创建文件夹
        """
        parent_path = data.get('parent_path', '')
        folder_name = data.get('folder_name', '')
        
        if not folder_name:
            return JsonResponse({
                'success': False,
                'error': '文件夹名称不能为空'
            })
        
        success, message = model_file_manager.create_folder(
            parent_path, folder_name, username
        )
        
        return JsonResponse({
            'success': success,
            'message': message
        })
    
    def _delete_file(self, data, username):
        """
        删除文件或文件夹
        """
        file_path = data.get('path', '')
        
        if not file_path:
            return JsonResponse({
                'success': False,
                'error': '文件路径不能为空'
            })
        
        success, message = model_file_manager.delete_file(file_path, username)
        
        return JsonResponse({
            'success': success,
            'message': message
        })


@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class CreateFileAPIView(View):
    """
    创建新文件API视图
    """
    
    def post(self, request):
        """
        创建新文件
        """
        try:
            data = json.loads(request.body)
            parent_path = data.get('parent_path', '')
            file_name = data.get('file_name', '')
            file_content = data.get('content', '')
            
            if not file_name:
                return JsonResponse({
                    'success': False,
                    'error': '文件名不能为空'
                })
            
            # 构建完整路径
            if parent_path:
                full_path = f"{parent_path}/{file_name}"
            else:
                full_path = file_name
            
            success, message = model_file_manager.save_file_content(
                full_path, file_content, request.user.username
            )
            
            return JsonResponse({
                'success': success,
                'message': message,
                'path': full_path
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': '请求数据格式错误'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f"创建文件失败: {str(e)}"
            })


# 简化的函数视图（用于URL配置）
@login_required
@require_http_methods(["GET"])
def get_model_tree(request):
    """获取模型文件树"""
    view = ModelTreeAPIView()
    return view.get(request)


@login_required
@csrf_exempt
@require_http_methods(["GET", "POST"])
def file_content_api(request):
    """文件内容API"""
    view = FileContentAPIView()
    if request.method == 'GET':
        return view.get(request)
    elif request.method == 'POST':
        return view.post(request)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def file_operation_api(request):
    """文件操作API"""
    view = FileOperationAPIView()
    return view.post(request)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def create_file_api(request):
    """创建文件API"""
    view = CreateFileAPIView()
    return view.post(request)


# ========== 参数配置相关API ==========

@method_decorator(login_required, name='dispatch')
class SettingTreeAPIView(View):
    """
    参数配置文件树API视图
    """
    
    def get(self, request):
        """
        获取参数配置文件树结构
        """
        try:
            username = request.user.username
            
            # 确保用户文件夹存在
            user_path = setting_file_manager.ensure_user_folder(username)
            
            # 获取default文件夹树
            default_tree = setting_file_manager.get_directory_tree(setting_file_manager.default_path)
            
            # 获取用户文件夹树
            user_tree = setting_file_manager.get_directory_tree(user_path)
            
            return JsonResponse({
                'success': True,
                'data': {
                    'default': default_tree,
                    'user': user_tree,
                    'username': username
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'获取文件树失败: {str(e)}'
            })


@method_decorator(login_required, name='dispatch')
class SettingFileContentAPIView(View):
    """
    参数配置文件内容API视图
    """
    
    def get(self, request):
        """
        获取文件内容
        """
        try:
            file_path = request.GET.get('path')
            if not file_path:
                return JsonResponse({
                    'success': False,
                    'error': '缺少文件路径参数'
                })
            
            content = setting_file_manager.get_file_content(file_path)
            
            return JsonResponse({
                'success': True,
                'data': {
                    'path': file_path,
                    'content': content
                }
            })
            
        except FileNotFoundError:
            return JsonResponse({
                'success': False,
                'error': '文件不存在'
            })
        except PermissionError:
            return JsonResponse({
                'success': False,
                'error': '没有权限访问此文件'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'读取文件失败: {str(e)}'
            })
    
    def post(self, request):
        """
        保存文件内容
        """
        try:
            data = json.loads(request.body)
            file_path = data.get('path')
            content = data.get('content', '')
            
            if not file_path:
                return JsonResponse({
                    'success': False,
                    'message': '缺少文件路径参数'
                })
            
            success = setting_file_manager.save_file_content(file_path, content, request.user.username)
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': '文件保存成功'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': '文件保存失败'
                })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': '无效的JSON数据'
            })
        except PermissionError:
            return JsonResponse({
                'success': False,
                'message': '没有权限修改此文件'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'保存文件失败: {str(e)}'
            })


@method_decorator(login_required, name='dispatch')
class SettingCreateFileAPIView(View):
    """
    创建参数配置文件API视图
    """
    
    def post(self, request):
        """
        创建新文件
        """
        try:
            data = json.loads(request.body)
            parent_path = data.get('parent_path', '')
            file_name = data.get('file_name')
            content = data.get('content', '')
            
            if not file_name:
                return JsonResponse({
                    'success': False,
                    'message': '缺少文件名'
                })
            
            file_path = setting_file_manager.create_file(parent_path, file_name, content, request.user.username)
            
            return JsonResponse({
                'success': True,
                'message': '文件创建成功',
                'path': file_path
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': '无效的JSON数据'
            })
        except FileExistsError:
            return JsonResponse({
                'success': False,
                'message': '文件已存在'
            })
        except PermissionError:
            return JsonResponse({
                'success': False,
                'message': '没有权限在此位置创建文件'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'创建文件失败: {str(e)}'
            })


@method_decorator(login_required, name='dispatch')
class SettingOperationAPIView(View):
    """
    参数配置文件操作API视图
    """
    
    def post(self, request):
        """
        文件操作（删除、创建文件夹等）
        """
        try:
            data = json.loads(request.body)
            operation = data.get('operation')
            
            if operation == 'delete':
                file_path = data.get('path')
                if not file_path:
                    return JsonResponse({
                        'success': False,
                        'message': '缺少文件路径'
                    })
                
                success = setting_file_manager.delete_file_or_folder(file_path, request.user.username)
                
                if success:
                    return JsonResponse({
                        'success': True,
                        'message': '删除成功'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': '删除失败'
                    })
            
            elif operation == 'create_folder':
                parent_path = data.get('parent_path', '')
                folder_name = data.get('folder_name')
                
                if not folder_name:
                    return JsonResponse({
                        'success': False,
                        'message': '缺少文件夹名称'
                    })
                
                folder_path = setting_file_manager.create_folder(parent_path, folder_name, request.user.username)
                
                return JsonResponse({
                    'success': True,
                    'message': '文件夹创建成功',
                    'path': folder_path
                })
            
            else:
                return JsonResponse({
                    'success': False,
                    'message': '不支持的操作'
                })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': '无效的JSON数据'
            })
        except (FileNotFoundError, FileExistsError, PermissionError) as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'操作失败: {str(e)}'
            })


@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class ModelTestAPIView(View):
    """
    模型测试API视图 - 运行模型测试脚本
    """
    
    def post(self, request):
        """
        执行模型测试
        """
        try:
            data = json.loads(request.body)
            model_path = data.get('model_path')
            
            if not model_path:
                return JsonResponse({
                    'success': False,
                    'message': '缺少模型文件路径参数'
                })
            
            # 验证文件是否为YAML格式
            if not model_path.endswith(('.yaml', '.yml')):
                return JsonResponse({
                    'success': False,
                    'message': '只能测试YAML格式的模型配置文件'
                })
            
            # 将相对路径转换为绝对路径
            if not os.path.isabs(model_path):
                # model_path是相对于模型配置目录的路径，需要转换为绝对路径
                absolute_model_path = str(model_file_manager.base_path / model_path)
            else:
                absolute_model_path = model_path
            
            # 验证文件是否存在
            if not os.path.exists(absolute_model_path):
                return JsonResponse({
                    'success': False,
                    'message': f'模型文件不存在: {absolute_model_path}'
                })
            
            # 获取EOLO目录路径（使用配置化路径）
            eolo_path = settings.EOLO_DIR
            
            # 验证测试脚本是否存在
            test_script_path = settings.EOLO_MODEL_TEST_SCRIPT
            if not test_script_path.exists():
                return JsonResponse({
                    'success': False,
                    'message': f'测试脚本不存在: {test_script_path}'
                })
            
            # 构建命令（使用配置化参数）
            command_parts = ['uv', 'run']
            
            # 如果配置了安静模式，添加--quiet参数
            if settings.MODEL_TEST_CONFIG.get('QUIET_MODE', True):
                command_parts.append('--quiet')
            
            # 添加脚本和参数
            command_parts.extend([
                str(settings.EOLO_MODEL_TEST_SCRIPT),
                absolute_model_path,
                '--device',
                settings.MODEL_TEST_CONFIG.get('DEFAULT_DEVICE', 'cpu')
            ])
            
            try:
                # 执行测试命令
                timeout = settings.MODEL_TEST_CONFIG.get('TIMEOUT', 60)
                result = subprocess.run(
                    command_parts,
                    cwd=str(eolo_path),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=os.environ.copy()
                )
                
                # 组合输出信息
                output_lines = []
                output_lines.append(f"执行命令: {' '.join(command_parts)}")
                output_lines.append(f"工作目录: {eolo_path}")
                output_lines.append(f"返回码: {result.returncode}")
                output_lines.append("=" * 50)
                
                if result.stdout:
                    output_lines.append("标准输出:")
                    output_lines.append(result.stdout)
                
                if result.stderr:
                    output_lines.append("错误输出:")
                    output_lines.append(result.stderr)
                
                # 判断执行是否成功
                success = result.returncode == 0
                
                return JsonResponse({
                    'success': True,
                    'test_success': success,
                    'output': '\n'.join(output_lines),
                    'return_code': result.returncode
                })
                
            except subprocess.TimeoutExpired:
                return JsonResponse({
                    'success': False,
                    'message': f'模型测试超时（超过{timeout}秒），请检查模型配置是否正确'
                })
            except subprocess.CalledProcessError as e:
                return JsonResponse({
                    'success': True,
                    'test_success': False,
                    'output': f"命令执行失败:\n返回码: {e.returncode}\n输出: {e.output}\n错误: {e.stderr}",
                    'return_code': e.returncode
                })
            except FileNotFoundError:
                return JsonResponse({
                    'success': False,
                    'message': '找不到uv命令，请确保uv已正确安装'
                })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': '无效的JSON请求数据'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'测试执行失败: {str(e)}'
            })
