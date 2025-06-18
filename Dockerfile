# 多阶段构建Dockerfile
# 第一阶段：构建React前端
FROM node:18-alpine AS frontend-builder

WORKDIR /app

# 复制package.json和package-lock.json
COPY package*.json ./

# 安装依赖
RUN npm install --production=false

# 复制前端源代码
COPY public/ ./public/
COPY src/ ./src/

# 构建React应用
RUN npm run build

# 第二阶段：Python后端
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制Python依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY server.py .
COPY test.py .

# 从第一阶段复制构建好的前端文件到public目录
COPY --from=frontend-builder /app/build ./public

# 创建非root用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "server.py"] 