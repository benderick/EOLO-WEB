import subprocess
import json
import re
from typing import List, Dict, Optional
from django.conf import settings


def check_gpu_memory_usage() -> Dict[str, Dict]:
    """
    检查GPU显存使用情况
    
    Returns:
        Dict: GPU信息字典，格式为:
        {
            "0": {"memory_used_percent": 25.5, "memory_total": 24576, "memory_used": 6277},
            "1": {"memory_used_percent": 15.2, "memory_total": 24576, "memory_used": 3735},
            ...
        }
    """
    try:
        # 从配置获取超时时间
        timeout = getattr(settings, 'GPU_CONFIG', {}).get('NVIDIA_SMI_TIMEOUT', 10)
        
        # 运行nvidia-smi命令获取GPU信息
        result = subprocess.run([
            'nvidia-smi', 
            '--query-gpu=index,memory.total,memory.used,memory.free',
            '--format=csv,noheader,nounits'
        ], capture_output=True, text=True, timeout=timeout)
        
        if result.returncode != 0:
            return {}
        
        gpu_info = {}
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    gpu_index = parts[0]
                    memory_total = int(parts[1])
                    memory_used = int(parts[2])
                    memory_used_percent = (memory_used / memory_total * 100) if memory_total > 0 else 0
                    
                    gpu_info[gpu_index] = {
                        'memory_total': memory_total,
                        'memory_used': memory_used,
                        'memory_used_percent': round(memory_used_percent, 1)
                    }
        
        return gpu_info
        
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
        # nvidia-smi不可用或执行失败
        return {}
    except Exception as e:
        return {}


def parse_device_string(device_str: str) -> List[int]:
    """
    解析设备字符串，提取GPU索引列表
    
    Args:
        device_str: 设备字符串，如 "[0,1,2]", "0", "cuda:0", "auto"
        
    Returns:
        List[int]: GPU索引列表
    """
    if not device_str or device_str.lower() in ['auto', 'cpu']:
        return []
    
    # 处理形如 "[0,1,2]" 的格式
    if device_str.startswith('[') and device_str.endswith(']'):
        device_str = device_str[1:-1]
    
    # 处理形如 "cuda:0" 的格式
    if device_str.startswith('cuda:'):
        device_str = device_str[5:]
    
    gpu_indices = []
    try:
        # 分割逗号分隔的GPU索引
        for part in device_str.split(','):
            part = part.strip()
            if part.isdigit():
                gpu_indices.append(int(part))
    except (ValueError, AttributeError):
        pass
    
    return gpu_indices


def check_gpu_availability(device_str: str, memory_threshold: float = None) -> Dict:
    """
    检查指定GPU的可用性
    
    Args:
        device_str: 设备字符串
        memory_threshold: 显存使用率阈值（百分比），如果为None则从配置读取
        
    Returns:
        Dict: 检查结果
        {
            "available": bool,  # 是否可用
            "gpu_indices": List[int],  # GPU索引列表
            "gpu_status": Dict,  # 每个GPU的状态
            "busy_gpus": List[int],  # 忙碌的GPU列表
            "message": str  # 详细信息
        }
    """
    # 从配置获取默认阈值
    if memory_threshold is None:
        memory_threshold = getattr(settings, 'GPU_CONFIG', {}).get('MEMORY_THRESHOLD', 20.0)
    
    gpu_indices = parse_device_string(device_str)
    
    # 如果没有指定GPU或使用auto/cpu，认为可用
    if not gpu_indices:
        return {
            "available": True,
            "gpu_indices": [],
            "gpu_status": {},
            "busy_gpus": [],
            "message": "未指定GPU设备或使用自动分配"
        }
    
    # 获取GPU使用情况
    gpu_info = check_gpu_memory_usage()
    
    if not gpu_info:
        # 无法获取GPU信息，假设可用
        return {
            "available": True,
            "gpu_indices": gpu_indices,
            "gpu_status": {},
            "busy_gpus": [],
            "message": "无法获取GPU信息，假设可用"
        }
    
    gpu_status = {}
    busy_gpus = []
    
    for gpu_idx in gpu_indices:
        gpu_str = str(gpu_idx)
        if gpu_str in gpu_info:
            usage_percent = gpu_info[gpu_str]['memory_used_percent']
            gpu_status[gpu_idx] = {
                'memory_used_percent': usage_percent,
                'memory_total': gpu_info[gpu_str]['memory_total'],
                'memory_used': gpu_info[gpu_str]['memory_used']
            }
            
            if usage_percent > memory_threshold:
                busy_gpus.append(gpu_idx)
        else:
            # GPU不存在
            gpu_status[gpu_idx] = {
                'memory_used_percent': 0,
                'memory_total': 0,
                'memory_used': 0,
                'error': 'GPU不存在'
            }
    
    available = len(busy_gpus) == 0
    
    if available:
        message = f"所有指定的GPU ({gpu_indices}) 可用"
    else:
        busy_info = []
        for gpu_idx in busy_gpus:
            if gpu_idx in gpu_status:
                usage = gpu_status[gpu_idx]['memory_used_percent']
                busy_info.append(f"GPU {gpu_idx}: {usage}%")
        message = f"以下GPU显存使用率超过{memory_threshold}%: {', '.join(busy_info)}"
    
    return {
        "available": available,
        "gpu_indices": gpu_indices,
        "gpu_status": gpu_status,
        "busy_gpus": busy_gpus,
        "message": message
    }
