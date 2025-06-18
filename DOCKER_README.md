# Docker 部署指南

本项目支持使用 Docker 进行快速部署，包含完整的 React 前端和 Flask 后端。**前端和后端现在都在同一个端口（5000）上运行**。

## 前置要求

- Docker Desktop (Windows/Mac) 或 Docker Engine (Linux)
- Docker Compose

## 快速部署

### 方法一：使用部署脚本（推荐）

#### Windows PowerShell
```powershell
.\deploy.ps1
```

#### Linux/macOS
```bash
chmod +x deploy.sh
./deploy.sh
```

### 方法二：手动部署

1. **构建并启动容器**
   ```bash
   docker-compose up --build -d
   ```

2. **查看服务状态**
   ```bash
   docker-compose ps
   ```

3. **查看日志**
   ```bash
   docker-compose logs -f
   ```

## 访问服务

部署成功后，可以通过以下地址访问：

- **主页（React前端）**: http://localhost:5000
- **渲染接口（API）**: http://localhost:5000/render
- **状态接口（API）**: http://localhost:5000/status

**注意**: 前端和后端现在都在5000端口运行，Flask服务器会自动提供React构建的静态文件。

## 架构说明

- **前端**: React应用构建后的静态文件由Flask提供
- **后端**: Flask API服务器处理模板渲染请求
- **端口**: 统一使用5000端口，避免跨域问题
- **通信**: 前端通过相对路径调用后端API

## 管理命令

### 停止服务
```bash
docker-compose down
```

### 重启服务
```bash
docker-compose restart
```

### 查看日志
```bash
docker-compose logs -f ssti-challenge
```

### 进入容器
```bash
docker-compose exec ssti-challenge bash
```

### 重新构建
```bash
docker-compose down --rmi all
docker-compose up --build -d
```

## 配置说明

### 端口配置
默认端口为 5000，如需修改，请编辑 `docker-compose.yml` 文件：

```yaml
ports:
  - "8080:5000"  # 将主机的8080端口映射到容器的5000端口
```

### 环境变量
可以在 `docker-compose.yml` 中添加环境变量：

```yaml
environment:
  - FLASK_ENV=production
  - FLASK_DEBUG=0
  - CUSTOM_VAR=value
```

### 数据持久化
flag.txt 文件会在容器启动时自动生成，每次重启都会生成新的flag。

## 故障排除

### 1. 端口被占用
如果 5000 端口被占用，修改 `docker-compose.yml` 中的端口映射。

### 2. 构建失败
检查 Docker 和 Docker Compose 版本是否兼容：
```bash
docker --version
docker-compose --version
```

### 3. 服务无法访问
检查容器状态：
```bash
docker-compose ps
docker-compose logs ssti-challenge
```

### 4. 权限问题
在 Linux 系统中，可能需要使用 sudo：
```bash
sudo docker-compose up --build -d
```

### 5. 前端无法加载
确保React应用已正确构建：
```bash
docker-compose exec ssti-challenge ls -la public/
```

## 安全说明

- 容器以非 root 用户运行
- 只暴露必要的端口
- 包含健康检查机制
- 自动重启策略
- WAF防护机制

## 开发模式

如需在开发模式下运行，可以修改 `docker-compose.yml`：

```yaml
environment:
  - FLASK_ENV=development
  - FLASK_DEBUG=1
```

然后重新构建：
```bash
docker-compose up --build
```

## 技术栈

- **前端**: React 18 + Axios + Lucide React
- **后端**: Flask + Jinja2 + Flask-CORS
- **容器**: Docker + Docker Compose
- **构建**: 多阶段Docker构建 