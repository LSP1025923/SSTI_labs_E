import { AlertTriangleIcon, CheckCircleIcon, EyeOffIcon, FlagIcon, TerminalIcon, XCircleIcon } from '../icons.jsx';

function Celebration() {
  return (
    <div className="flag-banner" role="status">
      <span className="flag-icon">
        <FlagIcon size={22} />
      </span>
      <div className="flag-text">
        <strong>🎉 FLAG FOUND —— 恭喜拿到 flag！</strong>
        <span>output 中检测到靶场 flag 内容，本关通过。</span>
      </div>
    </div>
  );
}

/**
 * 渲染结果面板。
 * 数据来源：POST /api/render 的响应（ok / output / truncated / flag_found / engine / level / mode）。
 */
export default function ResultPanel({ result, busy, error, level, engine }) {
  const hasResult = Boolean(result);
  const ok = hasResult && result.ok === true;
  const output = hasResult && result.output != null ? String(result.output) : '';

  return (
    <section className={`panel result-panel${hasResult ? (ok ? ' is-ok' : ' is-bad') : ''}`}>
      <div className="panel-head">
        <h2 className="panel-title">
          <TerminalIcon size={17} /> 渲染结果
        </h2>
        <div className="panel-head-tags">
          {hasResult ? (
            <>
              {result.engine ? <span className="tag">{String(result.engine)}</span> : null}
              {result.level != null ? <span className="tag tag-id">LEVEL {String(result.level)}</span> : null}
              {result.mode ? <span className="tag">{result.mode === 'god' ? 'GOD' : 'PRACTICE'}</span> : null}
            </>
          ) : engine ? (
            <span className="tag">{engine}</span>
          ) : null}
        </div>
      </div>

      {error ? (
        <div className="message message-error" role="alert">
          <XCircleIcon size={17} />
          <span>{error}</span>
        </div>
      ) : null}

      {!hasResult && !error ? (
        <p className="muted">
          {busy ? '正在请求 /api/render …' : '还没有结果。写好模板后按「提交渲染」或 Ctrl/⌘ + Enter。'}
        </p>
      ) : null}

      {hasResult ? (
        <>
          <div className={`status-line ${ok ? 'is-ok' : 'is-bad'}`}>
            {ok ? <CheckCircleIcon size={16} /> : <AlertTriangleIcon size={16} />}
            <span>{ok ? '渲染成功 (ok: true)' : '渲染失败 / 未通过 (ok: false)'}</span>
            {level && level.blind ? (
              <span className="status-hint">
                <EyeOffIcon size={13} /> 盲注关卡只回显 correct / wrong
              </span>
            ) : null}
          </div>

          {result.flag_found === true ? <Celebration /> : null}

          {result.truncated === true ? (
            <p className="notice notice-warn">
              <AlertTriangleIcon size={14} /> 输出过长已被服务端截断（truncated: true），完整内容请缩小 payload。
            </p>
          ) : null}

          <div className="output-display">
            {output ? <pre translate="no">{output}</pre> : <pre className="pre-empty">（空输出）</pre>}
          </div>
        </>
      ) : null}
    </section>
  );
}
