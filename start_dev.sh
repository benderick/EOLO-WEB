#!/bin/bash
# EOLO-WEB 开发模式启动脚本

echo "🚀 启动 EOLO-WEB 开发模式..."
echo "📍 访问地址: http://localhost:8000"
echo "🔧 调试模式: 开启"
echo "📁 静态文件: 自动处理"
echo "⚡ 热重载: 开启"
echo ""

# 设置开发模式环境变量
export DJANGO_DEBUG=True

# 启动开发服务器
uv run python manage.py runserver 0.0.0.0:8000
