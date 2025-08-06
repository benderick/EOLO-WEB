"""
模块管理相关的数据模型
"""
from django.db import models
from django.contrib.auth import get_user_model
from pathlib import Path
from django.conf import settings

User = get_user_model()


class FileStatus(models.TextChoices):
    """文件状态枚举"""
    UNREVIEWED = 'unreviewed', '未审查'  # ⭕
    AVAILABLE = 'available', '可用'      # ✔
    UNAVAILABLE = 'unavailable', '不可用' # ❌


class ModuleCategory(models.TextChoices):
    """模块分类枚举"""
    ATTENTION = 'attention', 'Attention'
    CONVOLUTION = 'convolution', 'Convolution'
    DOWNSAMPLE = 'downsample', 'Downsample'
    FUSION = 'fusion', 'Fusion'
    HEAD = 'head', 'Head'
    BLOCK = 'block', 'Block'
    OTHER = 'other', 'Other'


class DynamicModuleCategory(models.Model):
    """
    动态模块分类管理
    支持管理员添加/删除分类
    """
    key = models.CharField(max_length=50, unique=True, verbose_name="分类键")
    label = models.CharField(max_length=100, verbose_name="分类标签")
    description = models.TextField(blank=True, verbose_name="分类描述")
    icon = models.CharField(max_length=50, default="fas fa-cube", verbose_name="图标类名")
    color = models.CharField(max_length=20, default="primary", verbose_name="颜色主题")
    is_default = models.BooleanField(default=False, verbose_name="是否为默认分类")
    is_selectable = models.BooleanField(default=True, verbose_name="是否可选择")
    order = models.IntegerField(default=0, verbose_name="排序顺序")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="创建者")
    
    class Meta:
        verbose_name = "动态模块分类"
        verbose_name_plural = "动态模块分类"
        ordering = ['order', 'key']
    
    def __str__(self):
        return f"{self.label} ({self.key})"
    
    @classmethod
    def get_all_categories(cls):
        """获取所有分类（包括默认分类和动态分类）"""
        categories = []
        
        # 定义默认分类的配置
        default_categories_config = {
            'attention': {'icon': 'fas fa-eye', 'color': 'info', 'order': 10},
            'convolution': {'icon': 'fas fa-filter', 'color': 'primary', 'order': 20},
            'downsample': {'icon': 'fas fa-compress-arrows-alt', 'color': 'warning', 'order': 30},
            'fusion': {'icon': 'fas fa-project-diagram', 'color': 'success', 'order': 40},
            'head': {'icon': 'fas fa-brain', 'color': 'danger', 'order': 50},
            'block': {'icon': 'fas fa-th-large', 'color': 'secondary', 'order': 60},
            'other': {'icon': 'fas fa-cube', 'color': 'dark', 'order': 999},
        }
        
        # 添加默认的固定分类
        for choice in ModuleCategory.choices:
            config = default_categories_config.get(choice[0], {})
            categories.append({
                'key': choice[0],
                'label': choice[1],
                'icon': config.get('icon', 'fas fa-cube'),
                'color': config.get('color', 'primary'),
                'order': config.get('order', 0),
                'is_default': True,
                'is_deletable': choice[0] != 'other',  # Other分类不可删除
                'is_selectable': True
            })
        
        # 添加动态分类
        for category in cls.objects.all():
            categories.append({
                'key': category.key,
                'label': category.label,
                'icon': category.icon,
                'color': category.color,
                'order': category.order,
                'is_default': False,
                'is_deletable': True,
                'is_selectable': category.is_selectable
            })
        
        # 按排序顺序排列
        categories.sort(key=lambda x: x['order'])
        return categories
    
    def delete_and_migrate_modules(self):
        """删除分类并将其中的模块迁移到Other分类"""
        from .models import ModuleItem  # 避免循环导入
        
        # 将该分类下的所有模块迁移到 'other' 分类
        affected_modules = ModuleItem.objects.filter(category=self.key)
        migrated_count = affected_modules.update(category='other')
        
        # 删除分类
        self.delete()
        
        return migrated_count
    
    @classmethod 
    def delete_category_and_migrate(cls, category_key):
        """删除指定分类并迁移模块"""
        from .models import ModuleItem  # 避免循环导入
        
        if category_key == 'other':
            raise ValueError("Other分类不能删除")
        
        # 检查是否为默认分类
        default_keys = [choice[0] for choice in ModuleCategory.choices if choice[0] != 'other']
        
        if category_key in default_keys:
            # 删除默认分类：将模块迁移到Other
            affected_modules = ModuleItem.objects.filter(category=category_key)
            migrated_count = affected_modules.update(category='other')
            return migrated_count
        else:
            # 删除自定义分类
            try:
                category = cls.objects.get(key=category_key)
                return category.delete_and_migrate_modules()
            except cls.DoesNotExist:
                return 0


class ModuleFile(models.Model):
    """
    Python模块文件记录
    """
    # 文件相关信息
    name = models.CharField(max_length=255, verbose_name="文件名")
    relative_path = models.CharField(max_length=500, verbose_name="相对路径")
    size = models.BigIntegerField(verbose_name="文件大小(字节)")
    
    # 文件状态
    status = models.CharField(
        max_length=20, 
        choices=FileStatus.choices, 
        default=FileStatus.UNREVIEWED,
        verbose_name="文件状态"
    )
    
    # 元数据
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="上传者")
    status_updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='status_updated_files',
        verbose_name="状态更新者"
    )
    status_updated_at = models.DateTimeField(null=True, blank=True, verbose_name="状态更新时间")
    
    # 文件内容缓存（可选）
    content_hash = models.CharField(max_length=64, blank=True, verbose_name="文件哈希")
    
    class Meta:
        verbose_name = "模块文件"
        verbose_name_plural = "模块文件"
        unique_together = ['relative_path']  # 确保路径唯一
        ordering = ['relative_path']
    
    def __str__(self):
        return f"{self.name} ({self.relative_path})"
    
    @property
    def absolute_path(self):
        """获取文件的绝对路径"""
        return settings.EOLO_ULTRALYTICS_WORKPIECES_DIR / self.relative_path
    
    @property
    def directory(self):
        """获取文件所在目录"""
        return Path(self.relative_path).parent
    
    @property
    def exists(self):
        """检查文件是否存在"""
        return self.absolute_path.exists()
    
    def read_content(self):
        """读取文件内容"""
        try:
            if self.exists:
                return self.absolute_path.read_text(encoding='utf-8')
            return ""
        except Exception as e:
            return f"# 读取文件失败: {str(e)}"
    
    def write_content(self, content):
        """写入文件内容"""
        try:
            # 确保目录存在
            self.absolute_path.parent.mkdir(parents=True, exist_ok=True)
            # 写入内容
            self.absolute_path.write_text(content, encoding='utf-8')
            # 更新文件大小
            self.size = self.absolute_path.stat().st_size
            self.save()
            return True, "文件保存成功"
        except Exception as e:
            return False, f"保存失败: {str(e)}"
    
    @property
    def status_icon(self):
        """获取状态图标"""
        status_icons = {
            FileStatus.UNREVIEWED: '⭕',
            FileStatus.AVAILABLE: '✔',
            FileStatus.UNAVAILABLE: '❌'
        }
        return status_icons.get(self.status, '⭕')
    
    @property
    def status_display(self):
        """获取状态显示文本"""
        return self.get_status_display()
    
    def update_status(self, new_status, user):
        """更新文件状态"""
        from django.utils import timezone
        self.status = new_status
        self.status_updated_by = user
        self.status_updated_at = timezone.now()
        self.save(update_fields=['status', 'status_updated_by', 'status_updated_at'])


class ModuleEditSession(models.Model):
    """
    模块编辑会话记录（用于防止并发编辑冲突）
    """
    module_file = models.ForeignKey(ModuleFile, on_delete=models.CASCADE, verbose_name="模块文件")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="编辑用户")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="开始时间")
    is_active = models.BooleanField(default=True, verbose_name="是否活跃")
    
    class Meta:
        verbose_name = "模块编辑会话"
        verbose_name_plural = "模块编辑会话"
        unique_together = ['module_file', 'user']
    
    def __str__(self):
        return f"{self.user.username} 编辑 {self.module_file.name}"


class ModuleItem(models.Model):
    """
    Python模块中的具体模块项（从__all__字段提取）
    """
    # 关联的模块文件
    module_file = models.ForeignKey(ModuleFile, on_delete=models.CASCADE, 
                                    related_name='module_items', verbose_name="模块文件")
    
    # 模块信息 - 使用字符串字段支持动态分类
    name = models.CharField(max_length=255, verbose_name="模块名称")
    category = models.CharField(max_length=50, default='other', verbose_name="模块分类")
    
    # 元数据
    description = models.TextField(blank=True, verbose_name="模块描述")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    classified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                      verbose_name="分类者")
    
    # 是否从__all__字段自动检测到
    auto_detected = models.BooleanField(default=True, verbose_name="自动检测")
    
    class Meta:
        verbose_name = "模块项"
        verbose_name_plural = "模块项"
        unique_together = ['module_file', 'name']  # 同一文件中模块名不能重复
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()}) - {self.module_file.name}"
    
    def get_category_display(self):
        """获取分类显示名称"""
        # 首先检查是否是默认分类
        for choice in ModuleCategory.choices:
            if choice[0] == self.category:
                return choice[1]
        
        # 检查动态分类
        try:
            dynamic_cat = DynamicModuleCategory.objects.get(key=self.category)
            return dynamic_cat.label
        except DynamicModuleCategory.DoesNotExist:
            return self.category.title()
    
    @property
    def file_path(self):
        """获取模块文件路径"""
        return self.module_file.relative_path


class CodeTemplate(models.Model):
    """
    代码模板类
    用于存储可重用的Python类代码片段
    """
    name = models.CharField(max_length=255, unique=True, verbose_name="模板名称")
    description = models.TextField(blank=True, verbose_name="模板描述")
    code_content = models.TextField(verbose_name="模板代码内容")
    
    # 元数据
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="创建者")
    
    # 使用统计
    usage_count = models.PositiveIntegerField(default=0, verbose_name="使用次数")
    
    class Meta:
        verbose_name = "代码模板"
        verbose_name_plural = "代码模板"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name}"
    
    def increment_usage(self):
        """增加使用次数"""
        self.usage_count += 1
        self.save(update_fields=['usage_count'])
    
    def get_placeholders(self):
        """获取模板中的占位符（???）列表"""
        import re
        placeholders = re.findall(r'\?\?\?(\w*)', self.code_content)
        return list(set(placeholders))  # 去重
    
    def apply_template(self, replacements):
        """
        应用模板，替换占位符
        replacements: dict，key为占位符名称，value为替换值
        """
        result = self.code_content
        
        # 替换简单的???占位符
        for placeholder, replacement in replacements.items():
            if placeholder == 'default':
                result = result.replace('???', replacement)
            else:
                result = result.replace(f'???{placeholder}', replacement)
        
        return result
