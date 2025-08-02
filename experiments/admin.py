from django.contrib import admin
from .models import Experiment, ExperimentLog


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    """
    实验管理界面
    """
    list_display = ('name', 'user', 'task_type', 'status', 'created_at', 'updated_at')
    list_filter = ('task_type', 'status', 'created_at', 'user')
    search_fields = ('name', 'description', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'command')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'description', 'user', 'task_type')
        }),
        ('模型配置', {
            'fields': ('model_name', 'data_path', 'device')
        }),
        ('训练参数', {
            'fields': ('epochs', 'batch_size', 'image_size', 'learning_rate', 'weight_decay', 'workers')
        }),
        ('输出配置', {
            'fields': ('project_name', 'experiment_name', 'save_dir')
        }),
        ('状态信息', {
            'fields': ('status', 'command', 'started_at', 'completed_at', 'error_message')
        }),
        ('文件信息', {
            'fields': ('log_file', 'result_file')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['generate_commands', 'mark_as_completed', 'mark_as_failed']
    
    def generate_commands(self, request, queryset):
        """批量生成命令"""
        count = 0
        for experiment in queryset:
            experiment.generate_command()
            experiment.save()
            count += 1
        self.message_user(request, f'已为 {count} 个实验生成命令')
    generate_commands.short_description = '生成命令'
    
    def mark_as_completed(self, request, queryset):
        """标记为已完成"""
        count = queryset.update(status='completed')
        self.message_user(request, f'已标记 {count} 个实验为完成状态')
    mark_as_completed.short_description = '标记为已完成'
    
    def mark_as_failed(self, request, queryset):
        """标记为失败"""
        count = queryset.update(status='failed')
        self.message_user(request, f'已标记 {count} 个实验为失败状态')
    mark_as_failed.short_description = '标记为失败'


@admin.register(ExperimentLog)
class ExperimentLogAdmin(admin.ModelAdmin):
    """
    实验日志管理界面
    """
    list_display = ('experiment', 'level', 'timestamp', 'message_preview')
    list_filter = ('level', 'timestamp', 'experiment__user')
    search_fields = ('message', 'experiment__name')
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)
    
    def message_preview(self, obj):
        """消息预览"""
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_preview.short_description = '消息预览'
