# Eecho's SSTI CTF Challenge

一个融合赛博朋克风格的Python Server-Side Template Injection (SSTI) CTF挑战。

## 🎯 挑战目标

绕过防护并获取服务器上的flag。

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装前端依赖
npm install

# 安装后端依赖
pip install -r requirements.txt
```

### 2. 启动服务

```bash
# 启动后端服务器 (终端1)
python server.py

# 启动前端开发服务器 (终端2)
npm start
```

### 3. 访问应用

打开浏览器访问: http://localhost:3000

## 🎨 特色功能

### 前端设计
- **赛博朋克风格**: 深空黑背景 + 霓虹色彩
- **全息投影效果**: 3D视觉层次感
- **粒子背景**: 动态粒子系统
- **扫描线动画**: 模拟终端扫描效果
- **鼠标跟随**: 光晕跟随效果
- **响应式设计**: 适配各种设备

### 后端功能
- **防护机制**: 多层安全检查
- **Jinja2模板引擎**: 安全的模板渲染
- **随机Flag生成**: 每次启动生成新的flag
- **CORS支持**: 跨域请求支持
- **错误处理**: 完善的错误提示

## 🧩 技术栈

### 前端
- React 18
- CSS3 动画
- Lucide React 图标
- Axios HTTP客户端

### 后端
- Python 3.8+
- Flask Web框架
- Jinja2 模板引擎
- Flask-CORS 跨域支持

## 🎮 使用说明

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
```

## 🔧 开发说明

### 项目结构
```
ezssti/
├── public/              # 静态文件
├── src/                 # React源码
│   ├── App.js          # 主组件
│   ├── App.css         # 样式文件
│   ├── index.js        # 入口文件
│   └── index.css       # 全局样式
├── server.py           # Python后端
├── requirements.txt    # Python依赖
├── package.json        # Node.js依赖
└── README.md          # 项目说明
```

### 自定义配置

#### 修改端口
编辑 `server.py` 中的端口配置：

```python
app.run(host='0.0.0.0', port=5000, debug=False)
```

## 🎯 解题思路

这是一个SSTI挑战，目标是绕过防护并读取flag文件。需要寻找其他方法：

1. **利用Jinja2内置函数**
2. **使用字符串拼接绕过关键词检测**
3. **利用模板上下文中的变量**
4. **寻找防护的绕过方法**

## 📝 许可证

This project is licensed under the  MIT [LICENSE](LICENSE)  

## 👨‍💻 作者

Eecho

联系我：

- 我的blog:www.eecho.top

---

**注意**: 这是一个教育目的的CTF挑战，请勿用于恶意攻击。 

---

