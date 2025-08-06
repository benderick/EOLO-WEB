# Generated manually for category system refactoring

from django.db import migrations

def migrate_fixed_categories_to_db(apps, schema_editor):
    """
    将固定的模块分类迁移到数据库中
    确保所有分类都从数据库动态获取
    """
    DynamicModuleCategory = apps.get_model('modules', 'DynamicModuleCategory')
    User = apps.get_model('accounts', 'User')  # 使用自定义的User模型
    
    # 获取系统管理员用户（如果没有则创建）
    admin_user = None
    try:
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            # 创建系统用户作为默认创建者
            admin_user = User.objects.create_user(
                username='system',
                email='system@eolo.com',
                is_staff=True,
                is_superuser=True
            )
    except Exception:
        # 如果无法创建用户，使用ID为1的用户
        admin_user = User.objects.filter(id=1).first()
    
    if not admin_user:
        print("警告：无法找到管理员用户，跳过分类迁移")
        return
    
    # 定义固定分类的完整配置
    fixed_categories = [
        {
            'key': 'attention',
            'label': 'Attention',
            'description': 'Attention机制相关模块，用于实现注意力机制的网络层',
            'icon': 'fas fa-eye',
            'color': 'info',
            'order': 10,
            'is_default': True,
            'is_selectable': True
        },
        {
            'key': 'convolution',
            'label': 'Convolution',
            'description': '卷积层相关模块，包含各种卷积操作和卷积网络结构',
            'icon': 'fas fa-filter',
            'color': 'primary',
            'order': 20,
            'is_default': True,
            'is_selectable': True
        },
        {
            'key': 'downsample',
            'label': 'Downsample',
            'description': '下采样模块，用于降低特征图分辨率的网络层',
            'icon': 'fas fa-compress-arrows-alt',
            'color': 'warning',
            'order': 30,
            'is_default': True,
            'is_selectable': True
        },
        {
            'key': 'fusion',
            'label': 'Fusion',
            'description': '特征融合模块，用于合并不同层次或不同来源的特征',
            'icon': 'fas fa-project-diagram',
            'color': 'success',
            'order': 40,
            'is_default': True,
            'is_selectable': True
        },
        {
            'key': 'head',
            'label': 'Head',
            'description': '网络头部模块，用于最终的分类、检测或分割输出',
            'icon': 'fas fa-brain',
            'color': 'danger',
            'order': 50,
            'is_default': True,
            'is_selectable': True
        },
        {
            'key': 'block',
            'label': 'Block',
            'description': '基础模块块，可复用的网络结构单元',
            'icon': 'fas fa-th-large',
            'color': 'secondary',
            'order': 60,
            'is_default': True,
            'is_selectable': True
        },
        {
            'key': 'other',
            'label': 'Other',
            'description': '其他未分类的模块，兜底分类',
            'icon': 'fas fa-cube',
            'color': 'dark',
            'order': 999,
            'is_default': True,
            'is_selectable': True
        }
    ]
    
    # 创建或更新固定分类
    created_count = 0
    updated_count = 0
    
    for category_data in fixed_categories:
        category, created = DynamicModuleCategory.objects.get_or_create(
            key=category_data['key'],
            defaults={
                'label': category_data['label'],
                'description': category_data['description'],
                'icon': category_data['icon'],
                'color': category_data['color'],
                'is_default': category_data['is_default'],
                'is_selectable': category_data['is_selectable'],
                'order': category_data['order'],
                'created_by': admin_user
            }
        )
        
        if created:
            created_count += 1
            print(f"✓ 创建固定分类: {category.label} ({category.key})")
        else:
            # 更新现有分类的默认属性
            updated = False
            if not category.is_default:
                category.is_default = True
                updated = True
            if category.description != category_data['description']:
                category.description = category_data['description']
                updated = True
            if category.icon != category_data['icon']:
                category.icon = category_data['icon']
                updated = True
            if category.color != category_data['color']:
                category.color = category_data['color']
                updated = True
            if category.order != category_data['order']:
                category.order = category_data['order']
                updated = True
                
            if updated:
                category.save()
                updated_count += 1
                print(f"✓ 更新固定分类: {category.label} ({category.key})")
    
    print(f"✅ 分类迁移完成: 创建 {created_count} 个，更新 {updated_count} 个")

def reverse_migrate_fixed_categories(apps, schema_editor):
    """
    反向迁移：删除迁移的固定分类（保留用户自定义分类）
    """
    DynamicModuleCategory = apps.get_model('modules', 'DynamicModuleCategory')
    
    # 删除is_default=True的分类（固定分类）
    fixed_keys = ['attention', 'convolution', 'downsample', 'fusion', 'head', 'block', 'other']
    deleted_count = DynamicModuleCategory.objects.filter(
        key__in=fixed_keys,
        is_default=True
    ).delete()[0]
    
    print(f"✅ 反向迁移完成: 删除 {deleted_count} 个固定分类")


class Migration(migrations.Migration):

    dependencies = [
        ('modules', '0006_alter_dynamicmodulecategory_options_and_more'),
    ]

    operations = [
        migrations.RunPython(
            migrate_fixed_categories_to_db,
            reverse_migrate_fixed_categories
        ),
    ]
