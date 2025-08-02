"""
实验表单自定义组件
"""
from django import forms
from django.forms.widgets import CheckboxSelectMultiple
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .gpu_utils import check_gpu_memory_usage


class GPUStatusCheckboxSelectMultiple(CheckboxSelectMultiple):
    """
    显示GPU状态的多选框组件
    """
    
    def __init__(self, attrs=None):
        super().__init__(attrs)
        self.gpu_status = {}
        self._load_gpu_status()
    
    def _load_gpu_status(self):
        """
        加载GPU状态信息
        """
        try:
            gpu_usage = check_gpu_memory_usage()
            for gpu_id, usage_info in gpu_usage.items():
                memory_percent = usage_info.get('memory_used_percent', 0)
                self.gpu_status[str(gpu_id)] = {
                    'memory_percent': memory_percent,
                    'memory_used': usage_info.get('memory_used', 0) / 1024,  # 转换为GB
                    'memory_total': usage_info.get('memory_total', 0) / 1024,  # 转换为GB
                    'is_available': memory_percent < 20  # 20%以下视为可用
                }
        except Exception:
            # 如果获取失败，设置默认状态
            for i in range(6):
                self.gpu_status[str(i)] = {
                    'memory_percent': 0,
                    'memory_used': 0,
                    'memory_total': 0,
                    'is_available': True
                }

    def render(self, name, value, attrs=None, renderer=None):
        """
        完全自定义渲染方法，生成两列布局的GPU选择器
        """
        # 重新加载GPU状态
        self._load_gpu_status()
        
        # 确保value是列表
        if value is None:
            value = []
        elif isinstance(value, str):
            # 处理Django保存的字符串格式如 "[0,1]"
            if value.startswith('[') and value.endswith(']'):
                value = value[1:-1]
                if value:
                    value = [x.strip().strip('"').strip("'") for x in value.split(',')]
                else:
                    value = []
            else:
                value = [value] if value else []
        
        # 获取GPU选项
        if hasattr(self, 'choices'):
            choices = list(self.choices)
        else:
            # 默认GPU选项
            choices = [(str(i), f"GPU {i}") for i in range(6)]
            
        # 生成每个GPU选项的HTML
        gpu_options_html = []
        for option_value, option_label in choices:
            gpu_id = str(option_value)
            is_selected = str(option_value) in [str(v) for v in value]
            
            # 获取GPU状态
            gpu_info = self.gpu_status.get(gpu_id, {
                'memory_percent': 0,
                'memory_used': 0,
                'memory_total': 0,
                'is_available': True
            })
            
            memory_percent = gpu_info['memory_percent']
            memory_used = gpu_info['memory_used']
            memory_total = gpu_info['memory_total']
            is_available = gpu_info['is_available']
            
            # 状态信息
            if is_available:
                status_text = "可用"
                status_color = "success"
                status_icon = "🟢"
            elif memory_percent < 50:
                status_text = "部分使用"
                status_color = "warning"
                status_icon = "🟡"
            else:
                status_text = "繁忙"
                status_color = "danger"
                status_icon = "🔴"
            
            memory_info = f"{memory_used:.1f}GB / {memory_total:.1f}GB"
            
            # 背景颜色
            bg_color = 'rgba(40, 167, 69, 0.1)' if is_available else ('rgba(255, 193, 7, 0.1)' if memory_percent < 50 else 'rgba(220, 53, 69, 0.1)')
            border_color = 'rgba(40, 167, 69, 0.3)' if is_available else ('rgba(255, 193, 7, 0.3)' if memory_percent < 50 else 'rgba(220, 53, 69, 0.3)')
            
            # 生成单个GPU选项的HTML
            gpu_option_html = f'''
            <div class="gpu-option d-flex align-items-center justify-content-between p-3 border rounded mb-2" 
                 style="background-color: {bg_color}; border-color: {border_color}; width: 100%; min-height: 85px; box-sizing: border-box;">
                <div class="d-flex align-items-center" style="flex: 1;">
                    <div class="form-check-input-wrapper me-3">
                        <input type="checkbox" name="{name}" value="{option_value}" 
                               id="id_{name}_{option_value}" 
                               {'checked' if is_selected else ''}
                               style="transform: scale(1.3);" />
                    </div>
                    <div style="flex: 1;">
                        <strong style="font-size: 1.1em;">GPU {gpu_id}</strong>
                        <div class="small text-muted mt-1">{memory_info}</div>
                    </div>
                </div>
                <div class="text-end" style="flex-shrink: 0;">
                    <span class="badge bg-{status_color} mb-2" style="font-size: 0.85em;">{status_icon} {status_text} {memory_percent:.1f}%</span>
                    <div class="progress" style="width: 100px; height: 10px;">
                        <div class="progress-bar bg-{status_color}" style="width: {memory_percent:.1f}%"></div>
                    </div>
                    <div class="small text-muted mt-1">{memory_percent:.1f}% 使用中</div>
                </div>
            </div>
            '''
            gpu_options_html.append(gpu_option_html)
        
        # 将所有GPU选项组织成两列布局
        main_html = f'''
        <div class="gpu-status-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 10px 0;">
            {''.join(gpu_options_html)}
            <div class="gpu-refresh-status" style="font-size: 0.75em; color: #6c757d; margin-top: 10px; text-align: center; grid-column: 1 / -1;">
                <i class="bi bi-arrow-clockwise"></i> GPU状态每30秒自动更新
            </div>
        </div>
        '''
        
        # 添加样式和脚本
        extra_html = '''
        <style>
        .gpu-option {
            transition: all 0.2s ease;
            cursor: pointer;
        }
        .gpu-option:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .form-check-input-wrapper {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
        }
        .gpu-status-container .progress {
            border-radius: 5px;
            overflow: hidden;
        }
        .gpu-status-container .progress-bar {
            transition: width 0.3s ease;
        }
        </style>
        <script>
        let gpuStatusUpdateInterval;
        
        function updateGPUStatus() {
            fetch('/experiments/gpu-status-json/')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        console.log('GPU状态已更新:', data);
                        document.querySelector('.gpu-refresh-status').innerHTML = 
                            '<i class="bi bi-check-circle text-success"></i> 最后更新: ' + 
                            new Date(data.timestamp).toLocaleTimeString();
                    } else {
                        console.error('更新GPU状态失败:', data.error);
                        document.querySelector('.gpu-refresh-status').innerHTML = 
                            '<i class="bi bi-exclamation-triangle text-warning"></i> 更新失败，请刷新页面';
                    }
                })
                .catch(error => {
                    console.error('网络错误:', error);
                    document.querySelector('.gpu-refresh-status').innerHTML = 
                        '<i class="bi bi-wifi-off text-danger"></i> 网络连接错误';
                });
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            // 立即执行一次更新
            setTimeout(updateGPUStatus, 1000);
            
            // 设置定时更新
            gpuStatusUpdateInterval = setInterval(updateGPUStatus, 30000);
            
            // 页面卸载时清理定时器
            window.addEventListener('beforeunload', function() {
                if (gpuStatusUpdateInterval) {
                    clearInterval(gpuStatusUpdateInterval);
                }
            });
            
            // 当用户点击GPU选项时的交互效果
            document.querySelectorAll('.gpu-option').forEach(function(option) {
                option.addEventListener('click', function(e) {
                    // 如果点击的不是checkbox，则触发checkbox点击
                    if (e.target.type !== 'checkbox') {
                        const checkbox = this.querySelector('input[type="checkbox"]');
                        if (checkbox) {
                            checkbox.checked = !checkbox.checked;
                            checkbox.dispatchEvent(new Event('change'));
                        }
                    }
                });
            });
        });
        </script>
        '''
        
        return mark_safe(main_html + extra_html)

    def format_value(self, value):
        """
        格式化值
        """
        if value is None:
            return []
        if isinstance(value, str):
            # 处理 "[0,1,2]" 格式的字符串
            if value.startswith('[') and value.endswith(']'):
                value = value[1:-1]
                if value:
                    return [x.strip().strip('"').strip("'") for x in value.split(',')]
            return []
        return value
