from django.urls import path
from . import views

app_name = 'experiments'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('list/', views.experiment_list_view, name='list'),
    path('create/', views.experiment_create_view, name='create'),
    path('<int:pk>/', views.experiment_detail_view, name='detail'),
    path('<int:pk>/edit/', views.experiment_edit_view, name='edit'),
    path('<int:pk>/start/', views.experiment_start_view, name='start'),
    path('<int:pk>/stop/', views.experiment_stop_view, name='stop'),
    path('<int:pk>/restart/', views.experiment_restart_view, name='restart'),
    path('<int:pk>/delete/', views.experiment_delete_view, name='delete'),
    path('<int:pk>/command/', views.get_experiment_command, name='command'),
    
    # GPU状态API
    path('gpu-status/', views.gpu_status_view, name='gpu_status'),
    path('gpu-status-json/', views.gpu_status_json_view, name='gpu_status_json'),
    
    # 实验监控API
    path('<int:pk>/status-api/', views.experiment_status_api, name='status_api'),
    path('<int:pk>/logs-api/', views.experiment_logs_api, name='logs_api'),
    path('running-api/', views.running_experiments_api, name='running_api'),
    
    # 队列管理API
    path('<int:pk>/queue/', views.experiment_queue_view, name='queue'),
    path('queue-status/', views.queue_status_api, name='queue_status'),
]
