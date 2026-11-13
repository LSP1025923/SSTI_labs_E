import { useEffect, useRef } from 'react';
import ModeToggle from './ModeToggle.jsx';
import { PlayIcon, RefreshIcon, ZapIcon } from '../icons.jsx';

/**
 * 模板编辑器：等宽 textarea，Ctrl/Cmd+Enter 提交。
 * 提交内容完全由父组件决定，这里只负责收集输入与快捷键。
 */
export default function TemplateEditor({
  value,
  onChange,
  onSubmit,
  onClear,
  mode,
  onModeChange,
  busy,
  disabled,
  disabledReason,
  engineTitle,
  levelTitle,
}) {
  const textareaRef = useRef(null);

  useEffect(() => {
    const node = textareaRef.current;
    if (node) node.focus();
  }, []);

  const handleKeyDown = (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      if (!busy && !disabled) onSubmit();
    }
  };

  return (
    <section className="panel editor-panel">
      <div className="panel-head">
        <h2 className="panel-title">
          <ZapIcon size={17} /> 模板输入
        </h2>
        <div className="panel-head-tags">
          {engineTitle ? <span className="tag">{engineTitle}</span> : null}
          {levelTitle ? <span className="tag tag-id">{levelTitle}</span> : null}
        </div>
      </div>

      <ModeToggle mode={mode} onChange={onModeChange} />

      <label className="sr-only" htmlFor="template-input">
        模板内容
      </label>
      <textarea
        id="template-input"
        ref={textareaRef}
        className="template-input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        spellCheck={false}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        translate="no"
        rows={7}
        placeholder="在此输入模板 / payload，例如 {{ 7*7 }}"
        disabled={disabled}
      />

      <div className="editor-actions">
        <button
          type="button"
          className="btn btn-primary"
          onClick={onSubmit}
          disabled={busy || disabled || !value.trim()}
        >
          {busy ? <span className="inline-spinner" /> : <PlayIcon size={15} />}
          {busy ? '渲染中…' : '提交渲染'}
          <kbd className="kbd">Ctrl/⌘ + Enter</kbd>
        </button>
        <button type="button" className="btn btn-ghost" onClick={onClear} disabled={busy || !value}>
          <RefreshIcon size={15} /> 清空
        </button>
        {disabled && disabledReason ? <span className="muted small">{disabledReason}</span> : null}
      </div>
    </section>
  );
}
