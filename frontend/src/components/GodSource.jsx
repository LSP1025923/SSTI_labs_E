import { useEffect, useRef, useState } from 'react';
import { BookIcon, RefreshIcon } from '../icons.jsx';
import { fetchGodSource, describeError } from '../api.js';

/**
 * 「关卡源码」按钮 + 源码展示（仅上帝模式）。
 * 调用 GET /api/god/source?engine=<id>&level=<id>，展示响应里的 source。
 * 点击后才请求；一旦打开过，切换引擎/关卡会自动重新拉取。
 */
export default function GodSource({ engine, level, enabled }) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState({ status: 'idle', source: '', path: '', error: '' });
  const requestedFor = useRef(null);

  useEffect(() => {
    if (!enabled) {
      setOpen(false);
      setState({ status: 'idle', source: '', path: '', error: '' });
      requestedFor.current = null;
    }
  }, [enabled]);

  const load = async () => {
    const key = `${engine}::${level}`;
    requestedFor.current = key;
    setState((prev) => ({ ...prev, status: 'loading', error: '' }));
    try {
      const data = await fetchGodSource({ engine, level });
      if (requestedFor.current !== key) return;
      if (data && data.ok === false) {
        setState({ status: 'error', source: '', path: '', error: data.error || '无法加载源码' });
        return;
      }
      setState({
        status: 'ok',
        source: data && data.source != null ? String(data.source) : '',
        path: data && data.path ? String(data.path) : '',
        error: '',
      });
    } catch (err) {
      if (requestedFor.current !== key) return;
      const info = describeError(err, '加载关卡源码失败');
      setState({
        status: 'error',
        source: '',
        path: '',
        error: `${info.message}${info.status ? ` (HTTP ${info.status})` : ''}`,
      });
    }
  };

  // 已经打开过的状态下，切换引擎 / 关卡自动重取。
  useEffect(() => {
    if (!enabled || !open) return;
    if (requestedFor.current === `${engine}::${level}`) return;
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, open, engine, level]);

  if (!enabled) return null;

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && state.status === 'idle') void load();
  };

  return (
    <section className="panel source-panel">
      <div className="panel-head">
        <h2 className="panel-title">
          <BookIcon size={17} /> 关卡源码
        </h2>
        <div className="panel-head-tags">
          <button type="button" className={`btn btn-ghost${open ? ' is-active' : ''}`} onClick={toggle}>
            <BookIcon size={15} /> {open ? '收起关卡源码' : '关卡源码'}
          </button>
          {open ? (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => void load()}
              disabled={state.status === 'loading'}
            >
              <RefreshIcon size={15} /> 重新加载
            </button>
          ) : null}
        </div>
      </div>

      <p className="muted small">
        <code>GET /api/god/source?engine={engine}&amp;level={level}</code>
      </p>

      {open ? (
        state.status === 'loading' ? (
          <p className="muted">加载中…</p>
        ) : state.status === 'error' ? (
          <p className="notice notice-error">{state.error}</p>
        ) : (
          <>
            {state.path ? (
              <p className="muted small">
                来源：<code className="code-inline">{state.path}</code>
              </p>
            ) : null}
            <pre className="source-pre" translate="no">
              <code>{state.source || '（空源码）'}</code>
            </pre>
          </>
        )
      ) : null}
    </section>
  );
}
