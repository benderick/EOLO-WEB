"""
模块管理视图
"""
import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from .file_manager import module_file_manager
from .models import ModuleFile, ModuleEditSession


@login_required
def modules_list_view(request):
    """
    模块列表页面 - 显示文件树
    """
    try:
        # 获取文件树结构
        file_tree = module_file_manager.build_file_tree()
        
        # 获取目录结构（用于上传）
        directories = module_file_manager.get_directory_structure()
        
        # 统计信息
        all_files = module_file_manager.scan_python_files()
        stats = {
            'total_files': len(all_files),
            'total_size': sum(f['size'] for f in all_files),
            'total_directories': len(directories),
        }
        
        context = {
            'file_tree': file_tree,
            'directories': directories,
            'stats': stats,
            'workpieces_dir': str(module_file_manager.workpieces_dir),
        }
        
        return render(request, 'modules/modules_list.html', context)
        
    except Exception as e:
        messages.error(request, f"加载模块列表失败: {str(e)}")
        return render(request, 'modules/modules_list.html', {
            'file_tree': {},
            'directories': [],
            'stats': {'total_files': 0, 'total_size': 0, 'total_directories': 0}
        })


@login_required
def module_file_view(request, path):
    """
    查看和编辑单个模块文件
    """
    try:
        # 解码路径
        relative_path = path.replace('__', '/')
        
        # 获取文件内容
        success, content = module_file_manager.get_file_content(relative_path)
        
        if not success:
            messages.error(request, content)
            return redirect('modules:list')
        
        # 检查是否有其他用户正在编辑
        active_sessions = ModuleEditSession.objects.filter(
            module_file__relative_path=relative_path,
            is_active=True
        ).exclude(user=request.user)
        
        # 获取或创建模块文件记录（但不创建编辑会话）
        module_file, created = ModuleFile.objects.get_or_create(
            relative_path=relative_path,
            defaults={
                'name': relative_path.split('/')[-1],
                'size': len(content.encode('utf-8')),
                'uploaded_by': request.user,
            }
        )
        
        # 检查当前用户是否有活跃的编辑会话
        current_user_session = ModuleEditSession.objects.filter(
            module_file=module_file,
            user=request.user,
            is_active=True
        ).first()
        
        context = {
            'file_path': relative_path,
            'file_name': relative_path.split('/')[-1],
            'file_content': content,
            'file_size': len(content.encode('utf-8')),
            'active_sessions': active_sessions,
            'can_edit': len(active_sessions) == 0,  # 只有没有其他人编辑时才能编辑
            'is_editing': current_user_session is not None,  # 当前用户是否正在编辑
        }
        
        return render(request, 'modules/module_file_editor.html', context)
        
    except Exception as e:
        messages.error(request, f"打开文件失败: {str(e)}")
        return redirect('modules:list')


@login_required
@require_POST
def save_module_file(request):
    """
    保存模块文件内容
    """
    try:
        data = json.loads(request.body)
        relative_path = data.get('path')
        content = data.get('content')
        
        if not relative_path or content is None:
            return JsonResponse({'success': False, 'error': '参数不完整'})
        
        # 检查编辑权限
        active_sessions = ModuleEditSession.objects.filter(
            module_file__relative_path=relative_path,
            is_active=True
        ).exclude(user=request.user)
        
        if active_sessions.exists():
            return JsonResponse({
                'success': False, 
                'error': '文件正在被其他用户编辑，无法保存'
            })
        
        # 保存文件
        success, message = module_file_manager.save_file_content(
            relative_path, content, request.user
        )
        
        if success:
            # 保存成功后关闭编辑会话（自动退出编辑模式）
            try:
                module_file = ModuleFile.objects.get(relative_path=relative_path)
                ModuleEditSession.objects.filter(
                    module_file=module_file,
                    user=request.user
                ).update(is_active=False, last_activity=timezone.now())
            except:
                pass
        
        return JsonResponse({
            'success': success,
            'message': message,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'保存失败: {str(e)}'
        })


@login_required
@require_POST
def upload_module_file(request):
    """
    上传模块文件
    """
    try:
        uploaded_file = request.FILES.get('file')
        target_directory = request.POST.get('directory', '.')
        
        if not uploaded_file:
            return JsonResponse({'success': False, 'error': '没有选择文件'})
        
        # 检查文件扩展名
        if not uploaded_file.name.endswith('.py'):
            return JsonResponse({'success': False, 'error': '只能上传Python文件(.py)'})
        
        # 忽略__init__.py文件
        if uploaded_file.name == '__init__.py':
            return JsonResponse({'success': False, 'error': '不允许上传__init__.py文件'})
        
        # 构建目标路径
        if target_directory == '.':
            relative_path = uploaded_file.name
        else:
            relative_path = f"{target_directory}/{uploaded_file.name}"
        
        # 检查目标路径是否包含__pycache__目录
        if '__pycache__' in relative_path:
            return JsonResponse({'success': False, 'error': '不能上传到__pycache__目录'})
        
        # 读取文件内容
        file_data = uploaded_file.read()
        
        # 上传文件
        success, message = module_file_manager.upload_file(
            file_data, relative_path, request.user
        )
        
        return JsonResponse({
            'success': success,
            'message': message,
            'file_path': relative_path if success else None
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'上传失败: {str(e)}'
        })


@login_required
@require_POST
def delete_module_file(request):
    """
    删除模块文件
    """
    try:
        data = json.loads(request.body)
        relative_path = data.get('path')
        
        if not relative_path:
            return JsonResponse({'success': False, 'error': '路径参数缺失'})
        
        # 检查是否有人正在编辑
        active_sessions = ModuleEditSession.objects.filter(
            module_file__relative_path=relative_path,
            is_active=True
        )
        
        if active_sessions.exists():
            return JsonResponse({
                'success': False,
                'error': '文件正在被编辑，无法删除'
            })
        
        # 删除文件
        success, message = module_file_manager.delete_file(relative_path, request.user)
        
        return JsonResponse({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'删除失败: {str(e)}'
        })


@login_required
def module_file_tree_api(request):
    """
    获取文件树API（用于AJAX刷新）
    """
    try:
        file_tree = module_file_manager.build_file_tree()
        all_files = module_file_manager.scan_python_files()
        
        return JsonResponse({
            'success': True,
            'file_tree': file_tree,
            'stats': {
                'total_files': len(all_files),
                'total_size': sum(f['size'] for f in all_files),
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_POST
def close_edit_session(request):
    """
    关闭编辑会话
    """
    try:
        data = json.loads(request.body)
        relative_path = data.get('path')
        
        if relative_path:
            ModuleEditSession.objects.filter(
                module_file__relative_path=relative_path,
                user=request.user
            ).update(is_active=False)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@csrf_exempt
@require_POST
def enter_edit_mode(request):
    """
    进入编辑模式
    """
    try:
        data = json.loads(request.body)
        file_path = data.get('file_path')
        
        if not file_path:
            return JsonResponse({
                'success': False,
                'error': '缺少文件路径参数'
            })
        
        # 检查是否有其他用户正在编辑
        active_sessions = ModuleEditSession.objects.filter(
            module_file__relative_path=file_path,
            is_active=True
        ).exclude(user=request.user)
        
        if active_sessions.exists():
            # 获取其他编辑用户信息
            other_users = []
            for session in active_sessions:
                time_diff = timezone.now() - session.last_activity
                minutes_ago = int(time_diff.total_seconds() / 60)
                other_users.append({
                    'username': session.user.username,
                    'minutes_ago': minutes_ago
                })
            
            return JsonResponse({
                'success': False,
                'error': 'editing_conflict',
                'other_users': other_users
            })
        
        # 获取或创建模块文件记录
        module_file, created = ModuleFile.objects.get_or_create(
            relative_path=file_path,
            defaults={
                'name': file_path.split('/')[-1],
                'size': 0,  # 这里可以根据需要获取实际大小
                'uploaded_by': request.user,
            }
        )
        
        # 创建或激活编辑会话
        edit_session, session_created = ModuleEditSession.objects.get_or_create(
            module_file=module_file,
            user=request.user,
            defaults={'is_active': True}
        )
        
        if not session_created:
            edit_session.last_activity = timezone.now()
            edit_session.is_active = True
            edit_session.save()
        
        return JsonResponse({
            'success': True,
            'message': '已进入编辑模式'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': '请求数据格式错误'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'进入编辑模式失败: {str(e)}'
        })


@login_required
@csrf_exempt
@require_POST
def test_python_file(request):
    """
    测试运行Python文件
    """
    import subprocess
    import os
    from pathlib import Path
    from django.conf import settings
    
    try:
        data = json.loads(request.body)
        file_path = data.get('file_path')
        
        if not file_path:
            return JsonResponse({
                'success': False,
                'error': '缺少文件路径参数'
            })
        
        # 获取绝对路径
        absolute_path = module_file_manager.workpieces_dir / file_path
        
        # 检查文件是否存在且是Python文件
        if not absolute_path.exists():
            return JsonResponse({
                'success': False,
                'error': f'文件不存在: {file_path}'
            })
        
        if not absolute_path.suffix == '.py':
            return JsonResponse({
                'success': False,
                'error': '只能测试Python文件(.py)'
            })
        
        # 构建执行命令
        eolo_dir = Path(settings.BASE_DIR).parent / 'EOLO'
        command = f'cd "{eolo_dir}" && uv run --quiet "{absolute_path}"'
        
        try:
            # 执行命令
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,  # 30秒超时
                cwd=str(eolo_dir)
            )
            
            # 合并stdout和stderr
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                if output:
                    output += "\n--- 错误输出 ---\n"
                output += result.stderr
            
            if not output.strip():
                output = "(无输出)"
            
            return JsonResponse({
                'success': True,
                'output': output,
                'exit_code': result.returncode,
                'command': command
            })
            
        except subprocess.TimeoutExpired:
            return JsonResponse({
                'success': False,
                'error': '执行超时（超过30秒）'
            })
        except subprocess.CalledProcessError as e:
            return JsonResponse({
                'success': False,
                'error': f'命令执行失败: {e.stderr or str(e)}'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'执行过程中发生错误: {str(e)}'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': '请求数据格式错误'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'处理请求时发生错误: {str(e)}'
        })
