#!/usr/bin/env python
"""
测试创建实验功能
"""
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eolo_web.settings')
sys.path.append('/icislab/volume3/benderick/futurama/EOLO-WEB')
django.setup()

from experiments.models import Experiment
from accounts.models import User

def test_create_experiment():
    """测试创建实验功能"""
    print("=== 测试创建实验功能 ===")
    
    # 获取测试用户
    try:
        user = User.objects.get(username='testuser')
        print(f"使用测试用户: {user.username}")
    except User.DoesNotExist:
        user = User.objects.create_user('testuser', 'test@example.com', 'test123')
        print(f"创建测试用户: {user.username}")
    
    # 创建测试实验
    experiment_data = {
        'name': 'VisDrone_Detection_Test',
        'description': '使用VisDrone数据集进行目标检测实验',
        'user': user,
        'task_type': 'detect',
        'model_name': 'yolov8n.pt',
        'dataset': 'VisDrone',
        'epochs': 50,
        'batch_size': 16,
        'image_size': 640,
        'learning_rate': 0.01,
        'weight_decay': 0.0005,
        'device': 'auto',
        'workers': 8,
        'project_name': 'EOLO_Experiments',
        'experiment_name': 'VisDrone_Test'
    }
    
    # 创建实验
    experiment = Experiment.objects.create(**experiment_data)
    print(f"\n创建实验: {experiment.name}")
    print(f"实验ID: {experiment.pk}")
    
    # 生成命令
    command = experiment.generate_command()
    print(f"\n生成的命令:")
    print(command)
    
    # 检查数据集信息
    dataset_info = experiment.dataset_info
    print(f"\n数据集信息:")
    if dataset_info:
        print(f"  名称: {dataset_info['name']}")
        print(f"  路径: {dataset_info['path']}")
        print(f"  类别数: {dataset_info['nc']}")
        print(f"  类别: {dataset_info['names']}")
        print(f"  有效性: {dataset_info['is_valid']}")
    else:
        print("  无法获取数据集信息")
    
    # 查看生成的命令是否使用了正确的数据集路径
    print(f"\n命令分析:")
    if 'data=' in command:
        data_part = [part for part in command.split() if part.startswith('data=')][0]
        print(f"数据路径: {data_part}")
    
    print(f"\n实验创建成功，状态: {experiment.status}")
    
    # 清理
    experiment.delete()
    print("测试实验已删除")

if __name__ == '__main__':
    test_create_experiment()
