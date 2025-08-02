from django import forms
from .models import Experiment
from datasets.models import DatasetManager
from datetime import datetime
from .widgets import GPUStatusCheckboxSelectMultiple
from .gpu_utils import check_gpu_memory_usage


def get_gpu_choices():
    """
    动态获取可用的GPU选项
    """
    try:
        gpu_usage = check_gpu_memory_usage()
        if gpu_usage:
            return [(gpu_id, f'GPU {gpu_id}') for gpu_id in sorted(gpu_usage.keys(), key=int)]
        else:
            # 如果检测失败，返回默认的6个GPU
            return [(str(i), f'GPU {i}') for i in range(6)]
    except Exception:
        # 异常情况下返回默认选项
        return [(str(i), f'GPU {i}') for i in range(6)]


class ExperimentForm(forms.ModelForm):
    """
    实验创建和编辑表单
    """
    
    # 添加数据集选择字段
    dataset = forms.ChoiceField(
        label='数据集',
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text='选择用于训练的数据集'
    )
    
    # 模型选择字段（多选，但存储为文本）
    model_configs = forms.CharField(
        label='模型配置',
        widget=forms.HiddenInput(),
        help_text='选择用于训练的模型配置文件（可多选）',
        required=True
    )
    
    # 设置选择字段（单选，存储为文本）
    setting_config = forms.CharField(
        label='参数配置',
        widget=forms.HiddenInput(),
        help_text='选择训练参数配置文件（单选）',
        required=False
    )
     
    # 设备多选字段
    device = forms.MultipleChoiceField(
        label='训练设备',
        choices=get_gpu_choices(),
        widget=GPUStatusCheckboxSelectMultiple(),
        help_text='选择用于训练的GPU设备（可多选），绿色表示可用，黄色表示使用中，红色表示繁忙',
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # 动态更新GPU选择
        self.fields['device'].choices = get_gpu_choices()
        
        # 动态设置widget的choices
        self.fields['device'].widget.choices = get_gpu_choices()
        
        # 动态加载数据集选择
        self._load_dataset_choices()
        
        # 生成默认实验名称（当前时间）
        current_time = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        self.fields['name'].initial = current_time
        
        # 设置项目名称为用户名
        if user:
            self.fields['project_name'].initial = user.username
        
        # 为字段添加帮助文本
        self.fields['name'].help_text = '自动生成的实验名称（基于创建时间）'
        self.fields['model_configs'].help_text = '选择YAML模型配置文件，可多选'
        self.fields['setting_config'].help_text = '选择训练参数配置文件，可选'
        self.fields['dataset'].help_text = '选择已配置的数据集进行训练'
        self.fields['epochs'].help_text = '训练的轮数，建议100-300'
        self.fields['batch_size'].help_text = '批量大小，根据显存调整'
        self.fields['device'].help_text = '选择GPU设备，可多选；设备繁忙也不要紧，可以加入队列。'
        self.fields['project_name'].help_text = '项目名称，固定为您的用户名'
        
        # 如果用户有之前的实验，使用上次的设置
        if user and not self.instance.pk:  # 仅在创建新实验时
            self._load_last_experiment_settings(user)
    
    def _load_last_experiment_settings(self, user):
        """
        加载用户上次实验的设置
        """
        try:
            last_experiment = Experiment.objects.filter(user=user).order_by('-created_at').first()
            if last_experiment:
                # 复制上次的设置（包括模型配置和参数配置）
                self.fields['description'].initial = last_experiment.description
                self.fields['dataset'].initial = last_experiment.dataset
                self.fields['epochs'].initial = last_experiment.epochs
                self.fields['batch_size'].initial = last_experiment.batch_size
                
                # 新增字段的默认值
                if hasattr(last_experiment, 'scale'):
                    self.fields['scale'].initial = last_experiment.scale
                if hasattr(last_experiment, 'group'):
                    self.fields['group'].initial = last_experiment.group
                
                # 设置上次的模型配置选择
                if last_experiment.model_configs:
                    self.fields['model_configs'].initial = last_experiment.model_configs
                
                # 设置上次的参数配置选择
                if last_experiment.setting_config:
                    self.fields['setting_config'].initial = last_experiment.setting_config
                
                # 设备需要特殊处理，因为新的是多选字段
                if last_experiment.device and last_experiment.device != 'auto':
                    # 解析设备字符串，提取数字
                    try:
                        device_str = last_experiment.device.strip('[]')
                        if ',' in device_str:
                            devices = [d.strip() for d in device_str.split(',')]
                        else:
                            devices = [device_str]
                        # 过滤出0-5范围内的设备
                        valid_devices = [d for d in devices if d.isdigit() and 0 <= int(d) <= 5]
                        self.fields['device'].initial = valid_devices
                    except:
                        pass
        except Exception:
            pass  # 如果出错，使用默认值
    
    class Meta:
        model = Experiment
        fields = [
            'name', 'description', 'model_configs', 'setting_config', 'dataset',
            'epochs', 'batch_size', 'device', 'project_name', 'scale', 'group'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入实验名称',
                'readonly': True  # 由时间自动生成
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '请输入实验描述（可选）'
            }),
            'epochs': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 1000
            }),
            'batch_size': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 128
            }),
            'project_name': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': True  # 固定为用户名
            }),
            'scale': forms.Select(attrs={
                'class': 'form-control'
            }),
            'group': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '分组名称（可选）'
            }),
        }
    
    def _load_dataset_choices(self):
        """
        动态加载数据集选择列表
        """
        try:
            manager = DatasetManager()
            datasets = manager.get_all_datasets()
            
            # 构建选择列表
            choices = [('', '请选择数据集')]
            
            # 按有效性分组
            valid_datasets = []
            invalid_datasets = []
            
            for dataset in datasets:
                display_name = f"{dataset.name}"
                if dataset.nc > 0:
                    display_name += f" ({dataset.nc}类)"
                if dataset.description:
                    display_name += f" - {dataset.description}"
                
                if dataset.is_valid:
                    valid_datasets.append((dataset.name, display_name))
                else:
                    invalid_datasets.append((dataset.name, f"⚠️ {display_name} (配置错误)"))
            
            # 先添加有效的数据集
            if valid_datasets:
                choices.append(('有效数据集', valid_datasets))
            
            # 再添加无效的数据集（如果有）
            if invalid_datasets:
                choices.append(('配置错误的数据集', invalid_datasets))
            
            self.fields['dataset'].choices = choices
            
        except Exception as e:
            # 如果加载失败，提供默认选项
            self.fields['dataset'].choices = [
                ('', '加载数据集失败，请检查配置')
            ]
        
    def clean_model_configs(self):
        """
        验证模型配置选择
        """
        model_configs = self.cleaned_data.get('model_configs')
        if not model_configs:
            raise forms.ValidationError('请至少选择一个模型配置')
        
        # 验证每个模型配置路径格式
        config_list = [config.strip() for config in model_configs.split(',') if config.strip()]
        if not config_list:
            raise forms.ValidationError('请至少选择一个模型配置')
        
        # 验证路径格式（应该是 prefix/name 格式）
        for config in config_list:
            if '/' not in config:
                raise forms.ValidationError(f'模型配置路径格式错误: {config}')
        
        return model_configs  # 直接返回原始字符串
    
    def clean_setting_config(self):
        """
        验证设置配置选择
        """
        setting_config = self.cleaned_data.get('setting_config')
        # 设置配置是可选的，可以为空
        if setting_config and setting_config.strip() and '/' not in setting_config:
            raise forms.ValidationError(f'参数配置路径格式错误: {setting_config}')
        
        return setting_config or ''  # 返回空字符串而不是None
    
    def clean_dataset(self):
        """
        验证选择的数据集
        """
        dataset_name = self.cleaned_data['dataset']
        if not dataset_name:
            raise forms.ValidationError('请选择一个数据集')
        
        # 验证数据集是否存在且有效
        try:
            manager = DatasetManager()
            dataset = manager.get_dataset_by_name(dataset_name)
            if not dataset:
                raise forms.ValidationError(f'数据集 "{dataset_name}" 不存在')
            if not dataset.is_valid:
                raise forms.ValidationError(f'数据集 "{dataset_name}" 配置错误，请检查配置文件')
        except Exception as e:
            raise forms.ValidationError(f'验证数据集时出错: {str(e)}')
        
        return dataset_name
    
    def clean_device(self):
        """
        验证并格式化设备选择
        """
        devices = self.cleaned_data.get('device', [])
        if not devices:
            return 'auto'  # 如果没有选择设备，使用auto
        
        # 格式化为 [0,1,2] 这样的字符串（不带空格）
        device_list = [int(d) for d in devices if d.isdigit()]
        if len(device_list) == 1:
            return f"[{device_list[0]}]"  # 单个设备也用列表格式
        else:
            # 多个设备返回列表格式，不带空格
            device_str = ','.join(map(str, device_list))
            return f"[{device_str}]"
    
    def clean_epochs(self):
        """
        验证训练轮数
        """
        epochs = self.cleaned_data['epochs']
        if epochs <= 0:
            raise forms.ValidationError('训练轮数必须大于0')
        return epochs
    
    def clean_batch_size(self):
        """
        验证批量大小
        """
        batch_size = self.cleaned_data['batch_size']
        if batch_size <= 0:
            raise forms.ValidationError('批量大小必须大于0')
        return batch_size
