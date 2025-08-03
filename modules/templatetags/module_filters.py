"""
模块管理自定义模板过滤器
"""
from django import template

register = template.Library()


@register.filter
def mul(value, arg):
    """乘法过滤器"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def get_item(dictionary, key):
    """从字典中获取项目"""
    return dictionary.get(key)
