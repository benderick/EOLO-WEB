# EOLO-WEB 管理平台

一个基于 Django 的 Web 管理平台，用于管理和监控 EOLO 模型实验。提供用户友好的界面来配置、执行和监控机器学习实验。

## 📋 项目概述

EOLO-WEB 是一个现代化的 Web 应用程序，为 EOLO 机器学习框架提供图形化管理界面。主要功能包括：

- **用户管理**：账户注册、登录和权限管理
- **实验管理**：创建、配置和监控机器学习实验
- **数据集管理**：上传、组织和管理训练数据集
- **模型管理**：配置模型参数、执行测试和性能监控
- **实时监控**：实验进度跟踪和结果可视化

## 🏗️ 项目架构

```
EOLO-WEB/
├── eolo_web/           # Django 主项目配置
├── accounts/           # 用户账户管理应用
├── experiments/        # 实验管理应用
├── datasets/          # 数据集管理应用
├── models_manager/    # 模型配置和测试应用
├── templates/         # 全局模板文件
├── static/           # 静态文件（CSS、JS、图片）
├── EOLO/             # EOLO 子项目（软链接）
└── manage.py         # Django 管理脚本
```

## 🛠️ 技术栈

- **后端**：Django 5.2.4
- **前端**：Bootstrap 5、JavaScript、HTML5
- **数据库**：SQLite（便于迁移和部署）
- **包管理**：uv (Python 包管理器)
- **Python版本**：>=3.13

## 📦 依赖包

主要依赖：
- `django>=5.2.4` - Web 框架
- `pyyaml>=6.0.2` - YAML 配置文件解析
- `psutil>=6.0.0` - 系统进程监控

## 🚀 快速开始

### 1. 环境要求

- Python 3.13+
- uv 包管理器
- Git

### 2. 克隆项目

```bash
git clone <repository_url>
cd EOLO-WEB
```

### 3. 安装 uv（如果尚未安装）

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 4. 设置虚拟环境和依赖

```bash
# 创建虚拟环境并安装依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate     # Windows
```

### 5. 设置 EOLO 子项目链接

```bash
# 创建到 EOLO 项目的软链接
ln -s /path/to/your/EOLO EOLO

# 或复制 EOLO 项目到当前目录
cp -r /path/to/your/EOLO ./EOLO
```

### 6. 数据库初始化

```bash
# 执行数据库迁移
python manage.py makemigrations
python manage.py migrate

# 创建超级用户（可选）
python manage.py createsuperuser
```

### 7. 启动开发服务器

```bash
python manage.py runserver
```

现在访问 `http://localhost:8000` 即可使用系统。

## 🔧 配置说明

### 环境配置

主要配置文件：`eolo_web/settings.py`

#### EOLO 路径配置

```python
# EOLO子项目路径（相对于EOLO-WEB根目录）
EOLO_DIR = BASE_DIR / 'EOLO'

# EOLO配置文件路径
EOLO_CONFIGS_DIR = EOLO_DIR / 'configs'
EOLO_MODEL_CONFIGS_DIR = EOLO_CONFIGS_DIR / 'model'
EOLO_SETTING_CONFIGS_DIR = EOLO_CONFIGS_DIR / 'setting'

# EOLO脚本路径
EOLO_SCRIPTS_DIR = EOLO_DIR / 'scripts'
EOLO_MODEL_TEST_SCRIPT = EOLO_SCRIPTS_DIR / 'model_test.py'
```

#### 模型测试配置

```python
MODEL_TEST_CONFIG = {
    'TIMEOUT': 60,                # 测试命令超时时间（秒）
    'DEFAULT_DEVICE': 'cuda',     # 默认设备
    'QUIET_MODE': True,           # 是否使用安静模式
}
```

### 生产环境配置

1. **安全设置**：
   ```python
   DEBUG = False
   SECRET_KEY = 'your-production-secret-key'
   ALLOWED_HOSTS = ['your-domain.com']
   ```

2. **数据库配置**（使用SQLite，便于迁移）：
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.sqlite3',
           'NAME': BASE_DIR / 'db.sqlite3',
       }
   }
   ```

## 🚀 部署指南

### 1. 新环境部署步骤

#### 准备工作

1. 确保目标服务器满足环境要求
2. 安装必要的系统依赖：
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3.13 python3.13-venv git nginx
   
   # CentOS/RHEL
   sudo yum install python3.13 python3.13-venv git nginx
   ```

#### 部署流程

1. **克隆项目**：
   ```bash
   git clone <repository_url> /var/www/eolo-web
   cd /var/www/eolo-web
   ```

2. **安装 uv 和依赖**：
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source ~/.bashrc
   uv sync
   ```

3. **配置 EOLO 项目**：
   ```bash
   # 方法1：软链接（推荐）
   ln -s /path/to/eolo/project EOLO
   
   # 方法2：复制项目
   cp -r /path/to/eolo/project ./EOLO
   ```

4. **环境变量配置**：
   ```bash
   # 创建环境变量文件
   cat > .env << EOF
   DJANGO_SECRET_KEY=your-production-secret-key
   DJANGO_DEBUG=False
   ALLOWED_HOSTS=your-domain.com,www.your-domain.com
   EOF
   ```

5. **数据库设置**：
   ```bash
   # 使用SQLite，无需额外数据库服务器配置
   # 直接进行Django数据库迁移
   source .venv/bin/activate
   python manage.py migrate
   python manage.py collectstatic --noinput
   
   # 可选：复制现有数据库文件
   # cp /path/to/existing/db.sqlite3 ./db.sqlite3
   ```

6. **创建系统服务**：
   ```bash
   # 创建 systemd 服务文件
   sudo tee /etc/systemd/system/eolo-web.service << EOF
   [Unit]
   Description=EOLO-WEB Django Application
   After=network.target
   
   [Service]
   Type=exec
   User=www-data
   Group=www-data
   WorkingDirectory=/var/www/eolo-web
   Environment=PATH=/var/www/eolo-web/.venv/bin
   ExecStart=/var/www/eolo-web/.venv/bin/python manage.py runserver 0.0.0.0:8000
   Restart=always
   RestartSec=3
   
   [Install]
   WantedBy=multi-user.target
   EOF
   
   # 启动服务
   sudo systemctl daemon-reload
   sudo systemctl enable eolo-web
   sudo systemctl start eolo-web
   ```

7. **Nginx 配置**：
   ```bash
   # 创建 Nginx 配置
   sudo tee /etc/nginx/sites-available/eolo-web << EOF
   server {
       listen 80;
       server_name your-domain.com www.your-domain.com;
       
       location /static/ {
           alias /var/www/eolo-web/static/;
           expires 1y;
           add_header Cache-Control "public, immutable";
       }
       
       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host \$host;
           proxy_set_header X-Real-IP \$remote_addr;
           proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto \$scheme;
       }
   }
   EOF
   
   # 启用站点
   sudo ln -s /etc/nginx/sites-available/eolo-web /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

### 2. Docker 部署（可选）

创建 `Dockerfile`：

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install uv

# 复制项目文件
COPY . .

# 安装 Python 依赖
RUN uv sync

# 收集静态文件
RUN uv run python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]
```

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DJANGO_DEBUG=False
    volumes:
      - ./EOLO:/app/EOLO
      - ./db.sqlite3:/app/db.sqlite3  # 挂载SQLite数据库文件
```

运行：
```bash
docker-compose up -d
```

## 🔍 主要功能

### 模型管理
- 模型配置文件编辑
- 实时模型测试
- 测试结果可视化
- 配置验证和错误检查

### 实验管理
- 实验创建和配置
- 进度监控
- 结果分析
- 历史记录查看

### 用户管理
- 用户注册和登录
- 权限控制
- 个人资料管理

## 🐛 故障排除

### 常见问题

1. **EOLO 模块导入错误**：
   - 检查 EOLO 软链接是否正确
   - 确认 EOLO 项目路径配置

2. **模型测试超时**：
   - 调整 `MODEL_TEST_CONFIG['TIMEOUT']` 设置
   - 检查 CUDA 环境配置

3. **静态文件加载失败**：
   ```bash
   python manage.py collectstatic --noinput
   ```

4. **数据库相关问题**：
   - SQLite文件权限检查：`chmod 664 db.sqlite3`
   - 数据库迁移重置：`python manage.py migrate --fake-initial`
   - 数据库文件迁移：直接复制 `db.sqlite3` 到新环境即可

5. **项目迁移**：
   ```bash
   # 迁移到新服务器非常简单
   # 1. 复制整个项目目录（包含db.sqlite3）
   # 2. 重建软链接：ln -s /path/to/EOLO ./EOLO
   # 3. 安装依赖：uv sync
   # 4. 启动服务：uv run python manage.py runserver
   ```

## 📝 开发指南

### 代码风格
- 遵循 PEP 8 Python 代码规范
- 使用中文注释说明复杂逻辑
- 函数和类使用英文命名，注释使用中文

### 贡献流程
1. Fork 项目
2. 创建功能分支
3. 提交代码
4. 创建 Pull Request

## 📄 许可证

[添加您的许可证信息]

## 📞 支持

如有问题，请提交 Issue 或联系开发团队。

---

**版本**：0.1.0  
**最后更新**：2025年8月