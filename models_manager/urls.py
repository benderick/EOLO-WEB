"""
模型管理器URL配置
"""
from django.urls import path
from . import views

app_name = 'models_manager'

urlpatterns = [
    # 主页面
    path('', views.model_manager_view, name='model_manager'),
    
    # 模型配置API接口
    path('api/tree/', views.get_model_tree, name='api_tree'),
    path('api/file/', views.file_content_api, name='api_file'),
    path('api/operation/', views.file_operation_api, name='api_operation'),
    path('api/create/', views.create_file_api, name='api_create'),
    path('api/test/', views.ModelTestAPIView.as_view(), name='api_test'),
    
    # 模板配置API接口
    path('api/templates/tree/', views.TemplateTreeAPIView.as_view(), name='api_templates_tree'),
    path('api/templates/file/', views.TemplateFileContentAPIView.as_view(), name='api_templates_file'),
    path('api/templates/operation/', views.TemplateOperationAPIView.as_view(), name='api_templates_operation'),
    path('api/templates/create/', views.TemplateCreateFileAPIView.as_view(), name='api_templates_create'),
    
    # 参数配置API接口
    path('api/settings/tree/', views.SettingTreeAPIView.as_view(), name='api_settings_tree'),
    path('api/settings/file/', views.SettingFileContentAPIView.as_view(), name='api_settings_file'),
    path('api/settings/operation/', views.SettingOperationAPIView.as_view(), name='api_settings_operation'),
    path('api/settings/create/', views.SettingCreateFileAPIView.as_view(), name='api_settings_create'),
]
