import { EyeOffIcon, ShieldIcon, WifiOffIcon } from '../icons.jsx';

const WAF_KIND_LABELS = {
  substring: '子串过滤',
  chars: '字符黑名单',
  regex: '正则过滤',
  prefix: '前缀限制',
  combo: '组合过滤',
};

export function wafKindLabel(kind) {
  if (!kind) return '过滤';
  const key = String(kind).toLowerCase();
  return WAF_KIND_LABELS[key] ? `${WAF_KIND_LABELS[key]} (${kind})` : String(kind);
}

/** 关卡侧边栏：title + summary + blind 标记，当前关卡高亮。 */
export default function LevelList({ levels, currentId, onSelect }) {
  if (!Array.isArray(levels) || levels.length === 0) {
    return (
      <div className="empty-state">
        <p className="empty-title">该靶场没有可用关卡</p>
        <p className="empty-hint">/api/lab-info 的 levels 为空，请检查靶场初始化。</p>
      </div>
    );
  }

  return (
    <ul className="level-list">
      {levels.map((level) => {
        const id = String(level.id);
        const active = id === currentId;
        return (
          <li key={id}>
            <button
              type="button"
              className={`level-item${active ? ' is-active' : ''}`}
              onClick={() => onSelect(id)}
              aria-current={active ? 'true' : undefined}
            >
              <span className="level-item-top">
                <span className="level-title">{level.title || `关卡 ${id}`}</span>
                <span className="level-markers">
                  {level.blind ? (
                    <span className="tag tag-blind" title="盲注关卡：只回显 correct / wrong">
                      <EyeOffIcon size={12} /> BLIND
                    </span>
                  ) : null}
                  {level.no_egress ? (
                    <span className="tag tag-nodns" title="本关额外切断出网">
                      <WifiOffIcon size={12} /> NO EGRESS
                    </span>
                  ) : null}
                  {level.waf ? (
                    <span className="tag tag-waf" title={level.waf.note || '存在 WAF'}>
                      <ShieldIcon size={12} /> WAF
                    </span>
                  ) : null}
                </span>
              </span>
              {level.summary ? <span className="level-summary">{level.summary}</span> : null}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
