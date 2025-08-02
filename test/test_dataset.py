#!/usr/bin/env python
"""
测试数据集功能的脚本
"""
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eolo_web.settings')
sys.path.append('/icislab/volume3/benderick/futurama/EOLO-WEB')
django.setup()

from datasets.models import DatasetManager

def test_dataset_functionality():
    """测试数据集功能"""
    print("=== 测试数据集功能 ===")
    
    # 创建数据集管理器
    manager = DatasetManager()
    
    # 获取所有数据集
    print("\n1. 获取所有数据集:")
    datasets = manager.get_all_datasets()
    print(f"找到 {len(datasets)} 个数据集")
    
    for dataset in datasets:
        print(f"  - {dataset.name} ({dataset.filename})")
    
    # 测试VisDrone数据集
    print("\n2. 测试VisDrone数据集:")
    visdrone = manager.get_dataset_by_name('VisDrone')
    
    if visdrone:
        print(f"数据集名称: {visdrone.name}")
        print(f"是否为引用类型: {visdrone.is_reference_type}")
        print(f"原始文件路径: {visdrone.file_path}")
        print(f"显示文件路径: {visdrone.display_file_path}")
        print(f"原始文件名: {visdrone.filename}")
        print(f"显示文件名: {visdrone.display_filename}")
        print(f"引用文件是否存在: {visdrone.referenced_file_exists}")
        print(f"数据集是否有效: {visdrone.is_valid}")
        print(f"类别数量: {visdrone.nc}")
        print(f"类别名称: {visdrone.names}")
        print(f"文件大小: {visdrone.size} bytes")
        print(f"修改时间: {visdrone.modified_time}")
        
        print(f"\n路径信息:")
        print(f"  train原始: '{visdrone.train_original}'")
        print(f"  train解析: '{visdrone.train}'")
        print(f"  val原始: '{visdrone.val_original}'")
        print(f"  val解析: '{visdrone.val}'")
        print(f"  test原始: '{visdrone.test_original}'")
        print(f"  test解析: '{visdrone.test}'")
        
        if visdrone.reference_error:
            print(f"引用错误: {visdrone.reference_error}")
        
        print(f"\nYAML内容前100字符:")
        yaml_content = visdrone.yaml_content
        print(yaml_content[:100] + "...")
        
        print(f"\n路径验证结果:")
        validation = visdrone.validate_paths()
        print(f"  有效: {validation['valid']}")
        if validation['errors']:
            print(f"  错误: {validation['errors']}")
        if validation['warnings']:
            print(f"  警告: {validation['warnings']}")
    else:
        print("VisDrone数据集未找到")

if __name__ == '__main__':
    test_dataset_functionality()
