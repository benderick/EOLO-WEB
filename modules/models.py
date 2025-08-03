"""
模块管理相关的数据模型
"""
from django.db import models
from django.contrib.auth import get_user_model
from pathlib import Path
from django.conf import settings

User = get_user_model()


class ModuleFile(models.Model):
    """
    Python模块文件记录
    """
    # 文件相关信息
    name = models.CharField(max_length=255, verbose_name="文件名")
    relative_path = models.CharField(max_length=500, verbose_name="相对路径")
    size = models.BigIntegerField(verbose_name="文件大小(字节)")
    
    # 元数据
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="上传者")
    
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


class ModuleEditSession(models.Model):
    """
    模块编辑会话记录（用于防止并发编辑冲突）
    """
    module_file = models.ForeignKey(ModuleFile, on_delete=models.CASCADE, verbose_name="模块文件")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="编辑用户")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="开始时间")
    last_activity = models.DateTimeField(auto_now=True, verbose_name="最后活动时间")
    is_active = models.BooleanField(default=True, verbose_name="是否活跃")
    
    class Meta:
        verbose_name = "编辑会话"
        verbose_name_plural = "编辑会话"
        unique_together = ['module_file', 'user']
    
    def __str__(self):
        return f"{self.user.username} 编辑 {self.module_file.name}"
