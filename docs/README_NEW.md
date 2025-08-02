# EOLO-WEB - Ultralytics实验管理平台

EOLO-WEB是一个基于Django的Web应用，专为管理和启动Ultralytics YOLO实验而设计。该平台提供了用户友好的界面来配置、启动、监控和管理深度学习实验。

## 功能特点

### 🔐 用户管理系统
- 用户注册、登录、注销
- 个人资料管理
- 权限控制和用户认证

### 🧪 实验管理
- 创建和配置Ultralytics YOLO实验
- 支持多种任务类型：目标检测、实例分割、图像分类、姿态估计、目标跟踪
- 实验状态监控：等待中、运行中、已完成、失败、已取消
- 实验历史记录和日志管理

### ⚙️ 灵活配置
- 模型选择（YOLOv8n, YOLOv8s, YOLOv8m, YOLOv8l, YOLOv8x等）
- 训练参数配置（学习率、批量大小、训练轮数等）
- 数据集路径配置
- 设备选择（CPU、GPU）
- 输出目录自定义

### 📊 仪表板
- 实验统计概览
- 最近实验展示
- 状态分布图表
- 快速操作入口

### 🔧 命令生成
- 自动生成Ultralytics命令
- 命令预览和复制
- 参数验证

## 技术栈

- **后端**: Django 5.2.4, Python 3.x
- **前端**: Bootstrap 5, HTML5, JavaScript
- **数据库**: SQLite (开发环境)
- **包管理**: uv
- **样式**: Font Awesome, 自定义CSS

## 安装和设置

### 前置条件
- Python 3.8+
- uv 包管理器

### 安装步骤

1. **安装依赖**
   ```bash
   cd EOLO-WEB
   uv sync
   ```

2. **数据库迁移**
   ```bash
   uv run python manage.py makemigrations
   uv run python manage.py migrate
   ```

3. **创建超级用户**
   ```bash
   uv run python manage.py createsuperuser
   ```

4. **启动开发服务器**
   ```bash
   uv run python manage.py runserver
   ```

5. **访问应用**
   打开浏览器访问 `http://127.0.0.1:8000`

## 使用指南

### 创建实验

1. 登录系统后，点击"新建实验"
2. 填写实验基本信息：
   - 实验名称（必填）
   - 实验描述（可选）
   - 任务类型（检测、分割等）

3. 配置模型参数：
   - 选择预训练模型
   - 设置数据集路径
   - 配置训练参数

4. 设置输出选项（可选）
5. 保存实验配置

### 启动实验

1. 在实验列表中找到目标实验
2. 点击"启动实验"按钮
3. 系统会生成对应的Ultralytics命令
4. 复制生成的命令到终端执行

**生成的命令示例：**
```bash
yolo detect train model=yolov8n.pt data=/path/to/dataset.yaml epochs=100 batch=16 imgsz=640 lr0=0.01 weight_decay=0.0005 device=auto workers=8
```

### 监控实验

- 在仪表板查看所有实验的状态统计
- 在实验详情页面查看实时日志
- 检查实验进度和结果文件

## 项目结构

```
EOLO-WEB/
├── accounts/                 # 用户管理应用
│   ├── models.py            # 用户模型
│   ├── views.py             # 用户视图
│   ├── urls.py              # 用户路由
│   └── admin.py             # 管理界面
├── experiments/             # 实验管理应用
│   ├── models.py            # 实验模型
│   ├── views.py             # 实验视图
│   ├── urls.py              # 实验路由
│   ├── forms.py             # 表单定义
│   └── admin.py             # 管理界面
├── templates/               # 模板文件
│   ├── base.html            # 基础模板
│   ├── accounts/            # 用户模板
│   └── experiments/         # 实验模板
├── static/                  # 静态文件
│   ├── css/                 # 样式文件
│   └── js/                  # JavaScript文件
├── eolo_web/               # 项目配置
│   ├── settings.py          # Django设置
│   ├── urls.py              # 主路由
│   └── wsgi.py              # WSGI配置
├── manage.py                # Django管理脚本
├── pyproject.toml           # 项目配置
└── README.md                # 项目说明
```

## 重要说明

**本项目只负责生成Ultralytics训练命令，不包含深度学习训练代码。**

用户需要：
1. 在服务器或本地环境中单独安装Ultralytics
2. 复制网站生成的命令到终端执行
3. 自行管理训练环境和数据集

这种设计确保了：
- 网站轻量化，不依赖深度学习库
- 训练环境独立，可以在不同的机器上运行
- 便于维护和部署

## 快速启动

现在让我们启动服务器测试一下：

```bash
# 启动开发服务器
uv run python manage.py runserver

# 访问地址
http://127.0.0.1:8000

# 管理员界面
http://127.0.0.1:8000/admin
```

## 下一步

项目基础框架已搭建完成，您可以：

1. 启动服务器测试功能
2. 创建测试用户和实验
3. 根据需要调整界面和功能
4. 部署到生产环境

如有任何问题或需要进一步的功能扩展，请随时联系！
