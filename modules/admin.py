"""
模块管理 Django Admin 配置
"""
from django.contrib import admin
from .models import ModuleFile, ModuleEditSession, ModuleItem, DynamicModuleCategory


@admin.register(DynamicModuleCategory)
class DynamicModuleCategoryAdmin(admin.ModelAdmin):
    """动态模块分类管理（仅管理员可见）"""
    list_display = ('key', 'label', 'description', 'is_default', 'created_by', 'created_at')
    list_filter = ('is_default', 'created_at', 'created_by')
    search_fields = ('key', 'label', 'description')
    readonly_fields = ('created_at', 'created_by')
    ordering = ['key']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('key', 'label', 'description')
        }),
        ('元数据', {
            'fields': ('is_default', 'created_by', 'created_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """保存时自动设置创建者"""
        if not change:  # 仅在创建时设置
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_module_permission(self, request):
        """只有管理员可以访问此模块"""
        return request.user.is_superuser
    
    def has_view_permission(self, request, obj=None):
        """只有管理员可以查看"""
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        """只有管理员可以添加"""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """只有管理员可以修改"""
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """只有管理员可以删除"""
        return request.user.is_superuser


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
