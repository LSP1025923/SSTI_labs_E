import axios from 'axios';

/**
 * 靶场 HTTP API 客户端。
 *
 * 契约见 docs/API.md（v1，冻结）。这里只暴露契约里存在的字段/接口，
 * 不发明任何额外字段；所有请求都走相对根路径 `/api/...`，
 * 因此产物可以从容器根路径 `/` 直接提供。
 */
export const http = axios.create({
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
  // 靶场会返回 4xx/5xx；这些交给调用方处理，axios 只负责抛出。
  validateStatus: (status) => status >= 200 && status < 300,
});

/** GET /api/lab-info —— 前端启动时唯一必需的调用。 */
export async function fetchLabInfo() {
  const { data } = await http.get('/api/lab-info');
  return data;
}

/** GET /api/levels?engine=<id> —— 切换引擎时刷新关卡列表。 */
export async function fetchLevels(engine) {
  const { data } = await http.get('/api/levels', {
    params: engine ? { engine } : {},
  });
  return data;
}

/** POST /api/render —— 核心渲染接口。 */
export async function postRender({ engine, level, mode, template }) {
  const body = { mode, template };
  if (engine !== undefined && engine !== null && engine !== '') body.engine = engine;
  if (level !== undefined && level !== null && level !== '') body.level = level;
  const { data } = await http.post('/api/render', body);
  return data;
}

/** GET /api/god/source?engine=&level= —— 上帝模式：取关卡出题源码。 */
export async function fetchGodSource({ engine, level }) {
  const params = {};
  if (engine) params.engine = engine;
  if (level !== undefined && level !== null && level !== '') params.level = level;
  const { data } = await http.get('/api/god/source', { params });
  return data;
}

function pickServerMessage(data) {
  if (data == null) return '';
  if (typeof data === 'string') return data.slice(0, 400);
  if (typeof data === 'object') {
    if (typeof data.error === 'string' && data.error) return data.error.slice(0, 400);
    if (typeof data.message === 'string' && data.message) return data.message.slice(0, 400);
    if (typeof data.detail === 'string' && data.detail) return data.detail.slice(0, 400);
  }
  return '';
}

/**
 * 把 axios 错误归一化成 { status, statusText, message }，
 * 便于界面始终能显示「HTTP 状态 + 可读原因」，绝不白屏。
 */
export function describeError(err, fallback = '请求失败') {
  if (!err) return { status: null, statusText: '', message: fallback };

  if (err.response) {
    const status = err.response.status;
    const statusText = err.response.statusText || '';
    const serverMessage = pickServerMessage(err.response.data);
    return {
      status,
      statusText,
      message: serverMessage || `${fallback}（HTTP ${status}${statusText ? ' ' + statusText : ''}）`,
    };
  }

  if (err.code === 'ECONNABORTED' || err.code === 'ETIMEDOUT') {
    return { status: null, statusText: '', message: '请求超时：靶场服务无响应。' };
  }

  if (err.request) {
    return {
      status: null,
      statusText: '',
      message: '无法连接靶场服务：请确认容器仍在运行，且 /api 可访问。',
    };
  }

  return { status: null, statusText: '', message: err.message || fallback };
}
