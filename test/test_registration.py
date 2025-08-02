#!/usr/bin/env python3
"""
测试用户注册功能 - 验证简化的密码要求
"""
import os
import sys
import django

# 设置Django环境
sys.path.append('/icislab/volume3/benderick/futurama/EOLO-WEB')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eolo_web.settings')
django.setup()

from accounts.forms import CustomUserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()

def test_user_registration():
    """测试用户注册功能"""
    print("=== 测试用户注册功能 ===")
    
    # 测试1: 简单密码（1个字符）
    print("\n1. 测试1个字符的密码:")
    form_data = {
        'username': 'testuser1',
        'password1': '1',
        'password2': '1',
        'email': 'test1@example.com'
    }
    form = CustomUserCreationForm(data=form_data)
    if form.is_valid():
        print("✅ 1个字符的密码验证通过")
        try:
            user = form.save()
            print(f"✅ 用户 {user.username} 创建成功")
            user.delete()  # 清理测试数据
        except Exception as e:
            print(f"❌ 保存用户失败: {str(e)}")
    else:
        print("❌ 1个字符的密码验证失败:")
        for field, errors in form.errors.items():
            print(f"  {field}: {errors}")
    
    # 测试2: 常见密码
    print("\n2. 测试常见密码 'password':")
    form_data = {
        'username': 'testuser2',
        'password1': 'password',
        'password2': 'password',
        'email': 'test2@example.com'
    }
    form = CustomUserCreationForm(data=form_data)
    if form.is_valid():
        print("✅ 常见密码验证通过")
        try:
            user = form.save()
            print(f"✅ 用户 {user.username} 创建成功")
            user.delete()  # 清理测试数据
        except Exception as e:
            print(f"❌ 保存用户失败: {str(e)}")
    else:
        print("❌ 常见密码验证失败:")
        for field, errors in form.errors.items():
            print(f"  {field}: {errors}")
    
    # 测试3: 纯数字密码
    print("\n3. 测试纯数字密码 '123456':")
    form_data = {
        'username': 'testuser3',
        'password1': '123456',
        'password2': '123456',
        'email': 'test3@example.com'
    }
    form = CustomUserCreationForm(data=form_data)
    if form.is_valid():
        print("✅ 纯数字密码验证通过")
        try:
            user = form.save()
            print(f"✅ 用户 {user.username} 创建成功")
            user.delete()  # 清理测试数据
        except Exception as e:
            print(f"❌ 保存用户失败: {str(e)}")
    else:
        print("❌ 纯数字密码验证失败:")
        for field, errors in form.errors.items():
            print(f"  {field}: {errors}")
    
    # 测试4: 重复用户名
    print("\n4. 测试重复用户名:")
    # 先创建一个用户
    user1 = User.objects.create_user(username='duplicate_test', password='test123')
    
    form_data = {
        'username': 'duplicate_test',  # 重复的用户名
        'password1': 'anypassword',
        'password2': 'anypassword',
        'email': 'test4@example.com'
    }
    form = CustomUserCreationForm(data=form_data)
    if form.is_valid():
        print("❌ 重复用户名验证应该失败但通过了")
    else:
        print("✅ 重复用户名验证正确失败:")
        for field, errors in form.errors.items():
            print(f"  {field}: {errors}")
    
    # 清理测试数据
    user1.delete()
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_user_registration()
