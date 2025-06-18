#!/bin/bash

# SSTI CTF Challenge Docker Hub 镜像部署脚本

echo "🚀 开始部署 SSTI CTF Challenge (Docker Hub镜像)..."

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 停止并删除现有容器
echo "🛑 停止现有容器..."
docker stop ssti-challenge 2>/dev/null || true
docker rm ssti-challenge 2>/dev/null || true

# 拉取最新镜像
echo "📥 拉取Docker Hub镜像..."
docker pull 4c69/ssti_labs_e:ssti_v1

# 启动容器
echo "🔨 启动容器..."
docker run -d \
  --name ssti-challenge \
  -p 5000:5000 \
  --restart unless-stopped \
  4c69/ssti_labs_e:ssti_v1

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
    echo "💡 前端和后端都在5000端口运行"
else
    echo "❌ 服务启动失败，请检查日志："
    docker logs ssti-challenge
    exit 1
fi

echo "🎉 部署完成！" 