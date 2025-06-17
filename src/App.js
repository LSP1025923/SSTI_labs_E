import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Terminal, Code, AlertTriangle, CheckCircle, XCircle, Zap, Shield, Target } from 'lucide-react';
import './App.css';

function App() {
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const cursorRef = useRef(null);

  // 鼠标跟随效果
  useEffect(() => {
    const handleMouseMove = (e) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
      if (cursorRef.current) {
        cursorRef.current.style.left = e.clientX + 'px';
        cursorRef.current.style.top = e.clientY + 'px';
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    setLoading(true);
    setError('');
    setSuccess('');
    setOutput('');

    try {
      const response = await axios.post('http://localhost:5000/render', {
        template: input
      });
      
      setOutput(response.data.result);
      if (response.data.flag) {
        setSuccess('🎉 恭喜！你成功获取到了flag！');
      }
    } catch (err) {
      setError(err.response?.data?.error || '请求失败，请检查服务器是否运行');
    } finally {
      setLoading(false);
    }
  };

  const examples = [
    { name: '基础示例', template: 'Hello {{ name }}!' },
    { name: '数学运算', template: '1 + 1 = {{ 1 + 1 }}' },
    { name: '列表操作', template: '{{ [1,2,3] | length }}' },
    { name: '字符串操作', template: '{{ "hello" | upper }}' }
  ];

  const loadExample = (template) => {
    setInput(template);
  };

  return (
    <div className="app">
      {/* 粒子背景 */}
      <div className="particles-bg"></div>
      
      {/* 扫描线动画 */}
      <div className="scan-line"></div>
      
      {/* 鼠标跟随效果 */}
      <div ref={cursorRef} className="cursor-glow"></div>
      
      {/* 数据流动画 */}
      <div className="data-stream"></div>

      <div className="container">
        <header className="header">
          <div className="logo">
            <Terminal className="logo-icon" />
            <h1>Eecho's SSTI</h1>
          </div>
          <p className="subtitle">Cyberpunk Template Injection Challenge</p>
        </header>

        <div className="main-content">
          <div className="challenge-info">
            <div className="info-card hologram-container">
              <h3><Code className="icon" /> 挑战描述</h3>
              <p>欢迎来到Eecho的赛博朋克世界！这是一个Python Jinja2模板注入挑战。你的目标是绕过防护并获取服务器上的flag。</p>
            </div>
          </div>

          <div className="input-section hologram-container">
            <form onSubmit={handleSubmit} className="template-form">
              <div className="form-group">
                <label htmlFor="template-input">
                  <Zap className="icon" /> 模板输入
                </label>
                <textarea
                  id="template-input"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="输入你的Jinja2模板，例如: Hello {{ name }}!"
                  className="template-input"
                  rows="6"
                />
              </div>
              
              <div className="examples">
                <h4>示例模板：</h4>
                <div className="example-buttons">
                  {examples.map((example, index) => (
                    <button
                      key={index}
                      type="button"
                      onClick={() => loadExample(example.template)}
                      className="example-btn"
                    >
                      {example.name}
                    </button>
                  ))}
                </div>
              </div>

              <button 
                type="submit" 
                className="submit-btn"
                disabled={loading || !input.trim()}
              >
                {loading ? '处理中...' : '渲染模板'}
              </button>
            </form>
          </div>

          <div className="output-section hologram-container">
            <h3><Terminal className="icon" /> 渲染结果</h3>
            
            {error && (
              <div className="message error">
                <XCircle className="icon" />
                <span>{error}</span>
              </div>
            )}
            
            {success && (
              <div className="message success">
                <CheckCircle className="icon" />
                <span>{success}</span>
              </div>
            )}
            
            {output && (
              <div className="output-display">
                <pre>{output}</pre>
              </div>
            )}
          </div>
        </div>

        <footer className="footer">
          <p>© 2025 Eecho's Cyberpunk CTF Challenge</p>
        </footer>
      </div>
    </div>
  );
}

export default App; 