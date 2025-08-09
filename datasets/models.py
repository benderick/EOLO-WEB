import os
import yaml
import json
from django.db import models
from django.conf import settings
from django.utils import timezone


class Dataset:
    """
    数据集类 - 从YAML配置文件读取数据集信息
    这不是Django模型，而是一个普通的Python类
    支持两种格式：
    1. 直接包含数据集配置的YAML文件
    2. 引用其他文件的配置文件（包含name和file字段）
    """
    
    def __init__(self, filename, file_path):
        self.filename = filename
        self.file_path = file_path
        self.name = os.path.splitext(filename)[0]
        self._data = None
        self._referenced_data = None
        self._load_data()
    
    def _load_data(self):
        """加载YAML文件数据"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self._data = yaml.safe_load(f)
            
            # 检查是否是引用型配置文件
            if self._is_reference_config():
                self._load_referenced_data()
                
        except Exception as e:
            self._data = {'error': f'无法读取文件: {str(e)}'}
    
    def _is_reference_config(self):
        """判断是否是引用型配置文件"""
        if not self._data:
            return False
        # 如果包含name和file字段，且字段数量较少，则认为是引用型
        return ('name' in self._data and 'file' in self._data and 
                len(self._data) <= 3 and 'nc' not in self._data)
    
    def _load_paths_config(self):
        """
        从EOLO/api/paths.json文件读取路径配置
        
        Returns:
            dict: 路径配置字典，如果读取失败返回空字典
        """
        try:
            # 获取EOLO项目根目录
            eolo_root = settings.BASE_DIR / 'EOLO'
            paths_file = settings.EOLO_PATHS_JSON

            if paths_file.exists():
                with open(paths_file, 'r', encoding='utf-8') as f:
                    paths_config = json.load(f)
                    return paths_config.get('paths', {})
            else:
                # 如果paths.json不存在，使用默认路径
                return {
                    'data_dir': str(eolo_root / 'data'),
                    'root_dir': str(eolo_root),
                    'work_dir': str(eolo_root)
                }
        except Exception as e:
            # 读取失败时使用默认路径
            eolo_root = settings.BASE_DIR / 'EOLO'
            return {
                'data_dir': str(eolo_root / 'data'),
                'root_dir': str(eolo_root),
                'work_dir': str(eolo_root)
            }
    
    def _resolve_path_variables(self, path_string):
        """
        解析路径字符串中的变量
        
        Args:
            path_string (str): 包含变量的路径字符串，如 "${paths.data_dir}/UAVDT/UAVDT.yaml"
            
        Returns:
            str: 解析后的完整路径
        """
        if not path_string or '${' not in path_string:
            return path_string
        
        # 获取路径配置
        paths_config = self._load_paths_config()
        
        # 替换路径变量
        resolved_path = path_string
        for key, value in paths_config.items():
            variable_pattern = f'${{paths.{key}}}'
            if variable_pattern in resolved_path:
                resolved_path = resolved_path.replace(variable_pattern, value)
        
        return resolved_path
    
    def _load_referenced_data(self):
        """加载被引用的数据集文件"""
        try:
            referenced_file = self._data.get('file', '')
            if referenced_file:
                # 解析路径变量
                resolved_path = self._resolve_path_variables(referenced_file)
                
                if os.path.exists(resolved_path):
                    with open(resolved_path, 'r', encoding='utf-8') as f:
                        self._referenced_data = yaml.safe_load(f)
                else:
                    # 如果文件不存在，在_referenced_data中记录错误信息
                    self._referenced_data = {
                        'error': f'引用的数据集文件不存在: {resolved_path}',
                        'original_path': referenced_file,
                        'resolved_path': resolved_path
                    }
        except Exception as e:
            # 如果无法加载引用文件，记录错误信息
            self._referenced_data = {
                'error': f'加载引用文件时出错: {str(e)}',
                'original_path': self._data.get('file', '')
            }
    
    @property
    def data(self):
        """获取YAML数据 - 优先返回引用的数据，否则返回原始数据"""
        return self._referenced_data or self._data or {}
    
    @property
    def original_data(self):
        """获取原始配置文件数据"""
        return self._data or {}
    
    def _resolve_dataset_path(self, path_value):
        """
        解析数据集中的路径 - 处理相对路径和绝对路径
        
        Args:
            path_value (str): 路径值，可能是相对路径或绝对路径
            
        Returns:
            str: 解析后的绝对路径
        """
        if not path_value:
            return path_value
        
        # 如果是绝对路径，直接返回
        if os.path.isabs(path_value):
            return path_value
        
        # 如果是引用类型且被引用文件存在，相对于被引用文件所在目录解析路径
        if self.is_reference_type and self.referenced_file_exists:
            base_dir = os.path.dirname(self.referenced_file_path)
            return os.path.abspath(os.path.join(base_dir, path_value))
        
        # 否则相对于配置文件所在目录解析路径
        base_dir = os.path.dirname(self.file_path)
        return os.path.abspath(os.path.join(base_dir, path_value))
    
    @property
    def path(self):
        """获取path字段 - 转换为绝对路径"""
        path_value = self.data.get('path', '')
        return self._resolve_dataset_path(path_value)
    
    @property
    def train(self):
        """获取train路径 - 转换为绝对路径"""
        train_value = self.data.get('train', '')
        return self._resolve_dataset_path(train_value)
    
    @property
    def val(self):
        """获取val路径 - 转换为绝对路径"""
        val_value = self.data.get('val', '')
        return self._resolve_dataset_path(val_value)
    
    @property
    def test(self):
        """获取test路径 - 转换为绝对路径"""
        test_value = self.data.get('test', '')
        return self._resolve_dataset_path(test_value)
    
    @property
    def path_original(self):
        """获取原始path字段（未解析的路径）"""
        return self.data.get('path', '')
    
    @property
    def train_original(self):
        """获取原始train路径（未解析的路径）"""
        return self.data.get('train', '')
    
    @property
    def val_original(self):
        """获取原始val路径（未解析的路径）"""
        return self.data.get('val', '')
    
    @property
    def test_original(self):
        """获取原始test路径（未解析的路径）"""
        return self.data.get('test', '')
    
    @property
    def nc(self):
        """获取类别数量"""
        return self.data.get('nc', 0)
    
    @property
    def names(self):
        """获取类别名称列表"""
        return self.data.get('names', [])
    
    @property
    def description(self):
        """获取数据集描述"""
        return self.data.get('description', self.data.get('desc', ''))
    
    @property
    def download(self):
        """获取下载链接"""
        return self.data.get('download', '')
    
    @property
    def size(self):
        """获取文件大小 - 对于引用类型，返回数据集文件夹大小"""
        try:
            if self.is_reference_type and self.referenced_file_exists:
                # 对于引用类型，计算整个数据集文件夹的大小
                ref_path = self.referenced_file_path
                dataset_dir = os.path.dirname(ref_path)
                if os.path.exists(dataset_dir):
                    total_size = 0
                    for dirpath, dirnames, filenames in os.walk(dataset_dir):
                        for filename in filenames:
                            filepath = os.path.join(dirpath, filename)
                            try:
                                total_size += os.path.getsize(filepath)
                            except (OSError, IOError):
                                pass
                    return total_size
            # 普通情况返回YAML文件大小
            return os.path.getsize(self.file_path)
        except:
            return 0
    
    @property
    def modified_time(self):
        """获取修改时间 - 对于引用类型，返回被引用文件的修改时间"""
        try:
            if self.is_reference_type and self.referenced_file_exists:
                # 对于引用类型，返回被引用文件的修改时间
                timestamp = os.path.getmtime(self.referenced_file_path)
            else:
                # 普通情况返回YAML文件修改时间
                timestamp = os.path.getmtime(self.file_path)
            return timezone.datetime.fromtimestamp(timestamp, tz=timezone.get_current_timezone())
        except:
            return None
    
    @property
    def is_valid(self):
        """检查数据集配置是否有效"""
        return 'error' not in self.data and bool(self.data.get('names'))
    
    @property
    def is_reference_type(self):
        """检查是否是引用型配置文件"""
        return self._is_reference_config()
    
    @property
    def referenced_file_path(self):
        """获取解析后的引用文件路径"""
        if self.is_reference_type:
            original_path = self.original_data.get('file', '')
            return self._resolve_path_variables(original_path)
        return None
    
    @property
    def referenced_file_exists(self):
        """检查引用的文件是否存在"""
        ref_path = self.referenced_file_path
        return ref_path and os.path.exists(ref_path)
    
    @property
    def reference_error(self):
        """获取引用文件的错误信息"""
        if self._referenced_data and 'error' in self._referenced_data:
            return self._referenced_data['error']
        return None
    
    @property
    def yaml_content(self):
        """获取YAML文件内容 - 对于引用类型，返回被引用文件的内容"""
        try:
            if self.is_reference_type and self.referenced_file_exists:
                # 对于引用类型，读取被引用文件的内容
                with open(self.referenced_file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                # 普通情况读取原始文件内容
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            return f"无法读取文件内容: {str(e)}"
    
    @property
    def display_file_path(self):
        """获取显示用的文件路径 - 对于引用类型，返回被引用文件的路径"""
        if self.is_reference_type and self.referenced_file_exists:
            return self.referenced_file_path
        return self.file_path
    
    @property
    def display_filename(self):
        """获取显示用的文件名 - 对于引用类型，返回被引用文件的文件名"""
        if self.is_reference_type and self.referenced_file_exists:
            return os.path.basename(self.referenced_file_path)
        return self.filename
    
    @property
    def file_stats(self):
        """获取文件详细统计信息"""
        try:
            stat = os.stat(self.file_path)
            return {
                'size': stat.st_size,
                'created': timezone.datetime.fromtimestamp(stat.st_ctime, tz=timezone.get_current_timezone()),
                'modified': timezone.datetime.fromtimestamp(stat.st_mtime, tz=timezone.get_current_timezone()),
                'accessed': timezone.datetime.fromtimestamp(stat.st_atime, tz=timezone.get_current_timezone()),
            }
        except Exception:
            return {
                'size': 0,
                'created': None,
                'modified': None,
                'accessed': None,
            }
    
    def validate_paths(self):
        """验证数据集中的路径是否存在"""
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
        }
        
        # 检查主要路径
        for path_type in ['path', 'train', 'val', 'test']:
            path_value = getattr(self, path_type)
            if path_value:
                # 解析路径变量
                resolved_path = self._resolve_path_variables(path_value)
                if not os.path.exists(resolved_path):
                    validation_results['errors'].append(f'{path_type}路径不存在: {resolved_path}')
                    validation_results['valid'] = False
        
        # 检查引用文件
        if self.is_reference_type and not self.referenced_file_exists:
            validation_results['errors'].append(f'引用文件不存在: {self.referenced_file_path}')
            validation_results['valid'] = False
        
        # 检查类别数量和名称的一致性
        if self.nc > 0 and len(self.names) != self.nc:
            validation_results['warnings'].append(f'类别数量({self.nc})与names列表长度({len(self.names)})不匹配')
        
        return validation_results
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'name': self.name,
            'filename': self.filename,
            'path': self.path,
            'train': self.train,
            'val': self.val,
            'test': self.test,
            'nc': self.nc,
            'names': self.names,
            'description': self.description,
            'download': self.download,
            'size': self.size,
            'modified_time': self.modified_time,
            'is_valid': self.is_valid,
            'data': self.data
        }


class DatasetManager:
    """
    数据集管理器 - 负责扫描和管理数据集文件
    """
    
    def __init__(self):
        self.datasets_dir = getattr(settings, 'EOLO_DATASETS_CONFIGS_DIR', '')
    
    def get_all_datasets(self):
        """获取所有数据集"""
        datasets = []
        
        if not os.path.exists(self.datasets_dir):
            return datasets
        
        try:
            for filename in os.listdir(self.datasets_dir):
                if filename.endswith('.yaml') or filename.endswith('.yml'):
                    file_path = os.path.join(self.datasets_dir, filename)
                    if os.path.isfile(file_path):
                        dataset = Dataset(filename, file_path)
                        datasets.append(dataset)
        except Exception as e:
            # 处理目录访问错误
            pass
        
        # 按名称排序
        datasets.sort(key=lambda x: x.name.lower())
        return datasets
    
    def get_dataset_by_name(self, name):
        """根据名称获取数据集"""
        datasets = self.get_all_datasets()
        for dataset in datasets:
            if dataset.name == name:
                return dataset
        return None
    
    def search_datasets(self, query):
        """搜索数据集"""
        datasets = self.get_all_datasets()
        if not query:
            return datasets
        
        query = query.lower()
        filtered_datasets = []
        
        for dataset in datasets:
            # 在名称、描述、类别名称中搜索
            if (query in dataset.name.lower() or 
                query in dataset.description.lower() or
                any(query in name.lower() for name in dataset.names)):
                filtered_datasets.append(dataset)
        
        return filtered_datasets
