#!/bin/bash
# EOLO-WEB 生产模式启动脚本

echo "🏭 启动 EOLO-WEB 生产模式..."
echo "📍 访问地址: http://localhost:8000"
echo "🔐 调试模式: 关闭"
echo "📁 静态文件: 预收集"
echo "🛡️  安全模式: 开启"
echo ""

# 设置生产模式环境变量
export DJANGO_DEBUG=False
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,$(hostname -I | awk '{print $1}')

echo "🔄 收集静态文件..."
uv run python manage.py collectstatic --noinput

echo "✅ 启动服务器..."
# 使用 --insecure 允许Django在生产模式下处理静态文件
uv run python manage.py runserver 0.0.0.0:8000 --insecure
