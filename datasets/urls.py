from django.urls import path
from . import views

app_name = 'datasets'

urlpatterns = [
    path('', views.dataset_list_view, name='list'),
    path('stats/', views.dataset_stats_view, name='stats'),
    path('api/search/', views.dataset_search_api, name='search_api'),
    path('<str:name>/', views.dataset_detail_view, name='detail'),
    path('<str:name>/info/', views.dataset_info_api, name='info'),
    path('<str:name>/validate/', views.dataset_validate_api, name='validate'),
    path('<str:name>/download/', views.dataset_download_yaml, name='download'),
    path('api/<str:name>/', views.dataset_api_view, name='api'),
]
