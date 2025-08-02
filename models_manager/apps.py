"""
模型管理器应用配置
"""
from django.apps import AppConfig


class ModelsManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'models_manager'
    verbose_name = '模型配置管理'
