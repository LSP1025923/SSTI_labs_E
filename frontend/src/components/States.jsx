import { AlertTriangleIcon, RefreshIcon, TerminalIcon } from '../icons.jsx';

/** /api/lab-info 失败时的错误态：显示 HTTP 状态 + 原因 + 重试按钮，绝不白屏。 */
export default function FatalError({ info, onRetry, retrying }) {
  return (
    <div className="fatal-wrap">
      <div className="panel fatal-state" role="alert">
        <span className="fatal-icon">
          <AlertTriangleIcon size={34} />
        </span>
        <h1 className="fatal-title">无法加载靶场信息</h1>
        <p className="fatal-sub">控制台需要 <code className="code-inline">GET /api/lab-info</code> 才能初始化。</p>

        <dl className="fatal-kv">
          <div>
            <dt>HTTP 状态</dt>
            <dd>{info && info.status ? String(info.status) : '（无响应 / 网络错误）'}</dd>
          </div>
          <div>
            <dt>原因</dt>
            <dd>{info && info.message ? info.message : '未知错误'}</dd>
          </div>
          <div>
            <dt>请求</dt>
            <dd>
              <code className="code-inline">GET /api/lab-info</code>
            </dd>
          </div>
        </dl>

        <button type="button" className="btn btn-primary" onClick={onRetry} disabled={retrying}>
          {retrying ? <span className="inline-spinner" /> : <RefreshIcon size={15} />}
          {retrying ? '重试中…' : '重试'}
        </button>
      </div>
    </div>
  );
}

/** 首屏加载态。 */
export function LoadingScreen({ label = '正在连接靶场 /api/lab-info …' }) {
  return (
    <div className="fatal-wrap">
      <div className="panel loading-state">
        <span className="loading-logo">
          <TerminalIcon size={30} />
        </span>
        <p className="loading-text">{label}</p>
        <span className="loading-bar" aria-hidden="true" />
      </div>
    </div>
  );
}
