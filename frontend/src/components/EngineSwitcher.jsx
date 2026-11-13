import { LayersIcon } from '../icons.jsx';

/**
 * 引擎切换器：engines.length <= 1 时整体不渲染（契约要求）。
 * 切换后由父组件重新拉取 /api/levels?engine=<id>。
 */
export default function EngineSwitcher({ engines, value, onChange, busy = false }) {
  if (!Array.isArray(engines) || engines.length <= 1) return null;

  return (
    <div className="engine-switcher" role="group" aria-label="模板引擎">
      <span className="engine-label">
        <LayersIcon size={15} /> 模板引擎
      </span>
      <div className="engine-options" role="tablist">
        {engines.map((engine) => {
          const id = String(engine.id);
          const active = id === value;
          return (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={active}
              className={`chip-btn${active ? ' is-active' : ''}`}
              onClick={() => !active && onChange(id)}
              disabled={busy}
            >
              {engine.title || id}
            </button>
          );
        })}
      </div>
      {busy ? <span className="inline-spinner" title="加载关卡中…" aria-label="加载关卡中" /> : null}
    </div>
  );
}
