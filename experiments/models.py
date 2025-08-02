from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Experiment(models.Model):
    """
    实验模型 - 用于管理Ultralytics实验
    """
    EXPERIMENT_STATUS_CHOICES = [
        ('pending', '待启动'),
        ('queued', '排队'),
        ('running', '运行'),
        ('interrupted', '中断'),
        ('error', '错误'),
        ('completed', '完成'),
    ]
    
    TASK_TYPE_CHOICES = [
        ('detect', '目标检测'),
        ('segment', '实例分割'),
        ('classify', '图像分类'),
        ('pose', '姿态估计'),
        ('track', '目标跟踪'),
    ]
    
    # 基本信息
    name = models.CharField(max_length=200, verbose_name="实验名称")
    description = models.TextField(blank=True, null=True, verbose_name="实验描述")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="创建用户")
    
    # 实验配置
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES, default='detect', verbose_name="任务类型")
    model_configs = models.TextField(blank=True, null=True, verbose_name="模型配置", help_text="逗号分隔的模型配置路径")
    setting_config = models.CharField(max_length=200, blank=True, null=True, verbose_name="参数配置", help_text="参数配置文件路径")
    dataset = models.CharField(max_length=200, default='', verbose_name="数据集名称")
    epochs = models.IntegerField(default=100, verbose_name="训练轮数")
    batch_size = models.IntegerField(default=16, verbose_name="批量大小")
    device = models.CharField(max_length=20, default='auto', verbose_name="设备")
    
    # 新增字段
    SCALE_CHOICES = [
        ('n', 'Nano'),
        ('s', 'Small'),
        ('m', 'Medium'),
        ('l', 'Large'),
        ('x', 'Extra Large'),
    ]
    scale = models.CharField(max_length=1, choices=SCALE_CHOICES, default='n', verbose_name="尺寸")
    group = models.CharField(max_length=100, blank=True, null=True, verbose_name="分组")
    exp_timestamp = models.CharField(max_length=50, blank=True, null=True, verbose_name="实验时间戳")
    
    # 输出配置
    project_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="项目名称")
    
    # 状态和时间信息
    status = models.CharField(max_length=20, choices=EXPERIMENT_STATUS_CHOICES, default='pending', verbose_name="状态")
    command = models.TextField(blank=True, null=True, verbose_name="生成的命令")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    started_at = models.DateTimeField(blank=True, null=True, verbose_name="开始时间")
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name="完成时间")
    
    # 结果信息
    log_file = models.CharField(max_length=500, blank=True, null=True, verbose_name="日志文件")
    result_file = models.CharField(max_length=500, blank=True, null=True, verbose_name="结果文件")
    error_message = models.TextField(blank=True, null=True, verbose_name="错误信息")
    
    class Meta:
        verbose_name = "实验"
        verbose_name_plural = "实验"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.user.username}"
    
    def save(self, *args, **kwargs):
        """
        保存时自动生成命令和时间戳
        """
        # 生成时间戳（如果还没有的话）
        if not self.exp_timestamp:
            import datetime
            self.exp_timestamp = "t" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        
        self.generate_command()
        super().save(*args, **kwargs)
    
    @property
    def dataset_info(self):
        """
        获取数据集信息
        """
        try:
            from datasets.models import DatasetManager
            manager = DatasetManager()
            dataset_obj = manager.get_dataset_by_name(self.dataset)
            if dataset_obj:
                return {
                    'name': dataset_obj.name,
                    'path': dataset_obj.display_file_path,
                    'nc': dataset_obj.nc,
                    'names': dataset_obj.names,
                    'is_valid': dataset_obj.is_valid,
                    'description': dataset_obj.description
                }
        except Exception:
            pass
        return None
    
    def generate_command(self):
        """
        根据实验配置生成训练命令
        """
        # 构建模型配置参数
        model_param = ""
        if self.model_configs:
            # 处理模型配置列表，确保格式正确
            model_list = [config.strip() for config in self.model_configs.split(',') if config.strip()]
            
            # 对包含空格的模型名称添加双引号
            formatted_models = []
            for model in model_list:
                if ' ' in model:
                    # 检查是否已经有引号
                    if not (model.startswith('"') and model.endswith('"')):
                        # 找到最后一个斜杠位置
                        last_slash = model.rfind('/')
                        if last_slash != -1:
                            prefix = model[:last_slash + 1]
                            name = model[last_slash + 1:]
                            model = f'{prefix}"{name}"'
                        else:
                            model = f'"{model}"'
                formatted_models.append(model)
            
            # 用逗号连接（逗号后不加空格）
            model_param = f"model={','.join(formatted_models)}"
        
        # 构建设置配置参数
        setting_param = ""
        if self.setting_config:
            setting_param = f"setting={self.setting_config}"
        
        # 基本命令
        base_cmd = "uv run --quiet src/train.py -m"

        # 基本参数
        cmd_parts = [base_cmd]
        
        # 添加模型配置参数
        if model_param:
            cmd_parts.append(model_param)
        
        # 添加设置配置参数
        if setting_param:
            cmd_parts.append(setting_param)
         
        # 其他参数
        cmd_parts.extend([
            f"data={self.dataset}",  # 使用数据集名称而不是文件路径
            f"epochs={self.epochs}",
            f"batch={self.batch_size}",
            f"device=\"{self.device}\"",  # 设备格式化为字符串，如 "[0,1,2,3,4,5]"
            f"model.scale={self.scale}",  # 添加尺寸参数到model
            f"logger.exp_timestamp={self.exp_timestamp}",  # 添加时间戳参数到logger
        ])
        
        # 可选参数
        if self.project_name:
            cmd_parts.append(f"project_name={self.project_name}")  # 改为 project_name
        if self.group:
            cmd_parts.append(f"logger.group={self.group}")  # 添加分组参数到logger
        
        command = " ".join(cmd_parts)
        self.command = command
        return command
    
    def start_experiment(self):
        """
        启动实验
        """
        self.status = 'running'
        self.started_at = timezone.now()
        self.generate_command()
        self.save()
    
    def complete_experiment(self):
        """
        完成实验（正常结束）
        """
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def interrupt_experiment(self, message=None):
        """
        中断实验（用户手动停止）
        """
        self.status = 'interrupted'
        self.completed_at = timezone.now()
        if message:
            self.error_message = message
        self.save()
    
    def fail_experiment(self, error_message=None):
        """
        实验失败（运行错误）
        """
        self.status = 'error'
        self.completed_at = timezone.now()
        if error_message:
            self.error_message = error_message
        self.save()
    
    def queue_experiment(self):
        """
        将实验设置为排队状态
        """
        self.status = 'queued'
        self.save()


class ExperimentLog(models.Model):
    """
    实验日志模型
    """
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='logs', verbose_name="实验")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="时间戳")
    level = models.CharField(max_length=20, default='INFO', verbose_name="日志级别")
    message = models.TextField(verbose_name="日志信息")
    
    class Meta:
        verbose_name = "实验日志"
        verbose_name_plural = "实验日志"
        ordering = ['timestamp']  # 改为正序：最早的在上面，最新的在下面
    
    def __str__(self):
        return f"{self.experiment.name} - {self.timestamp}"
