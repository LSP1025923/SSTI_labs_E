# SSTI CTF Challenge Docker 部署脚本 (PowerShell)

Write-Host "🚀 开始部署 SSTI CTF Challenge..." -ForegroundColor Green

# 检查Docker是否安装
try {
    docker --version | Out-Null
    Write-Host "✅ Docker 已安装" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker 未安装，请先安装 Docker" -ForegroundColor Red
    exit 1
}

# 检查Docker Compose是否安装
try {
    docker-compose --version | Out-Null
    Write-Host "✅ Docker Compose 已安装" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Compose 未安装，请先安装 Docker Compose" -ForegroundColor Red
    exit 1
}

# 停止并删除现有容器
Write-Host "🛑 停止现有容器..." -ForegroundColor Yellow
docker-compose down

# 删除现有镜像（可选）
$rebuild = Read-Host "是否删除现有镜像重新构建？(y/N)"
if ($rebuild -eq "y" -or $rebuild -eq "Y") {
    Write-Host "🗑️  删除现有镜像..." -ForegroundColor Yellow
    docker-compose down --rmi all
}

# 构建并启动容器
Write-Host "🔨 构建并启动容器..." -ForegroundColor Yellow
docker-compose up --build -d

# 等待服务启动
Write-Host "⏳ 等待服务启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# 检查服务状态
Write-Host "🔍 检查服务状态..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000/status" -UseBasicParsing -TimeoutSec 10
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ 服务启动成功！" -ForegroundColor Green
        Write-Host "🌐 访问地址: http://localhost:5000" -ForegroundColor Cyan
        Write-Host "📝 渲染接口: http://localhost:5000/render" -ForegroundColor Cyan
        Write-Host "📊 状态接口: http://localhost:5000/status" -ForegroundColor Cyan
        Write-Host "💡 前端和后端现在都在5000端口运行" -ForegroundColor Yellow
    } else {
        throw "服务响应异常"
    }
} catch {
    Write-Host "❌ 服务启动失败，请检查日志：" -ForegroundColor Red
    docker-compose logs
    exit 1
}

Write-Host "🎉 部署完成！" -ForegroundColor Green 