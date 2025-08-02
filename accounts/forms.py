# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """
    自定义用户注册表单 - 放开密码限制
    """
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': '邮箱地址（可选）'
        }),
        help_text='可选：用于密码重置等功能'
    )
    
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '请输入用户名'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 自定义字段属性
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '请输入用户名'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '请输入密码'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '请确认密码'
        })
        
        # 简化帮助文本
        self.fields['username'].help_text = '用户名不能重复'
        self.fields['password1'].help_text = '密码至少1个字符即可'
        self.fields['password2'].help_text = '请再次输入相同的密码进行确认'
    
    def clean_username(self):
        """
        只检查用户名是否重复
        """
        username = self.cleaned_data.get("username")
        if not username:
            raise forms.ValidationError("用户名不能为空")
        
        # 检查用户名是否已存在
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("该用户名已存在，请选择其他用户名")
        
        return username
    
    def clean_password1(self):
        """
        极简密码验证 - 只要求最少1个字符
        """
        password1 = self.cleaned_data.get("password1")
        if not password1:
            raise forms.ValidationError("密码不能为空")
        if len(password1) < 1:
            raise forms.ValidationError("密码至少需要1个字符")
        return password1
    
    def clean_password2(self):
        """
        确保两次密码输入一致
        """
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("两次输入的密码不一致")
        return password2
    
    def save(self, commit=True):
        """
        保存用户，完全绕过Django默认的密码验证
        """
        user = super(UserCreationForm, self).save(commit=False)  # 跳过UserCreationForm的save方法
        user.set_password(self.cleaned_data["password1"])  # 直接设置密码
        if self.cleaned_data.get('email'):
            user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """
    自定义登录表单 - 增强样式
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['username'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': '请输入用户名',
            'autofocus': True
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': '请输入密码'
        })
        
        # 删除帮助文本
        self.fields['username'].help_text = None
        self.fields['password'].help_text = None
