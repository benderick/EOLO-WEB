"""
模块管理URL配置
"""
from django.urls import path
from . import views

app_name = 'modules'

urlpatterns = [
    # 模块列表页面
    path('', views.modules_list_view, name='list'),
    
    # 文件编辑器
    path('edit/<path:path>/', views.module_file_view, name='edit'),
    path('file/<path:path>/', views.module_file_view, name='file'),  # 保持向后兼容
    
    # API接口
    path('api/save/', views.save_module_file, name='save_file'),
    path('api/upload/', views.upload_module_file, name='upload_file'),
    path('api/delete/', views.delete_module_file, name='delete_file'),
    path('api/tree/', views.module_file_tree_api, name='file_tree_api'),
    path('api/close-session/', views.close_edit_session, name='close_session'),
    path('api/enter-edit/', views.enter_edit_mode, name='enter_edit'),
    path('api/test-python/', views.test_python_file, name='test_python'),
    path('api/update-file-status/', views.update_file_status_api, name='update_file_status'),
    
    # 模块管理API
    path('api/scan-modules/', views.scan_modules_api, name='scan_modules'),
    path('api/classify-module/', views.classify_module_api, name='classify_module'),
    path('api/modules-by-category/', views.get_modules_by_category_api, name='modules_by_category'),
    path('api/analyze-file/', views.analyze_file_api, name='analyze_file'),
    
    # 分类管理API（仅管理员）
    path('api/manage-categories/', views.manage_categories_api, name='manage_categories'),
    
    # Base模板API
    path('api/base-templates/', views.get_base_templates_api, name='base_templates'),
    
    # 执行模型配置命令API
    path('api/execute-config/', views.execute_model_config_api, name='execute_config'),
    
    # 模板类管理API
    path('api/templates/', views.templates_list_api, name='templates_list'),
    path('api/templates/create/', views.create_template_api, name='create_template'),
    path('api/templates/update/', views.update_template_api, name='update_template'),
    path('api/templates/delete/', views.delete_template_api, name='delete_template'),
    path('api/templates/usage/', views.update_template_usage_api, name='update_template_usage'),
]
