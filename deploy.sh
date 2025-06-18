#!/bin/bash

# SSTI CTF Challenge Docker 部署脚本

echo "🚀 开始部署 SSTI CTF Challenge..."

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

# 停止并删除现有容器
echo "🛑 停止现有容器..."
docker-compose down

# 删除现有镜像（可选）
read -p "是否删除现有镜像重新构建？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  删除现有镜像..."
    docker-compose down --rmi all
fi

# 构建并启动容器
echo "🔨 构建并启动容器..."
docker-compose up --build -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo "🔍 检查服务状态..."
if curl -f http://localhost:5000/status &> /dev/null; then
    echo "✅ 服务启动成功！"
    echo "🌐 访问地址: http://localhost:5000"
    echo "📝 渲染接口: http://localhost:5000/render"
    echo "📊 状态接口: http://localhost:5000/status"
    echo "💡 前端和后端现在都在5000端口运行"
else
    echo "❌ 服务启动失败，请检查日志："
    docker-compose logs
    exit 1
fi

echo "🎉 部署完成！" 