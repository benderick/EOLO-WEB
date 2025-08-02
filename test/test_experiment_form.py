#!/usr/bin/env python
"""
测试实验表单功能
"""
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eolo_web.settings')
sys.path.append('/icislab/volume3/benderick/futurama/EOLO-WEB')
django.setup()

from experiments.forms import ExperimentForm
from datasets.models import DatasetManager

def test_experiment_form():
    """测试实验表单功能"""
    print("=== 测试实验表单功能 ===")
    
    # 测试表单初始化
    print("\n1. 测试表单初始化:")
    form = ExperimentForm()
    
    # 检查数据集选择字段
    dataset_choices = form.fields['dataset'].choices
    print(f"数据集选择数量: {len(dataset_choices)}")
    
    for value, label in dataset_choices:
        if isinstance(label, list):  # 分组选择
            print(f"分组: {value}")
            for sub_value, sub_label in label:
                print(f"  - {sub_value}: {sub_label}")
        else:
            print(f"  - {value}: {label}")
    
    # 测试表单验证
    print("\n2. 测试表单验证:")
    
    # 测试有效数据
    valid_data = {
        'name': 'test_experiment',
        'description': '测试实验',
        'task_type': 'detect',
        'model_name': 'yolov8n.pt',
        'dataset': 'VisDrone',
        'epochs': 100,
        'batch_size': 16,
        'image_size': 640,
        'learning_rate': 0.01,
        'weight_decay': 0.0005,
        'device': 'auto',
        'workers': 8,
    }
    
    form_valid = ExperimentForm(data=valid_data)
    print(f"有效数据验证: {form_valid.is_valid()}")
    if not form_valid.is_valid():
        print(f"错误: {form_valid.errors}")
    
    # 测试无效数据（无数据集）
    invalid_data = valid_data.copy()
    invalid_data['dataset'] = ''
    
    form_invalid = ExperimentForm(data=invalid_data)
    print(f"无效数据验证: {form_invalid.is_valid()}")
    if not form_invalid.is_valid():
        print(f"预期错误: {form_invalid.errors.get('dataset', [])}")
    
    print("\n3. 测试数据集信息:")
    manager = DatasetManager()
    datasets = manager.get_all_datasets()
    
    for dataset in datasets:
        print(f"数据集: {dataset.name}")
        print(f"  有效性: {dataset.is_valid}")
        print(f"  类别数: {dataset.nc}")
        print(f"  描述: {dataset.description}")
        print(f"  显示路径: {dataset.display_file_path}")

if __name__ == '__main__':
    test_experiment_form()
