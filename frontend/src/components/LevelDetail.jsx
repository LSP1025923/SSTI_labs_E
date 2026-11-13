import Collapsible from './Collapsible.jsx';
import { BulbIcon, EyeOffIcon, ShieldIcon, TargetIcon, WifiOffIcon } from '../icons.jsx';
import { wafKindLabel } from './LevelList.jsx';

/**
 * 当前关卡详情：description + 可折叠 hint + WAF 规则摘要（kind / items chips / note）。
 * 所有内容都来自 /api/lab-info 的 levels[]，前端不内置任何题目文案或答案。
 */
export default function LevelDetail({ level, labHint }) {
  if (!level) {
    return (
      <section className="panel level-detail">
        <div className="panel-head">
          <h2 className="panel-title">
            <TargetIcon size={17} /> 关卡详情
          </h2>
        </div>
        <p className="muted">请在左侧选择一个关卡。</p>
      </section>
    );
  }

  const waf = level.waf && typeof level.waf === 'object' ? level.waf : null;
  const items = waf && Array.isArray(waf.items) ? waf.items : [];
  const hint = typeof level.hint === 'string' ? level.hint.trim() : '';

  return (
    <section className="panel level-detail">
      <div className="panel-head">
        <h2 className="panel-title">
          <TargetIcon size={17} /> {level.title || `关卡 ${level.id}`}
        </h2>
        <div className="panel-head-tags">
          <span className="tag tag-id">LEVEL {String(level.id)}</span>
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
        </div>
      </div>

      {level.description ? <p className="level-desc">{level.description}</p> : null}
      {level.summary && level.summary !== level.description ? (
        <p className="level-summary-line">概要：{level.summary}</p>
      ) : null}

      {waf ? (
        <div className="waf-box">
          <h3 className="waf-title">
            <ShieldIcon size={15} /> WAF 规则摘要
            <span className="tag tag-waf">{wafKindLabel(waf.kind)}</span>
          </h3>
          {items.length > 0 ? (
            <div className="chips">
              {items.map((item, index) => (
                <code className="chip" key={`${String(item)}-${index}`}>
                  {String(item)}
                </code>
              ))}
            </div>
          ) : (
            <p className="muted small">（本关未给出可枚举的规则条目）</p>
          )}
          {waf.note ? <p className="waf-note">{waf.note}</p> : null}
        </div>
      ) : null}

      {hint ? (
        <Collapsible title="本关提示（可折叠）" icon={<BulbIcon size={15} />} tone="hint">
          <p className="hint-text">{hint}</p>
        </Collapsible>
      ) : null}

      {!hint && labHint ? (
        <Collapsible title="靶场通用提示（可折叠）" icon={<BulbIcon size={15} />} tone="hint">
          <p className="hint-text">{labHint}</p>
        </Collapsible>
      ) : null}
    </section>
  );
}
