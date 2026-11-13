import { useEffect } from 'react';
import { BulbIcon, EyeOffIcon, ShieldIcon, WifiOffIcon, XCircleIcon } from '../icons.jsx';

/**
 * 「思路提示」抽屉。
 * 只展示 lab-info 里带的 hint（关卡级优先，靶场级兜底），
 * 前端不内置任何完整答案 / payload 解法。
 */
export default function HintDrawer({ open, onClose, level, labHint, labTitle }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  const levelHint = level && typeof level.hint === 'string' ? level.hint.trim() : '';

  return (
    <>
      <div className={`drawer-backdrop${open ? ' is-open' : ''}`} onClick={onClose} aria-hidden="true" />
      <aside
        className={`drawer${open ? ' is-open' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label="思路提示"
        aria-hidden={open ? 'false' : 'true'}
      >
        <div className="drawer-head">
          <h2 className="drawer-title">
            <BulbIcon size={17} /> 思路提示
          </h2>
          <button type="button" className="btn btn-ghost" onClick={onClose} aria-label="关闭思路提示">
            <XCircleIcon size={15} /> 关闭
          </button>
        </div>

        <div className="drawer-body">
          <p className="muted small">
            {labTitle ? `${labTitle} · ` : ''}
            {level ? `当前关卡 ${level.title || level.id}` : '未选择关卡'}
          </p>

          {level ? (
            <div className="drawer-tags">
              {level.blind ? (
                <span className="tag tag-blind">
                  <EyeOffIcon size={12} /> 盲注
                </span>
              ) : null}
              {level.no_egress ? (
                <span className="tag tag-nodns">
                  <WifiOffIcon size={12} /> 无出网
                </span>
              ) : null}
              {level.waf ? (
                <span className="tag tag-waf">
                  <ShieldIcon size={12} /> WAF · {String(level.waf.kind || '')}
                </span>
              ) : null}
            </div>
          ) : null}

          {levelHint ? (
            <div className="hint-card">
              <h3>本关提示</h3>
              <p className="hint-text">{levelHint}</p>
            </div>
          ) : (
            <p className="muted small">本关未提供 hint 字段。</p>
          )}

          {labHint && labHint !== levelHint ? (
            <div className="hint-card">
              <h3>靶场通用提示</h3>
              <p className="hint-text">{labHint}</p>
            </div>
          ) : null}

          <p className="drawer-footnote">
            抽屉只展示靶场自带提示，前端不内置完整解法；拿到 flag 后请在练习模式下提交。
          </p>
        </div>
      </aside>
    </>
  );
}
