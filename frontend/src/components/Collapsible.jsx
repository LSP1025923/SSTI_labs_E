import { useEffect, useRef, useState } from 'react';
import { ChevronIcon } from '../icons.jsx';

/**
 * 通用可折叠面板（受控 / 非受控都支持）。
 * 用于：本关提示、上帝模式诊断块。
 */
export default function Collapsible({
  title,
  icon = null,
  defaultOpen = false,
  open: openProp,
  onToggle,
  tone = 'default',
  meta = null,
  children,
  className = '',
  id,
}) {
  const isControlled = typeof openProp === 'boolean';
  const [innerOpen, setInnerOpen] = useState(defaultOpen);
  const open = isControlled ? openProp : innerOpen;
  const bodyId = useRef(id || `collapsible-${Math.random().toString(36).slice(2, 9)}`).current;

  useEffect(() => {
    if (!isControlled) setInnerOpen(defaultOpen);
    // defaultOpen 变化时同步（仅在非受控模式生效）
  }, [defaultOpen, isControlled]);

  const toggle = () => {
    if (isControlled) {
      if (typeof onToggle === 'function') onToggle(!open);
    } else {
      setInnerOpen((v) => !v);
    }
  };

  return (
    <div className={`collapsible collapsible-${tone} ${open ? 'is-open' : ''} ${className}`.trim()}>
      <button
        type="button"
        className="collapsible-head"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={bodyId}
      >
        <ChevronIcon open={open} className="collapsible-chev" />
        {icon ? <span className="collapsible-icon">{icon}</span> : null}
        <span className="collapsible-title">{title}</span>
        {meta ? <span className="collapsible-meta">{meta}</span> : null}
      </button>
      {open ? (
        <div className="collapsible-body" id={bodyId}>
          {children}
        </div>
      ) : null}
    </div>
  );
}
