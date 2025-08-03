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
        
        # 创建或更新编辑会话
        module_file, created = ModuleFile.objects.get_or_create(
            relative_path=relative_path,
            defaults={
                'name': relative_path.split('/')[-1],
                'size': len(content.encode('utf-8')),
                'uploaded_by': request.user,
            }
        )
        
        edit_session, session_created = ModuleEditSession.objects.get_or_create(
            module_file=module_file,
            user=request.user,
            defaults={'is_active': True}
        )
        
        if not session_created:
            edit_session.last_activity = timezone.now()
            edit_session.is_active = True
            edit_session.save()
        
        context = {
            'file_path': relative_path,
            'file_name': relative_path.split('/')[-1],
            'file_content': content,
            'file_size': len(content.encode('utf-8')),
            'active_sessions': active_sessions,
            'can_edit': len(active_sessions) == 0,  # 只有没有其他人编辑时才能编辑
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
            # 更新编辑会话
            try:
                module_file = ModuleFile.objects.get(relative_path=relative_path)
                ModuleEditSession.objects.filter(
                    module_file=module_file,
                    user=request.user
                ).update(last_activity=timezone.now())
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
