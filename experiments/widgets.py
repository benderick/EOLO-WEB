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
        
        # 处理value - 确保它是一个列表
        if value is None:
            value = []
        elif isinstance(value, str):
            if value.startswith('[') and value.endswith(']'):
                value = value[1:-1]
                if value:
                    value = [x.strip().strip('"').strip("'") for x in value.split(',')]
                else:
                    value = []
            else:
                value = [value] if value else []
        elif not isinstance(value, (list, tuple)):
            value = [str(value)]
        
        # 确保value中的所有元素都是字符串
        value = [str(v) for v in value if v is not None]
        
        # 获取GPU选项 - 根据实际检测到的GPU数量
        if hasattr(self, 'choices'):
            choices = list(self.choices)
        else:
            # 根据GPU状态动态生成选项
            choices = []
            for gpu_id in sorted(self.gpu_status.keys(), key=int):
                choices.append((gpu_id, f"GPU {gpu_id}"))
            
            # 如果没有检测到GPU，使用默认的4个
            if not choices:
                choices = [(str(i), f"GPU {i}") for i in range(4)]
            
        # 生成每个GPU选项的HTML
        gpu_options_html = []
        for option_value, option_label in choices:
            gpu_id = str(option_value)
            is_selected = gpu_id in value
            
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
            
            # 背景颜色 - 选中状态有不同的样式
            if is_selected:
                # 选中状态：更明显的边框和背景
                if is_available:
                    bg_color = 'rgba(40, 167, 69, 0.25)'  # 更深的绿色
                    border_color = 'rgba(40, 167, 69, 0.6)'
                    border_width = '2px'
                elif memory_percent < 50:
                    bg_color = 'rgba(255, 193, 7, 0.25)'
                    border_color = 'rgba(255, 193, 7, 0.6)'
                    border_width = '2px'
                else:
                    bg_color = 'rgba(220, 53, 69, 0.25)'
                    border_color = 'rgba(220, 53, 69, 0.6)'
                    border_width = '2px'
            else:
                # 未选中状态：淡一些的颜色
                if is_available:
                    bg_color = 'rgba(40, 167, 69, 0.1)'
                    border_color = 'rgba(40, 167, 69, 0.3)'
                    border_width = '1px'
                elif memory_percent < 50:
                    bg_color = 'rgba(255, 193, 7, 0.1)'
                    border_color = 'rgba(255, 193, 7, 0.3)'
                    border_width = '1px'
                else:
                    bg_color = 'rgba(220, 53, 69, 0.1)'
                    border_color = 'rgba(220, 53, 69, 0.3)'
                    border_width = '1px'
            
            # 设置checkbox的属性
            checkbox_id = f"id_{name}_{gpu_id}"
            checkbox_attrs = f'id="{checkbox_id}" name="{name}" value="{gpu_id}"'
            if is_selected:
                checkbox_attrs += ' checked="checked"'
            
            # 生成单个GPU选项的HTML
            gpu_option_html = f'''
            <div class="gpu-option border rounded {'selected' if is_selected else ''}" 
                 style="background-color: {bg_color}; border-color: {border_color}; border-width: {border_width}; width: 100%; min-height: 90px; box-sizing: border-box; margin: 0; overflow: hidden; padding: 12px; display: flex; flex-direction: column; position: relative;">
                {f'<div class="selection-indicator" style="position: absolute; top: 8px; right: 8px; width: 20px; height: 20px; background-color: #28a745; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: bold;">✓</div>' if is_selected else ''}
                <div class="d-flex align-items-center justify-content-between mb-2">
                    <div style="flex: 1; min-width: 0;">
                        <input type="checkbox" {checkbox_attrs} style="opacity: 0; position: absolute; pointer-events: none;" />
                        <strong style="font-size: 1.1em; white-space: nowrap; color: {'#155724' if is_selected else 'inherit'};">GPU {gpu_id}</strong>
                    </div>
                    <div style="flex-shrink: 0; margin-right: {'25px' if is_selected else '0'};">
                        <span class="badge bg-{status_color}" style="font-size: 0.75em; white-space: nowrap;">{status_icon} {status_text}</span>
                    </div>
                </div>
                <div class="d-flex align-items-center justify-content-between">
                    <div style="flex: 1; min-width: 0;">
                        <div class="small text-muted" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: {'#6c757d' if not is_selected else '#495057'};">{memory_info}</div>
                    </div>
                    <div style="flex-shrink: 0; margin-left: 10px;">
                        <div class="progress" style="width: 70px; height: 6px; margin-bottom: 2px;">
                            <div class="progress-bar bg-{status_color}" style="width: {memory_percent:.1f}%"></div>
                        </div>
                        <div class="small text-muted text-end" style="font-size: 0.65em; color: {'#6c757d' if not is_selected else '#495057'};">{memory_percent:.1f}%</div>
                    </div>
                </div>
            </div>
            '''
            gpu_options_html.append(gpu_option_html)
        
        # 将所有GPU选项组织成两列布局
        main_html = f'''
        <div class="gpu-status-container" style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 10px 0; max-width: 100%; overflow: hidden;">
            {''.join(gpu_options_html)}
        </div>
        <div class="gpu-refresh-status" style="font-size: 0.75em; color: #6c757d; margin-top: 10px; text-align: center; grid-column: span 2;">
            <i class="bi bi-arrow-clockwise"></i> GPU状态每30秒自动更新
        </div>
        '''
        
        # 添加样式和脚本
        extra_html = '''
        <style>
        .gpu-status-container {
            max-width: 100%;
            box-sizing: border-box;
        }
        .gpu-option {
            transition: all 0.3s ease;
            cursor: pointer;
            max-width: 100%;
            box-sizing: border-box;
        }
        .gpu-option:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .gpu-option.selected {
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(0,0,0,0.2);
        }
        .gpu-option.selected:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.25);
        }
        .gpu-option input[type="checkbox"] {
            cursor: pointer;
            pointer-events: auto;
        }
        .gpu-status-container .progress {
            border-radius: 3px;
            overflow: hidden;
        }
        .gpu-status-container .progress-bar {
            transition: width 0.3s ease;
        }
        .gpu-refresh-status {
            grid-column: 1 / -1;
            text-align: center;
            margin-top: 15px;
        }
        .selection-indicator {
            animation: fadeIn 0.3s ease-in-out;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: scale(0.5); }
            to { opacity: 1; transform: scale(1); }
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
                        const statusElement = document.querySelector('.gpu-refresh-status');
                        if (statusElement) {
                            statusElement.innerHTML = 
                                '<i class="bi bi-check-circle text-success"></i> 最后更新: ' + 
                                new Date(data.timestamp).toLocaleTimeString();
                        }
                    } else {
                        console.error('更新GPU状态失败:', data.error);
                        const statusElement = document.querySelector('.gpu-refresh-status');
                        if (statusElement) {
                            statusElement.innerHTML = 
                                '<i class="bi bi-exclamation-triangle text-warning"></i> 更新失败，请刷新页面';
                        }
                    }
                })
                .catch(error => {
                    console.error('网络错误:', error);
                    const statusElement = document.querySelector('.gpu-refresh-status');
                    if (statusElement) {
                        statusElement.innerHTML = 
                            '<i class="bi bi-wifi-off text-danger"></i> 网络连接错误';
                    }
                });
        }
        
        function updateGPUSelection(option, checkbox) {
            const isSelected = checkbox.checked;
            const indicator = option.querySelector('.selection-indicator');
            const gpuTitle = option.querySelector('strong');
            
            if (isSelected) {
                option.classList.add('selected');
                if (!indicator) {
                    // 添加选中指示器
                    const newIndicator = document.createElement('div');
                    newIndicator.className = 'selection-indicator';
                    newIndicator.style.cssText = 'position: absolute; top: 8px; right: 8px; width: 20px; height: 20px; background-color: #28a745; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: bold;';
                    newIndicator.textContent = '✓';
                    option.appendChild(newIndicator);
                }
                if (gpuTitle) {
                    gpuTitle.style.color = '#155724';
                }
            } else {
                option.classList.remove('selected');
                if (indicator) {
                    indicator.remove();
                }
                if (gpuTitle) {
                    gpuTitle.style.color = 'inherit';
                }
            }
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            console.log('GPU选择器已加载，检测到的checkbox数量:', document.querySelectorAll('input[type="checkbox"][name="device"]').length);
            
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
            
            // 增强的多选功能 - 实时更新视觉反馈
            document.querySelectorAll('.gpu-option').forEach(function(option, index) {
                const checkbox = option.querySelector('input[type="checkbox"]');
                if (checkbox) {
                    console.log('设置checkbox事件:', checkbox.name, checkbox.value, '初始状态:', checkbox.checked);
                    
                    // checkbox change事件
                    checkbox.addEventListener('change', function(e) {
                        console.log('Checkbox状态改变:', this.name, this.value, this.checked);
                        updateGPUSelection(option, this);
                    });
                    
                    // 点击GPU选项区域也能切换选择
                    option.addEventListener('click', function(e) {
                        if (e.target.type !== 'checkbox' && !e.target.classList.contains('selection-indicator')) {
                            e.preventDefault();
                            checkbox.checked = !checkbox.checked;
                            
                            // 触发change事件
                            const event = new Event('change', { bubbles: true });
                            checkbox.dispatchEvent(event);
                            
                            console.log('通过点击区域切换:', checkbox.name, checkbox.value, checkbox.checked);
                        }
                    });
                }
            });
        });
        </script>
        '''
        
        return mark_safe(main_html + extra_html)

    def format_value(self, value):
        """
        格式化值，确保正确处理各种输入格式
        """
        if value is None:
            return []
        
        # 如果已经是列表，直接返回字符串化的版本
        if isinstance(value, (list, tuple)):
            return [str(v) for v in value]
        
        # 如果是字符串，尝试解析
        if isinstance(value, str):
            # 处理 "[0,1,2]" 或 "['0','1','2']" 格式的字符串
            if value.startswith('[') and value.endswith(']'):
                value = value[1:-1].strip()
                if not value:
                    return []
                # 分割并清理
                items = []
                for item in value.split(','):
                    item = item.strip().strip('"').strip("'").strip()
                    if item:
                        items.append(item)
                return items
            # 处理逗号分隔的字符串
            elif ',' in value:
                return [item.strip() for item in value.split(',') if item.strip()]
            # 单个值
            elif value.strip():
                return [value.strip()]
            else:
                return []
        
        # 其他类型，尝试转换为字符串
        return [str(value)]

    def value_from_datadict(self, data, files, name):
        """
        从表单数据中提取值
        """
        return data.getlist(name)
