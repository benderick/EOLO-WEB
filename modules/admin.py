"""
模块管理 Django Admin 配置
"""
from django.contrib import admin
from .models import ModuleFile, ModuleEditSession, ModuleItem


@admin.register(ModuleFile)
class ModuleFileAdmin(admin.ModelAdmin):
    """模块文件管理"""
    list_display = ('name', 'relative_path', 'size', 'uploaded_by', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at', 'uploaded_by')
    search_fields = ('name', 'relative_path')
    readonly_fields = ('content_hash', 'created_at', 'updated_at')
    ordering = ['relative_path']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'relative_path', 'size')
        }),
        ('元数据', {
            'fields': ('uploaded_by', 'content_hash', 'created_at', 'updated_at')
        }),
    )


@admin.register(ModuleEditSession)
class ModuleEditSessionAdmin(admin.ModelAdmin):
    """编辑会话管理"""
    list_display = ('module_file', 'user', 'started_at', 'is_active')
    list_filter = ('is_active', 'started_at')
    search_fields = ('module_file__name', 'user__username')
    readonly_fields = ('started_at',)
    ordering = ['-started_at']


@admin.register(ModuleItem)
class ModuleItemAdmin(admin.ModelAdmin):
    """模块项管理"""
    list_display = ('name', 'category', 'module_file', 'auto_detected', 'classified_by', 'updated_at')
    list_filter = ('category', 'auto_detected', 'created_at', 'updated_at')
    search_fields = ('name', 'module_file__name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ['category', 'name']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'module_file', 'category')
        }),
        ('详细信息', {
            'fields': ('description', 'auto_detected', 'classified_by')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at')
        }),
    )
