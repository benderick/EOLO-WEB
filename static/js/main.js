// EOLO-WEB 主JavaScript文件

document.addEventListener('DOMContentLoaded', function() {
    // 初始化工具提示
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // 自动隐藏消息提示
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // 为表单添加提交确认
    var dangerForms = document.querySelectorAll('form[action*="delete"], form[action*="stop"]');
    dangerForms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            var action = form.action;
            var confirmMessage = '确认执行此操作？';
            
            if (action.includes('delete')) {
                confirmMessage = '确认删除？此操作不可撤销！';
            } else if (action.includes('stop')) {
                confirmMessage = '确认停止实验？';
            }
            
            if (!confirm(confirmMessage)) {
                e.preventDefault();
            }
        });
    });

    // 实验状态自动刷新
    var runningExperiments = document.querySelectorAll('[data-status="running"]');
    if (runningExperiments.length > 0) {
        setInterval(function() {
            // 可以在这里添加AJAX请求来更新状态
            console.log('检查运行中的实验状态...');
        }, 30000); // 每30秒检查一次
    }

    // 代码复制功能
    window.copyToClipboard = function(text) {
        navigator.clipboard.writeText(text).then(function() {
            showToast('代码已复制到剪贴板', 'success');
        }, function(err) {
            console.error('复制失败: ', err);
            showToast('复制失败', 'error');
        });
    };

    // 显示临时提示
    window.showToast = function(message, type = 'info') {
        var toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '1050';
            document.body.appendChild(toastContainer);
        }

        var toastId = 'toast-' + Date.now();
        var toastClass = type === 'success' ? 'bg-success' : 
                        type === 'error' ? 'bg-danger' : 
                        type === 'warning' ? 'bg-warning' : 'bg-info';

        var toastHtml = `
            <div id="${toastId}" class="toast ${toastClass} text-white" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        var toastElement = document.getElementById(toastId);
        var toast = new bootstrap.Toast(toastElement);
        toast.show();

        // 自动清理过期的toast
        toastElement.addEventListener('hidden.bs.toast', function() {
            toastElement.remove();
        });
    };

    // 表单验证增强
    var forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            var isValid = true;
            var requiredFields = form.querySelectorAll('[required]');
            
            requiredFields.forEach(function(field) {
                if (!field.value.trim()) {
                    field.classList.add('is-invalid');
                    isValid = false;
                } else {
                    field.classList.remove('is-invalid');
                }
            });

            if (!isValid) {
                e.preventDefault();
                showToast('请填写所有必填字段', 'warning');
            }
        });

        // 实时移除错误标记
        var inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(function(input) {
            input.addEventListener('input', function() {
                this.classList.remove('is-invalid');
            });
        });
    });

    // 数据表格排序功能
    var sortableHeaders = document.querySelectorAll('th[data-sort]');
    sortableHeaders.forEach(function(header) {
        header.style.cursor = 'pointer';
        header.addEventListener('click', function() {
            var column = this.dataset.sort;
            var currentUrl = new URL(window.location);
            var currentSort = currentUrl.searchParams.get('sort');
            var newSort = column;
            
            if (currentSort === column) {
                newSort = '-' + column;
            } else if (currentSort === '-' + column) {
                newSort = '';
            }
            
            if (newSort) {
                currentUrl.searchParams.set('sort', newSort);
            } else {
                currentUrl.searchParams.delete('sort');
            }
            
            window.location = currentUrl.toString();
        });
    });

    // 实验命令预览功能
    window.previewCommand = function(experimentId) {
        fetch(`/experiments/${experimentId}/command/`)
            .then(response => response.json())
            .then(data => {
                var modal = new bootstrap.Modal(document.getElementById('commandModal'));
                document.getElementById('commandText').textContent = data.command;
                modal.show();
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('获取命令失败', 'error');
            });
    };

    // 自动保存表单草稿
    var experimentForm = document.getElementById('experiment-form');
    if (experimentForm) {
        var formData = {};
        var inputs = experimentForm.querySelectorAll('input, select, textarea');
        
        inputs.forEach(function(input) {
            // 从localStorage恢复数据
            var savedValue = localStorage.getItem('draft_' + input.name);
            if (savedValue && !input.value) {
                input.value = savedValue;
            }
            
            // 保存用户输入
            input.addEventListener('input', function() {
                localStorage.setItem('draft_' + this.name, this.value);
            });
        });

        // 提交时清除草稿
        experimentForm.addEventListener('submit', function() {
            inputs.forEach(function(input) {
                localStorage.removeItem('draft_' + input.name);
            });
        });
    }

    // 键盘快捷键
    document.addEventListener('keydown', function(e) {
        // Ctrl+N 新建实验
        if (e.ctrlKey && e.key === 'n') {
            e.preventDefault();
            window.location.href = '/experiments/create/';
        }
        
        // Ctrl+H 返回仪表板
        if (e.ctrlKey && e.key === 'h') {
            e.preventDefault();
            window.location.href = '/experiments/';
        }
    });

    console.log('EOLO-WEB 已加载完成');
});

// 全局工具函数
window.EoloWeb = {
    // 格式化时间
    formatTime: function(timestamp) {
        var date = new Date(timestamp);
        return date.toLocaleString('zh-CN');
    },
    
    // 获取状态颜色
    getStatusColor: function(status) {
        var colors = {
            'pending': '#6c757d',
            'running': '#ffc107',
            'completed': '#28a745',
            'failed': '#dc3545',
            'cancelled': '#343a40'
        };
        return colors[status] || '#6c757d';
    },
    
    // 显示加载状态
    showLoading: function(element, text = '加载中...') {
        element.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
            ${text}
        `;
        element.disabled = true;
    },
    
    // 隐藏加载状态
    hideLoading: function(element, originalText) {
        element.innerHTML = originalText;
        element.disabled = false;
    }
};
