# Eecho's SSTI CTF Challenge

一个融合赛博朋克风格的Python Server-Side Template Injection (SSTI) CTF挑战。

## 🎯 挑战目标

绕过Web应用防火墙(WAF)的防护机制，通过Jinja2模板注入技术获取服务器上的flag。

## 🚀 快速开始

### 方式一：Docker部署（推荐）

#### 使用Docker Hub镜像
```bash
# 最简单的方式
docker run -d --name ssti-challenge -p 5000:5000 --restart unless-stopped 4c69/ssti_labs_e:ssti_v1

# 或使用docker-compose
docker-compose -f docker-compose.prod.yml up -d
```

#### 本地构建
```bash
# 使用部署脚本
chmod +x deploy.sh
./deploy.sh

# 或手动构建
docker-compose up --build -d
```

### 方式二：本地开发

#### 1. 安装依赖
```bash
# 安装前端依赖
npm install

# 安装后端依赖
pip install -r requirements.txt
```

#### 2. 启动服务
```bash
# 启动后端服务器 (终端1)
python server.py

# 启动前端开发服务器 (终端2)
npm start
```

#### 3. 访问应用
- **Docker部署**: http://localhost:5000
- **本地开发**: http://localhost:3000

## 🎨 特色功能

### 前端设计
- **赛博朋克风格**: 深空黑背景 + 霓虹色彩
- **全息投影效果**: 3D视觉层次感
- **粒子背景**: 动态粒子系统
- **扫描线动画**: 模拟终端扫描效果
- **鼠标跟随**: 光晕跟随效果
- **响应式设计**: 适配各种设备

### 后端功能
- **多层WAF防护**: 关键词过滤 + 正则表达式检测
- **Jinja2模板引擎**: 安全的模板渲染
- **随机Flag生成**: 每次启动生成新的flag
- **CORS支持**: 跨域请求支持
- **完善错误处理**: 详细的错误提示

## 🔒 防护机制详解

### 禁止的关键词
```python
UNSAFE_KEYWORDS = [
    '__', 'import', 'os', 'sys', 'eval', 'subprocess', 
    'popen', 'system', '%2f', '%2F', 'flag', 'cat', '?'
]
```

### 危险模式检测
- 类构造: `class\s*\(`
- 内置函数: `globals\s*\(`, `locals\s*\(`, `getattr\s*\(`
- 文件操作: `open\s*\(`, `file\s*\(`
- 代码执行: `exec\s*\(`, `compile\s*\(`, `eval\s*\(`
- 魔术方法: `__class__`, `__bases__`, `__subclasses__` 等

## 🎮 使用说明

### 基本操作
1. 在模板输入框中输入Jinja2模板
2. 点击"渲染模板"按钮
3. 查看渲染结果
4. 尝试绕过防护获取flag

### 示例模板
```jinja2
# 基础示例
Hello {{ name }}!

# 数学运算
1 + 1 = {{ 1 + 1 }}

# 列表操作
{{ [1,2,3] | length }}

# 字符串操作
{{ "hello" | upper }}

# 字典操作
{{ dict.items() }}

# 条件判断
{% if true %}条件为真{% endif %}
```

## 🎯 解题思路

### 核心思路
这是一个SSTI挑战，目标是绕过WAF防护并读取flag文件。需要寻找其他方法：

1. **利用Jinja2内置函数和过滤器**
2. **使用字符串拼接绕过关键词检测**
3. **利用模板上下文中的变量**
4. **寻找防护的绕过方法**

### 技术要点
- 理解Jinja2模板引擎的工作原理
- 掌握Python对象的内置属性和方法
- 学会绕过字符串过滤的技术
- 了解SSTI漏洞的利用技巧

### 提示
- 注意观察模板上下文中的可用变量
- 尝试使用不同的字符串编码方式
- 考虑使用Jinja2的内置函数和过滤器
- 研究如何绕过双下划线的检测

## 🏗️ 技术架构

### 前端技术栈
- **React 18**: 现代化前端框架
- **CSS3 动画**: 赛博朋克视觉效果
- **Lucide React**: 高质量图标库
- **Axios**: HTTP客户端

### 后端技术栈
- **Python 3.8+**: 主要开发语言
- **Flask**: 轻量级Web框架
- **Jinja2**: 模板引擎
- **Flask-CORS**: 跨域支持

### 部署技术
- **Docker**: 容器化部署
- **Docker Compose**: 多容器编排
- **多阶段构建**: 优化镜像大小

## 📁 项目结构
```
SSTI_labs/
├── public/                 # 静态文件
│   └── index.html         # HTML模板
├── src/                   # React源码
│   ├── App.js            # 主组件
│   ├── App.css           # 样式文件
│   ├── index.js          # 入口文件
│   └── index.css         # 全局样式
├── server.py             # Python后端
├── requirements.txt      # Python依赖
├── package.json          # Node.js依赖
├── Dockerfile            # Docker构建文件
├── docker-compose.yml    # Docker编排文件
├── deploy.sh             # 部署脚本
├── deploy.ps1            # PowerShell部署脚本
├── DOCKER_README.md      # Docker部署文档
└── README.md            # 项目说明
```

## 🔧 配置说明

### 端口配置
- **Docker部署**: 默认5000端口
- **本地开发**: 前端3000端口，后端5000端口

### 环境变量
```bash
FLASK_ENV=production
FLASK_DEBUG=0
```

### 自定义配置
编辑 `server.py` 中的端口配置：
```python
app.run(host='0.0.0.0', port=5000, debug=False)
```

## 🐛 故障排除

### 常见问题
1. **端口被占用**: 修改docker-compose.yml中的端口映射
2. **构建失败**: 检查Docker和Docker Compose版本
3. **服务无法访问**: 查看容器日志 `docker-compose logs`
4. **权限问题**: Linux系统可能需要使用sudo

### 调试命令
```bash
# 查看容器状态
docker ps

# 查看日志
docker logs ssti-challenge

# 进入容器
docker exec -it ssti-challenge bash

# 检查服务状态
curl http://localhost:5000/status
```

## 📚 学习资源

### SSTI相关
- [OWASP SSTI](https://owasp.org/www-community/attacks/Server-Side_Template_Injection)
- [Jinja2官方文档](https://jinja.palletsprojects.com/)
- [SSTI Payloads](https://github.com/payloadbox/ssti-payloads)

### CTF相关
- [CTF Wiki](https://ctf-wiki.org/)
- [HackTricks](https://book.hacktricks.xyz/)

## 📝 许可证

This project is licensed under the MIT [LICENSE](LICENSE)

## 👨‍💻 作者

**Eecho**

- 博客: [www.eecho.top](https://www.eecho.top)
- GitHub: [@4c69](https://github.com/4c69)

## ⚠️ 免责声明

**重要提醒**: 
- 这是一个教育目的的CTF挑战
- 仅用于学习和研究SSTI漏洞
- 请勿用于恶意攻击或非法用途
- 在授权环境中进行测试

---

**Happy Hacking! 🎉**

