import Collapsible from './Collapsible.jsx';
import { BugIcon, DiffIcon } from '../icons.jsx';

function Value({ value, mono = true, block = false }) {
  if (value === null || value === undefined || value === '') {
    return <span className="muted">（无）</span>;
  }
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  if (block) {
    return (
      <pre className="pre-mini" translate="no">
        {text}
      </pre>
    );
  }
  return <code className={mono ? 'code-inline' : undefined}>{text}</code>;
}

/**
 * 上帝模式诊断块（仅 mode=god 时渲染）。
 * 字段全部来自 POST /api/render 的响应，缺省字段不编造、不显示。
 */
export default function GodDiagnostics({ result, defaultOpen = true }) {
  const hasResult = Boolean(result);
  const rawOutputPresent =
    hasResult && result.raw_output !== null && result.raw_output !== undefined && result.raw_output !== '';

  return (
    <Collapsible
      title="上帝模式诊断"
      icon={<BugIcon size={15} />}
      tone="god"
      defaultOpen={defaultOpen}
      meta={<span className="tag tag-god">GOD · 出题人可见</span>}
      className="god-diagnostics"
    >
      {!hasResult ? (
        <p className="muted small">提交一次渲染后，这里会显示 WAF 处理后的模板、异常与出题源码位置。</p>
      ) : (
        <div className="kv-grid">
          <div className="kv-row kv-row-full">
            <span className="kv-key">
              <DiffIcon size={13} /> template_after_waf
            </span>
            <div className="kv-val">
              <Value value={result.template_after_waf} block />
            </div>
          </div>

          <div className="kv-row">
            <span className="kv-key">ok</span>
            <div className="kv-val">
              <Value value={typeof result.ok === 'boolean' ? String(result.ok) : result.ok} />
            </div>
          </div>

          <div className="kv-row">
            <span className="kv-key">exception_type</span>
            <div className="kv-val">
              <Value value={result.exception_type} />
            </div>
          </div>

          <div className="kv-row">
            <span className="kv-key">source_class</span>
            <div className="kv-val">
              <Value value={result.source_class} />
            </div>
          </div>

          <div className="kv-row">
            <span className="kv-key">source_file</span>
            <div className="kv-val">
              <Value value={result.source_file} />
            </div>
          </div>

          <div className="kv-row kv-row-full">
            <span className="kv-key">error</span>
            <div className="kv-val">
              <Value value={result.error} block />
            </div>
          </div>

          <div className="kv-row kv-row-full">
            <span className="kv-key">raw_output</span>
            <div className="kv-val">
              {rawOutputPresent ? (
                <pre className="pre-mini pre-terminal" translate="no">
                  {String(result.raw_output)}
                </pre>
              ) : (
                <span className="muted small">（本关 / 本次响应未返回 raw_output）</span>
              )}
            </div>
          </div>
        </div>
      )}
    </Collapsible>
  );
}
