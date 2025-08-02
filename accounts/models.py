from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    扩展用户模型，添加额外的用户信息
    """
    # 可以在这里添加额外的用户字段
    phone = models.CharField(max_length=15, blank=True, null=True, verbose_name="电话号码")
    department = models.CharField(max_length=100, blank=True, null=True, verbose_name="部门")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"
        
    def __str__(self):
        return self.username
