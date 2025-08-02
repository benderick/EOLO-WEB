from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404, HttpResponse
from django.core.paginator import Paginator
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import DatasetManager
import json


@login_required
def dataset_list_view(request):
    """
    数据集列表视图
    """
    manager = DatasetManager()
    
    # 获取搜索查询
    search_query = request.GET.get('search', '').strip()
    
    # 获取数据集
    if search_query:
        datasets = manager.search_datasets(search_query)
    else:
        datasets = manager.get_all_datasets()
    
    # 统计信息
    total_datasets = len(datasets)
    valid_datasets = len([d for d in datasets if d.is_valid])
    invalid_datasets = total_datasets - valid_datasets
    
    # 分页
    paginator = Paginator(datasets, 12)  # 每页显示12个数据集
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'total_datasets': total_datasets,
        'valid_datasets': valid_datasets,
        'invalid_datasets': invalid_datasets,
    }
    
    return render(request, 'datasets/dataset_list.html', context)


@login_required
def dataset_detail_view(request, name):
    """
    数据集详情视图
    """
    try:
        print(f"[DEBUG] 正在获取数据集: {name}")
        manager = DatasetManager()
        dataset = manager.get_dataset_by_name(name)
        
        if not dataset:
            print(f"[DEBUG] 数据集 {name} 不存在")
            raise Http404("数据集不存在")
        
        print(f"[DEBUG] 数据集 {name} 获取成功，路径: {dataset.file_path}")
        
        # 获取要显示的YAML内容
        yaml_content = dataset.yaml_content
        print(f"[DEBUG] YAML内容读取成功，长度: {len(yaml_content)}")
        
        context = {
            'dataset': dataset,
            'yaml_content': yaml_content,
        }
        
        print(f"[DEBUG] 准备渲染模板，context keys: {list(context.keys())}")
        return render(request, 'datasets/dataset_detail.html', context)
        
    except Exception as e:
        print(f"[DEBUG] 视图异常: {e}")
        import traceback
        traceback.print_exc()
        raise


@login_required
def dataset_api_view(request, name):
    """
    数据集API接口 - 返回JSON格式的数据集信息
    """
    manager = DatasetManager()
    dataset = manager.get_dataset_by_name(name)
    
    if not dataset:
        return JsonResponse({'error': '数据集不存在'}, status=404)
    
    return JsonResponse(dataset.to_dict())


@login_required
def dataset_search_api(request):
    """
    数据集搜索API
    """
    query = request.GET.get('q', '').strip()
    manager = DatasetManager()
    
    datasets = manager.search_datasets(query)
    
    # 转换为简化的字典格式
    results = []
    for dataset in datasets[:10]:  # 限制返回10个结果
        results.append({
            'name': dataset.name,
            'filename': dataset.filename,
            'nc': dataset.nc,
            'description': dataset.description,
            'is_valid': dataset.is_valid
        })
    
    return JsonResponse({'results': results})


@login_required
def dataset_stats_view(request):
    """
    数据集统计页面
    """
    manager = DatasetManager()
    datasets = manager.get_all_datasets()
    
    # 统计信息
    stats = {
        'total': len(datasets),
        'valid': len([d for d in datasets if d.is_valid]),
        'invalid': len([d for d in datasets if not d.is_valid]),
        'by_class_count': {},
        'recent_datasets': []
    }
    
    # 按类别数量分组统计
    for dataset in datasets:
        if dataset.is_valid:
            nc = dataset.nc
            if nc in stats['by_class_count']:
                stats['by_class_count'][nc] += 1
            else:
                stats['by_class_count'][nc] = 1
    
    # 最近修改的数据集
    valid_datasets = [d for d in datasets if d.is_valid and d.modified_time]
    valid_datasets.sort(key=lambda x: x.modified_time, reverse=True)
    stats['recent_datasets'] = valid_datasets[:5]
    
    context = {'stats': stats}
    return render(request, 'datasets/dataset_stats.html', context)


@login_required
def dataset_info_api(request, name):
    """
    获取数据集基本信息API（用于检查文件更新）
    """
    manager = DatasetManager()
    dataset = manager.get_dataset_by_name(name)
    
    if not dataset:
        return JsonResponse({'error': '数据集不存在'}, status=404)
    
    info = {
        'name': dataset.name,
        'filename': dataset.filename,
        'size': dataset.size,
        'modified_time': dataset.modified_time.isoformat() if dataset.modified_time else None,
        'is_valid': dataset.is_valid,
    }
    
    return JsonResponse(info)


@login_required
@require_POST
def dataset_validate_api(request, name):
    """
    验证数据集配置API
    """
    manager = DatasetManager()
    dataset = manager.get_dataset_by_name(name)
    
    if not dataset:
        return JsonResponse({'error': '数据集不存在'}, status=404)
    
    # 执行验证
    validation_result = dataset.validate_paths()
    
    return JsonResponse(validation_result)


@login_required
def dataset_download_yaml(request, name):
    """
    下载数据集YAML文件 - 对于引用类型，下载被引用的文件
    """
    manager = DatasetManager()
    dataset = manager.get_dataset_by_name(name)
    
    if not dataset:
        return JsonResponse({'error': '数据集不存在'}, status=404)
    
    try:
        # 使用dataset.yaml_content获取正确的内容
        yaml_content = dataset.yaml_content
        
        # 返回文件下载响应
        response = HttpResponse(yaml_content, content_type='text/yaml')
        response['Content-Disposition'] = f'attachment; filename="{dataset.display_filename}"'
        return response
        
    except Exception as e:
        return JsonResponse({'error': f'无法读取文件: {str(e)}'}, status=500)
