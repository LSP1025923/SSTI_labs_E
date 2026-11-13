import { BanIcon, BulbIcon, TerminalIcon } from '../icons.jsx';

/**
 * 顶栏：lab title / subtitle / id 全部来自 /api/lab-info。
 * no_egress 为 true 时显示醒目徽标，并把 no_egress_note 同时作为 tooltip 与横幅。
 */
export default function Header({ info, hintOpen, onToggleHint }) {
  const title = info.title || info.id || 'SSTI Lab';
  const noEgress = info.no_egress === true;
  const note = typeof info.no_egress_note === 'string' ? info.no_egress_note.trim() : '';

  return (
    <header className="app-header panel">
      <div className="header-main">
        <div className="header-brand">
          <span className="header-logo" aria-hidden="true">
            <TerminalIcon size={26} />
          </span>
          <div className="header-text">
            <h1 className="header-title">{title}</h1>
            {info.subtitle ? <p className="header-subtitle">{info.subtitle}</p> : null}
            <div className="header-tags">
              {info.id ? <span className="tag tag-id">LAB ID · {info.id}</span> : null}
              {info.engine_title ? <span className="tag">{info.engine_title}</span> : null}
              {info.flag_format ? <span className="tag tag-flag">FLAG {info.flag_format}</span> : null}
              {noEgress ? (
                <span className="badge badge-danger" title={note || '容器已切断出网'}>
                  <BanIcon size={14} /> ⛔ 不出网 / NO EGRESS
                </span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="header-actions">
          <button
            type="button"
            className={`btn btn-ghost${hintOpen ? ' is-active' : ''}`}
            onClick={onToggleHint}
            aria-expanded={hintOpen}
          >
            <BulbIcon size={15} /> 思路提示
          </button>
        </div>
      </div>

      {noEgress && note ? (
        <p className="egress-banner" role="note">
          <BanIcon size={15} />
          <span>{note}</span>
        </p>
      ) : null}

      {info.description ? <p className="header-desc">{info.description}</p> : null}
    </header>
  );
}
