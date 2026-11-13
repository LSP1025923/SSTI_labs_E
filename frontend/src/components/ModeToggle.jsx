import { BugIcon } from '../icons.jsx';

const MODES = [
  {
    id: 'practice',
    label: '练习模式',
    en: 'PRACTICE',
    title: '练习模式：玩家视角，只看到回显结果。',
  },
  {
    id: 'god',
    label: '上帝模式',
    en: 'GOD',
    title: '上帝模式：出题人 / 运维诊断视角，会回显 WAF 处理后的模板、异常堆栈与关卡源码。',
  },
];

/**
 * 模式切换：practice / god。
 * 上帝模式是出题人诊断模式，这里明确标注，避免玩家误以为它是「更强的一关」。
 */
export default function ModeToggle({ mode, onChange }) {
  return (
    <div className="mode-toggle">
      <div className="mode-buttons" role="radiogroup" aria-label="渲染模式">
        {MODES.map((item) => {
          const active = mode === item.id;
          return (
            <button
              key={item.id}
              type="button"
              role="radio"
              aria-checked={active}
              title={item.title}
              className={`mode-btn mode-${item.id}${active ? ' is-active' : ''}`}
              onClick={() => !active && onChange(item.id)}
            >
              <span className="mode-label">{item.label}</span>
              <span className="mode-en">{item.en}</span>
            </button>
          );
        })}
      </div>
      {mode === 'god' ? (
        <p className="mode-note">
          <BugIcon size={14} />
          <span>
            <strong>上帝模式</strong>：出题人诊断用。会额外回显 <code>template_after_waf</code>、异常类型、
            关卡源码位置等内部信息 —— 参赛选手请切回练习模式。
          </span>
        </p>
      ) : null}
    </div>
  );
}

export { MODES };
