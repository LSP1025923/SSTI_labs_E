import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles/app.css';

const container = document.getElementById('root');

if (!container) {
  // index.html 一定包含 #root；这里只是防御性兜底，避免出现白屏。
  document.body.innerHTML =
    '<pre style="color:#ff3366;font-family:monospace;padding:16px">前端挂载失败：未找到 #root 节点。</pre>';
} else {
  createRoot(container).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
