import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';

import Header from './components/Header.jsx';
import EngineSwitcher from './components/EngineSwitcher.jsx';
import LevelList from './components/LevelList.jsx';
import LevelDetail from './components/LevelDetail.jsx';
import TemplateEditor from './components/TemplateEditor.jsx';
import ResultPanel from './components/ResultPanel.jsx';
import GodDiagnostics from './components/GodDiagnostics.jsx';
import GodSource from './components/GodSource.jsx';
import HintDrawer from './components/HintDrawer.jsx';
import FatalError, { LoadingScreen } from './components/States.jsx';
import { describeError, fetchLabInfo, fetchLevels, postRender } from './api.js';
import { applyDocumentTitle, applyTheme } from './theme.js';
import { AlertTriangleIcon, RefreshIcon, TargetIcon, ZapIcon } from './icons.jsx';

/** 三个纯装饰性的赛博朋克背景层（CSS-only，无外部资源）。 */
function Backdrop() {
  return (
    <>
      <div className="fx-particles" aria-hidden="true" />
      <div className="fx-grid" aria-hidden="true" />
      <div className="fx-scanline" aria-hidden="true" />
    </>
  );
}

function normalizeLevels(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item) => item && typeof item === 'object' && item.id !== undefined && item.id !== null)
    .map((item) => ({ ...item, id: String(item.id) }));
}

function firstLevelId(levels) {
  return levels.length > 0 ? levels[0].id : null;
}

export default function App() {
  const [status, setStatus] = useState('loading'); // loading | ready | error
  const [loadError, setLoadError] = useState(null);
  const [retrying, setRetrying] = useState(false);

  const [info, setInfo] = useState(null);
  const [engine, setEngine] = useState(null);
  const [levels, setLevels] = useState([]);
  const [levelId, setLevelId] = useState(null);
  const [levelsBusy, setLevelsBusy] = useState(false);
  const [levelsError, setLevelsError] = useState('');

  const [mode, setMode] = useState('practice');
  const [template, setTemplate] = useState('');
  const [result, setResult] = useState(null);
  const [renderBusy, setRenderBusy] = useState(false);
  const [renderError, setRenderError] = useState('');

  const [hintOpen, setHintOpen] = useState(false);

  const cursorRef = useRef(null);
  const bootedRef = useRef(false);

  /* ---------------------------------------------------------------- 初始化 */

  const loadLabInfo = useCallback(async ({ isRetry = false } = {}) => {
    if (isRetry) setRetrying(true);
    else setStatus('loading');
    setLoadError(null);

    try {
      const data = await fetchLabInfo();
      const labInfo = data && typeof data === 'object' ? data : {};

      applyTheme(labInfo.theme);
      applyDocumentTitle(labInfo);

      const engines = Array.isArray(labInfo.engines) ? labInfo.engines.filter((e) => e && e.id) : [];
      const initialEngine =
        (labInfo.engine && String(labInfo.engine)) || (engines[0] ? String(engines[0].id) : null);
      const initialLevels = normalizeLevels(labInfo.levels);

      setInfo(labInfo);
      setEngine(initialEngine);
      setLevels(initialLevels);
      setLevelId(firstLevelId(initialLevels));
      setLevelsError('');
      setLevelsBusy(false);
      setResult(null);
      setRenderError('');
      setStatus('ready');
    } catch (err) {
      setLoadError(describeError(err, '加载靶场信息失败'));
      setStatus('error');
    } finally {
      setRetrying(false);
    }
  }, []);

  useEffect(() => {
    if (bootedRef.current) return;
    bootedRef.current = true;
    void loadLabInfo();
  }, [loadLabInfo]);

  /* ------------------------------------------------------------ 鼠标光晕 */

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return undefined;
    if (!window.matchMedia('(pointer: fine)').matches) return undefined;
    const onMove = (event) => {
      const node = cursorRef.current;
      if (node) {
        node.style.transform = `translate3d(${event.clientX - 90}px, ${event.clientY - 90}px, 0)`;
      }
    };
    window.addEventListener('mousemove', onMove, { passive: true });
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  /* -------------------------------------------------------- 引擎 / 关卡 */

  const loadLevelsForEngine = useCallback(
    async (engineId, { keepLevelIfPresent = true } = {}) => {
      setLevelsBusy(true);
      setLevelsError('');
      try {
        const data = await fetchLevels(engineId);
        const nextLevels = normalizeLevels(data && data.levels);
        setLevels(nextLevels);
        setLevelId((prev) => {
          if (keepLevelIfPresent && prev && nextLevels.some((l) => l.id === prev)) return prev;
          return firstLevelId(nextLevels);
        });
        setResult(null);
        setRenderError('');
      } catch (err) {
        const detail = describeError(err, '加载关卡列表失败');
        setLevelsError(`${detail.message}${detail.status ? ` (HTTP ${detail.status})` : ''}`);
      } finally {
        setLevelsBusy(false);
      }
    },
    [],
  );

  const handleEngineChange = useCallback(
    (nextEngine) => {
      setEngine(nextEngine);
      void loadLevelsForEngine(nextEngine, { keepLevelIfPresent: false });
    },
    [loadLevelsForEngine],
  );

  const handleLevelSelect = useCallback((nextId) => {
    setLevelId(nextId);
    setResult(null);
    setRenderError('');
  }, []);

  /* -------------------------------------------------------------- 提交 */

  const handleSubmit = useCallback(async () => {
    if (renderBusy) return;
    if (!template.trim()) return;
    if (!engine && levels.length > 0 && !levelId) return;

    setRenderBusy(true);
    setRenderError('');
    try {
      const data = await postRender({
        engine,
        level: levelId,
        mode,
        template,
      });
      setResult(data && typeof data === 'object' ? data : {});
    } catch (err) {
      if (axios.isAxiosError && axios.isAxiosError(err)) {
        const detail = describeError(err, '渲染请求失败');
        setRenderError(`${detail.message}${detail.status ? ` (HTTP ${detail.status})` : ''}`);
      } else {
        setRenderError(describeError(err, '渲染请求失败').message);
      }
    } finally {
      setRenderBusy(false);
    }
  }, [engine, levelId, levels.length, mode, renderBusy, template]);

  const toggleHint = useCallback(() => setHintOpen((v) => !v), []);
  const closeHint = useCallback(() => setHintOpen(false), []);

  /* -------------------------------------------------------------- 派生 */

  const currentLevel = useMemo(
    () => levels.find((level) => level.id === levelId) || null,
    [levels, levelId],
  );

  const engineTitle = useMemo(() => {
    if (!info || !Array.isArray(info.engines)) return '';
    const hit = info.engines.find((item) => item && String(item.id) === engine);
    return hit ? hit.title || String(hit.id) : '';
  }, [info, engine]);

  const labHint = info && typeof info.hint === 'string' ? info.hint.trim() : '';
  const noLevels = levels.length === 0;
  const submitDisabled = noLevels && !levelId;

  /* -------------------------------------------------------------- 渲染 */

  if (status === 'loading') {
    return (
      <div className="app">
        <Backdrop />
        <div ref={cursorRef} className="fx-cursor" aria-hidden="true" />
        <LoadingScreen />
      </div>
    );
  }

  if (status === 'error' || !info) {
    return (
      <div className="app">
        <Backdrop />
        <div ref={cursorRef} className="fx-cursor" aria-hidden="true" />
        <FatalError info={loadError} onRetry={() => void loadLabInfo({ isRetry: true })} retrying={retrying} />
      </div>
    );
  }

  return (
    <div className="app">
      <Backdrop />
      <div ref={cursorRef} className="fx-cursor" aria-hidden="true" />

      <div className="app-shell">
        <Header info={info} hintOpen={hintOpen} onToggleHint={toggleHint} />

        <EngineSwitcher
          engines={info.engines}
          value={engine}
          onChange={handleEngineChange}
          busy={levelsBusy}
        />

        <div className="layout">
          <aside className="panel sidebar" aria-label="关卡列表">
            <div className="panel-head">
              <h2 className="panel-title">
                <TargetIcon size={17} /> 关卡列表
              </h2>
              <span className="tag tag-id">{levels.length} LEVELS</span>
            </div>

            {levelsError ? (
              <div className="message message-error sidebar-error" role="alert">
                <AlertTriangleIcon size={16} />
                <span>{levelsError}</span>
                <button
                  type="button"
                  className="btn btn-ghost btn-tiny"
                  onClick={() => void loadLevelsForEngine(engine)}
                >
                  <RefreshIcon size={14} /> 重试
                </button>
              </div>
            ) : null}

            <LevelList levels={levels} currentId={levelId} onSelect={handleLevelSelect} />
          </aside>

          <main className="content">
            <LevelDetail level={currentLevel} labHint={labHint} />

            <TemplateEditor
              value={template}
              onChange={setTemplate}
              onSubmit={() => void handleSubmit()}
              onClear={() => setTemplate('')}
              mode={mode}
              onModeChange={setMode}
              busy={renderBusy}
              disabled={submitDisabled}
              disabledReason={
                submitDisabled ? '该靶场未返回任何关卡，无法提交渲染。' : ''
              }
              engineTitle={engineTitle}
              levelTitle={currentLevel ? currentLevel.title || currentLevel.id : ''}
            />

            <ResultPanel
              result={result}
              busy={renderBusy}
              error={renderError}
              level={currentLevel}
              engine={engineTitle || engine}
            />

            {mode === 'god' ? <GodDiagnostics result={result} /> : null}

            <GodSource engine={engine} level={levelId} enabled={mode === 'god'} />
          </main>
        </div>

        <footer className="app-footer">
          <span className="footer-brand">
            <ZapIcon size={14} /> SSTI Lab Console
          </span>
          <span className="footer-meta">
            {info.id ? `${info.id}` : 'lab'}
            {info.flag_path ? ` · flag: ${info.flag_path}` : ''}
            {' · 运行时通过 /api/lab-info 自描述'}
          </span>
        </footer>
      </div>

      <HintDrawer
        open={hintOpen}
        onClose={closeHint}
        level={currentLevel}
        labHint={labHint}
        labTitle={info.title || info.id || ''}
      />
    </div>
  );
}
