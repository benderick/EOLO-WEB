from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    自定义用户管理界面
    """
    list_display = ('username', 'email', 'first_name', 'last_name', 'phone', 'department', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined', 'department')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone')
    ordering = ('-date_joined',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('额外信息', {'fields': ('phone', 'department')}),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('额外信息', {'fields': ('phone', 'department')}),
    )
