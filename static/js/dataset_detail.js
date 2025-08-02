// 数据集详情页面的JavaScript功能
document.addEventListener('DOMContentLoaded', function() {
    // 初始化提示框
    const toastEl = document.getElementById('toast');
    const toast = new bootstrap.Toast(toastEl);
    
    // 显示提示信息
    function showToast(message, type = 'info') {
        const toastBody = document.getElementById('toast-body');
        const toastHeader = document.querySelector('.toast-header i');
        
        // 更新内容
        toastBody.textContent = message;
        
        // 更新图标和样式
        toastHeader.className = `fas me-2`;
        switch(type) {
            case 'success':
                toastHeader.classList.add('fa-check-circle', 'text-success');
                break;
            case 'error':
                toastHeader.classList.add('fa-exclamation-circle', 'text-danger');
                break;
            case 'warning':
                toastHeader.classList.add('fa-exclamation-triangle', 'text-warning');
                break;
            default:
                toastHeader.classList.add('fa-info-circle', 'text-primary');
        }
        
        toast.show();
    }
    
    // 复制到剪贴板功能
    window.copyToClipboard = function(text) {
        navigator.clipboard.writeText(text).then(function() {
            showToast('已复制到剪贴板: ' + text.substring(0, 50) + (text.length > 50 ? '...' : ''), 'success');
        }).catch(function(err) {
            console.error('复制失败: ', err);
            showToast('复制失败，请手动复制', 'error');
        });
    };
    
    // 复制数据集路径
    window.copyDatasetPath = function() {
        const pathElement = document.querySelector('input[readonly]');
        if (pathElement) {
            copyToClipboard(pathElement.value);
        }
    };
    
    // 复制YAML内容
    window.copyYamlContent = function() {
        const yamlContent = document.getElementById('yaml-content');
        if (yamlContent) {
            copyToClipboard(yamlContent.textContent);
        }
    };
    
    // 下载YAML文件
    window.downloadYaml = function() {
        const yamlContent = document.getElementById('yaml-content');
        if (!yamlContent) {
            showToast('无法获取YAML内容', 'error');
            return;
        }
        
        // 获取数据集名称
        const datasetName = document.querySelector('h1').textContent.trim().split(' ')[0];
        
        // 创建下载链接
        const blob = new Blob([yamlContent.textContent], { type: 'text/yaml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${datasetName}.yaml`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast('YAML文件下载已开始', 'success');
    };
    
    // 验证数据集配置
    window.validateDataset = function() {
        showToast('正在验证数据集配置...', 'info');
        
        // 获取当前数据集名称
        const urlParts = window.location.pathname.split('/');
        const datasetName = urlParts[urlParts.length - 2]; // 假设URL格式为 /datasets/name/
        
        // 发送验证请求
        fetch(`/datasets/${datasetName}/validate/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.valid) {
                showToast('数据集配置验证通过', 'success');
            } else {
                showToast('数据集配置验证失败: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('验证失败:', error);
            showToast('验证过程中出现错误', 'error');
        });
    };
    
    // 获取CSRF令牌
    function getCsrfToken() {
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        return cookieValue || '';
    }
    
    // 语法高亮（如果有相关库）
    if (typeof hljs !== 'undefined') {
        hljs.highlightAll();
    }
    
    // 添加键盘快捷键
    document.addEventListener('keydown', function(e) {
        // Ctrl+C 复制YAML内容
        if (e.ctrlKey && e.key === 'c' && !window.getSelection().toString()) {
            e.preventDefault();
            copyYamlContent();
        }
        
        // Ctrl+D 下载YAML文件
        if (e.ctrlKey && e.key === 'd') {
            e.preventDefault();
            downloadYaml();
        }
        
        // Esc键返回列表
        if (e.key === 'Escape') {
            window.location.href = '/datasets/';
        }
    });
    
    // 自动刷新文件信息（每30秒检查一次文件修改时间）
    let lastModified = null;
    
    function checkFileUpdate() {
        const urlParts = window.location.pathname.split('/');
        const datasetName = urlParts[urlParts.length - 2];
        
        fetch(`/datasets/${datasetName}/info/`)
            .then(response => response.json())
            .then(data => {
                if (lastModified === null) {
                    lastModified = data.modified_time;
                } else if (data.modified_time !== lastModified) {
                    showToast('检测到数据集文件已更新，点击刷新页面查看最新内容', 'warning');
                    lastModified = data.modified_time;
                    
                    // 添加刷新按钮到提示中
                    const toastBody = document.getElementById('toast-body');
                    const refreshBtn = document.createElement('button');
                    refreshBtn.className = 'btn btn-sm btn-warning ms-2';
                    refreshBtn.innerHTML = '<i class="fas fa-refresh me-1"></i>刷新';
                    refreshBtn.onclick = () => location.reload();
                    toastBody.appendChild(refreshBtn);
                }
            })
            .catch(error => {
                console.error('检查文件更新失败:', error);
            });
    }
    
    // 每30秒检查一次文件更新
    setInterval(checkFileUpdate, 30000);
    
    // 初始化时记录当前修改时间
    checkFileUpdate();
    
    console.log('数据集详情页面JavaScript初始化完成');
});
