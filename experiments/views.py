from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from .models import Experiment, ExperimentLog
from .forms import ExperimentForm
from .gpu_utils import check_gpu_availability
from .process_manager import process_manager
import json


@login_required
def dashboard_view(request):
    """
    实验管理仪表板
    """
    # 获取用户的实验统计信息
    user_experiments = Experiment.objects.filter(user=request.user)
    total_experiments = user_experiments.count()
    running_experiments = user_experiments.filter(status='running').count()
    completed_experiments = user_experiments.filter(status='completed').count()
    interrupted_experiments = user_experiments.filter(status='interrupted').count()
    failed_experiments = user_experiments.filter(status='error').count()
    
    # 获取最近的实验
    recent_experiments = user_experiments[:5]
    
    context = {
        'total_experiments': total_experiments,
        'running_experiments': running_experiments,
        'completed_experiments': completed_experiments,
        'interrupted_experiments': interrupted_experiments,
        'failed_experiments': failed_experiments,
        'recent_experiments': recent_experiments,
    }
    
    return render(request, 'experiments/dashboard.html', context)


@login_required
def experiment_list_view(request):
    """
    实验列表视图
    """
    experiments = Experiment.objects.filter(user=request.user)
    
    # 状态过滤
    status_filter = request.GET.get('status')
    if status_filter:
        experiments = experiments.filter(status=status_filter)
    
    # 分页
    paginator = Paginator(experiments, 10)  # 每页显示10个实验
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
    }
    
    return render(request, 'experiments/experiment_list.html', context)


@login_required
def experiment_create_view(request):
    """
    创建实验视图
    """
    # 从查询参数获取预填充的数据集名称
    dataset_name = request.GET.get('dataset')
    
    if request.method == 'POST':
        form = ExperimentForm(request.POST, user=request.user)
        if form.is_valid():
            experiment = form.save(commit=False)
            experiment.user = request.user
            experiment.task_type = 'detect'  # 固定为目标检测
            experiment.project_name = request.user.username  # 固定为用户名
            
            # 设置固定的默认值
            experiment.image_size = 640  # 固定图像大小为640
            experiment.workers = 8      # 固定工作进程数为8
            
            experiment.generate_command()  # 生成命令
            experiment.save()
            messages.success(request, f'实验 "{experiment.name}" 创建成功！')
            return redirect('experiments:detail', pk=experiment.pk)
    else:
        # 如果有数据集参数，预填充表单
        initial_data = {}
        if dataset_name:
            initial_data['dataset'] = dataset_name
            messages.info(request, f'已预选数据集: {dataset_name}')
        
        form = ExperimentForm(initial=initial_data, user=request.user)
    
    return render(request, 'experiments/experiment_form.html', {'form': form, 'title': '创建新实验'})


@login_required
def experiment_detail_view(request, pk):
    """
    实验详情视图
    """
    experiment = get_object_or_404(Experiment, pk=pk, user=request.user)
    logs = experiment.logs.all().order_by('timestamp')  # 正序：最早的在上面，最新的在下面
    
    # 获取配置参数传递给模板
    api_config = getattr(settings, 'EXPERIMENT_API_CONFIG', {})
    
    context = {
        'experiment': experiment,
        'logs': logs,
        'api_config': api_config,
    }
    
    return render(request, 'experiments/experiment_detail.html', context)


@login_required
def experiment_edit_view(request, pk):
    """
    编辑实验视图
    """
    experiment = get_object_or_404(Experiment, pk=pk, user=request.user)
    
    # 只有未开始的实验才能编辑
    if experiment.status not in ['pending']:
        messages.error(request, '只有等待中的实验才能编辑！')
        return redirect('experiments:detail', pk=pk)
    
    if request.method == 'POST':
        form = ExperimentForm(request.POST, instance=experiment)
        if form.is_valid():
            experiment = form.save()
            experiment.generate_command()  # 重新生成命令
            experiment.save()
            messages.success(request, f'实验 "{experiment.name}" 更新成功！')
            return redirect('experiments:detail', pk=experiment.pk)
    else:
        form = ExperimentForm(instance=experiment)
    
    return render(request, 'experiments/experiment_form.html', {
        'form': form, 
        'title': f'编辑实验 - {experiment.name}',
        'experiment': experiment
    })


@login_required
@require_POST
def experiment_start_view(request, pk):
    """
    启动实验
    """
    experiment = get_object_or_404(Experiment, pk=pk, user=request.user)
    
    if experiment.status not in ['pending', 'queued']:
        messages.error(request, '只有等待中或排队中的实验才能启动！')
        return redirect('experiments:detail', pk=pk)
    
    # 检查是否强制启动
    force_start = request.POST.get('force_start') == 'true'
    
    if not force_start:
        # 检查GPU可用性
        gpu_check = check_gpu_availability(experiment.device, memory_threshold=20.0)
        
        if not gpu_check['available']:
            # GPU繁忙，显示确认页面
            context = {
                'experiment': experiment,
                'gpu_check': gpu_check,
                'gpu_indices': gpu_check['gpu_indices'],
                'busy_gpus': gpu_check['busy_gpus'],
                'gpu_status': gpu_check['gpu_status']
            }
            return render(request, 'experiments/gpu_conflict.html', context)
    
    # 使用进程管理器启动实验
    success, message = process_manager.start_experiment(experiment.id, force_start=force_start)
    
    if success:
        if force_start:
            messages.warning(request, f'实验 "{experiment.name}" 已强制启动！请注意GPU使用情况。')
        else:
            messages.success(request, f'实验 "{experiment.name}" 已启动！')
    else:
        if "排队" in message:
            messages.warning(request, f'GPU繁忙，实验 "{experiment.name}" 已加入排队！')
        else:
            messages.error(request, f'启动失败: {message}')
    
    return redirect('experiments:detail', pk=pk)


@login_required
@require_POST
def experiment_stop_view(request, pk):
    """
    停止实验
    """
    experiment = get_object_or_404(Experiment, pk=pk, user=request.user)
    
    if experiment.status != 'running':
        messages.error(request, '只有运行中的实验才能停止！')
    else:
        # 使用进程管理器停止实验
        success, message = process_manager.stop_experiment(experiment.id, user_initiated=True)
        
        if success:
            messages.success(request, f'实验 "{experiment.name}" 已停止！')
        else:
            messages.error(request, f'停止实验失败: {message}')
    
    return redirect('experiments:detail', pk=pk)


@login_required
def experiment_delete_view(request, pk):
    """
    删除实验
    """
    experiment = get_object_or_404(Experiment, pk=pk, user=request.user)
    
    if request.method == 'POST':
        experiment_name = experiment.name
        experiment.delete()
        messages.success(request, f'实验 "{experiment_name}" 已删除！')
        return redirect('experiments:list')
    
    return render(request, 'experiments/experiment_confirm_delete.html', {'experiment': experiment})


@login_required
def experiment_restart_view(request, pk):
    """
    重启实验视图
    """
    experiment = get_object_or_404(Experiment, pk=pk, user=request.user)
    
    if request.method == 'POST':
        if experiment.status in ['error', 'completed', 'interrupted']:
            # 重置实验状态
            experiment.status = 'pending'
            experiment.started_at = None
            experiment.completed_at = None
            experiment.error_message = None
            experiment.save()
            
            messages.success(request, f'实验 "{experiment.name}" 已重置为待启动状态！')
        else:
            messages.warning(request, '只有错误、完成或中断的实验可以重启！')
        
        return redirect('experiments:detail', pk=experiment.pk)
    
    return redirect('experiments:detail', pk=experiment.pk)


@login_required
def get_experiment_command(request, pk):
    """
    获取实验命令的API接口
    """
    experiment = get_object_or_404(Experiment, pk=pk, user=request.user)
    command = experiment.generate_command()
    
    return JsonResponse({
        'command': command,
        'status': experiment.status
    })


@login_required
def gpu_status_view(request):
    """
    查看GPU状态（用于调试）
    """
    from .gpu_utils import check_gpu_memory_usage
    
    gpu_info = check_gpu_memory_usage()
    
    context = {
        'gpu_info': gpu_info,
        'title': 'GPU状态监控'
    }
    
    return render(request, 'experiments/gpu_status.html', context)


@login_required
def gpu_status_json_view(request):
    """
    返回GPU状态的JSON数据（用于AJAX刷新）
    """
    from .gpu_utils import check_gpu_memory_usage
    
    try:
        gpu_status = check_gpu_memory_usage()
        
        # 格式化返回数据
        formatted_status = {}
        for gpu_id, info in gpu_status.items():
            memory_percent = info.get('memory_used_percent', 0)
            formatted_status[str(gpu_id)] = {
                'memory_percent': round(memory_percent, 1),
                'memory_used': round(info.get('memory_used', 0) / 1024, 1),
                'memory_total': round(info.get('memory_total', 0) / 1024, 1),
                'is_available': memory_percent < 20,
                'status': 'available' if memory_percent < 20 else 'busy' if memory_percent >= 50 else 'in_use'
            }
        
        return JsonResponse({
            'success': True,
            'gpu_status': formatted_status,
            'timestamp': timezone.now().isoformat()
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        })


@login_required
def experiment_status_api(request, pk):
    """
    获取实验的实时状态API
    """
    try:
        experiment = get_object_or_404(Experiment, pk=pk, user=request.user)
        
        # 定期执行轻量级健康检查（从配置获取间隔）
        import time
        api_config = getattr(settings, 'EXPERIMENT_API_CONFIG', {})
        health_check_interval = api_config.get('HEALTH_CHECK_INTERVAL', 60)
        
        current_time = time.time()
        if not hasattr(experiment_status_api, '_last_health_check') or \
           current_time - experiment_status_api._last_health_check > health_check_interval:
            # 只检查当前实验的进程状态
            try:
                if experiment.status == 'running' and experiment.id not in process_manager.running_processes:
                    # 发现孤儿实验，立即修复
                    experiment.fail_experiment("进程监控丢失")
                    process_manager._log_to_experiment(experiment, 'ERROR', "检测到进程监控丢失，状态已修复")
            except Exception:
                pass  # 健康检查失败不影响主要功能
            experiment_status_api._last_health_check = current_time
        
        # 获取进程状态
        process_status = process_manager.get_experiment_status(experiment.id)
        
        # 获取最新日志（从配置获取条数）
        log_config = getattr(settings, 'EXPERIMENT_LOG_CONFIG', {})
        recent_logs_count = log_config.get('RECENT_LOGS_COUNT', 10)
        
        recent_logs = list(experiment.logs.order_by('-timestamp')[:recent_logs_count].values(
            'id', 'timestamp', 'level', 'message'
        ))
        
        # 格式化时间戳
        for log in recent_logs:
            log['timestamp'] = log['timestamp'].isoformat()
        
        return JsonResponse({
            'success': True,
            'experiment': {
                'id': experiment.id,
                'name': experiment.name,
                'status': experiment.status,
                'started_at': experiment.started_at.isoformat() if experiment.started_at else None,
                'completed_at': experiment.completed_at.isoformat() if experiment.completed_at else None,
                'command': experiment.command,
                'error_message': experiment.error_message
            },
            'process_status': process_status,
            'recent_logs': recent_logs,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        })


@login_required
def experiment_logs_api(request, pk):
    """
    获取实验日志API（支持分页）
    """
    try:
        experiment = get_object_or_404(Experiment, pk=pk, user=request.user)
        
        # 获取查询参数
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 50))
        since_id = request.GET.get('since_id')  # 获取指定ID之后的日志
        
        # 构建查询
        logs_query = experiment.logs.all()
        
        if since_id:
            try:
                logs_query = logs_query.filter(id__gt=int(since_id))
            except ValueError:
                pass
        
        # 分页（按时间正序，最早的在前面）
        total_count = logs_query.count()
        start = (page - 1) * per_page
        end = start + per_page
        logs = list(logs_query.order_by('timestamp')[start:end].values(
            'id', 'timestamp', 'level', 'message'
        ))
        
        # 格式化时间戳
        for log in logs:
            log['timestamp'] = log['timestamp'].isoformat()
        
        return JsonResponse({
            'success': True,
            'logs': logs,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'has_next': end < total_count
            },
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        })


@login_required
def running_experiments_api(request):
    """
    获取所有正在运行的实验API
    """
    try:
        # 获取用户的运行中实验
        running_experiments = Experiment.objects.filter(
            user=request.user,
            status='running'
        ).values('id', 'name', 'started_at', 'command')
        
        # 获取进程状态
        experiments_with_status = []
        for exp in running_experiments:
            process_status = process_manager.get_experiment_status(exp['id'])
            exp['process_status'] = process_status
            exp['started_at'] = exp['started_at'].isoformat() if exp['started_at'] else None
            experiments_with_status.append(exp)
        
        return JsonResponse({
            'success': True,
            'running_experiments': experiments_with_status,
            'count': len(experiments_with_status),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        })


@login_required
@require_POST
def experiment_queue_view(request, pk):
    """
    将实验加入队列
    """
    try:
        experiment = get_object_or_404(Experiment, pk=pk, user=request.user)
        
        # 检查实验状态
        if experiment.status not in ['pending', 'error', 'interrupted']:
            return JsonResponse({
                'success': False,
                'error': f'实验状态不允许加入队列: {experiment.status}',
                'timestamp': timezone.now().isoformat()
            })
        
        # 加入队列
        from .queue_scheduler import gpu_scheduler
        success, message = gpu_scheduler.add_to_queue(experiment.id)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': message,
                'experiment': {
                    'id': experiment.id,
                    'status': experiment.status
                },
                'timestamp': timezone.now().isoformat()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message,
                'timestamp': timezone.now().isoformat()
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        })


@login_required
def queue_status_api(request):
    """
    获取队列状态API
    """
    try:
        from .queue_scheduler import gpu_scheduler
        status = gpu_scheduler.get_queue_status()
        
        # 只返回用户自己的实验
        filtered_device_groups = {}
        for device, info in status.get('device_groups', {}).items():
            user_experiments = [
                exp for exp in info['experiments'] 
                if exp.get('user') == request.user.username
            ]
            if user_experiments:
                filtered_device_groups[device] = {
                    'count': len(user_experiments),
                    'experiments': user_experiments
                }
        
        return JsonResponse({
            'success': True,
            'scheduler_running': status['scheduler_running'],
            'check_interval': status['check_interval'],
            'user_queued_count': sum(info['count'] for info in filtered_device_groups.values()),
            'total_queued': status['total_queued'],
            'device_groups': filtered_device_groups,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        })
