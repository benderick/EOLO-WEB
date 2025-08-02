from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from .models import User
from .forms import CustomUserCreationForm, CustomAuthenticationForm


class CustomLoginView(LoginView):
    """
    自定义登录视图
    """
    template_name = 'accounts/login.html'
    form_class = CustomAuthenticationForm
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('experiments:dashboard')


class CustomLogoutView(LogoutView):
    """
    自定义登出视图
    """
    next_page = reverse_lazy('accounts:login')


def register_view(request):
    """
    用户注册视图
    """
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'账户 {username} 创建成功！欢迎加入EOLO-WEB！')
            # 自动登录新注册的用户
            new_user = authenticate(username=username, password=form.cleaned_data.get('password1'))
            if new_user is not None:
                login(request, new_user)
                return redirect('experiments:dashboard')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile_view(request):
    """
    用户个人资料视图
    """
    user = request.user
    
    # 计算实验统计信息
    total_experiments = user.experiment_set.count()
    completed_experiments = user.experiment_set.filter(status='completed').count()
    running_experiments = user.experiment_set.filter(status='running').count()
    
    # 获取最近的实验
    recent_experiments = user.experiment_set.all()[:5]
    
    context = {
        'user': user,
        'total_experiments': total_experiments,
        'completed_experiments': completed_experiments,
        'running_experiments': running_experiments,
        'recent_experiments': recent_experiments,
    }
    
    return render(request, 'accounts/profile.html', context)
