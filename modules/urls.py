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
]
