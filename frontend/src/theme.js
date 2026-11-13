/**
 * 主题注入：把 lab-info.theme ({name, accent, accent2, glow}) 映射到
 * 文档根节点的 CSS 自定义属性上。字段缺失时回落到 cyber 默认配色。
 */

export const DEFAULT_THEME = {
  name: 'cyber',
  accent: '#00e5ff',
  accent2: '#ff2bd6',
  glow: 'rgba(0, 229, 255, 0.55)',
};

const HEX_RE = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
const RGBA_RE = /^rgba?\([\d\s.,%/]+\)$/i;

function isValidColor(value) {
  if (typeof value !== 'string') return false;
  const v = value.trim();
  if (!v) return false;
  if (HEX_RE.test(v) || RGBA_RE.test(v)) return true;
  // 允许 hsla()/颜色关键字之类的安全 CSS 颜色写法，但不接受分号/花括号等可注入内容。
  return /^(?:hsla?\([\d\s.,%/]+\)|[a-z]{3,24})$/i.test(v);
}

function cleanColor(value, fallback) {
  return isValidColor(value) ? String(value).trim() : fallback;
}

export function hexToRgba(hex, alpha) {
  const m = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.exec(String(hex || '').trim());
  if (!m) return null;
  let body = m[1];
  if (body.length === 3) {
    body = body
      .split('')
      .map((c) => c + c)
      .join('');
  }
  const r = parseInt(body.slice(0, 2), 16);
  const g = parseInt(body.slice(2, 4), 16);
  const b = parseInt(body.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** 用一个颜色 + alpha 生成柔光色；非 hex 颜色时回落到默认 glow。 */
function softColor(color, alpha, fallback) {
  const rgba = hexToRgba(color, alpha);
  if (rgba) return rgba;
  if (isValidColor(color)) return color;
  return fallback;
}

/**
 * @param {{name?:string,accent?:string,accent2?:string,glow?:string}|null|undefined} theme
 * @returns {{name:string,accent:string,accent2:string,glow:string}} 实际生效的主题
 */
export function applyTheme(theme) {
  const source = theme && typeof theme === 'object' ? theme : {};
  const accent = cleanColor(source.accent, DEFAULT_THEME.accent);
  const accent2 = cleanColor(source.accent2, DEFAULT_THEME.accent2);
  const glow = cleanColor(source.glow, DEFAULT_THEME.glow);
  const effective = {
    name: typeof source.name === 'string' && source.name.trim() ? source.name.trim() : DEFAULT_THEME.name,
    accent,
    accent2,
    glow,
  };

  const root = document.documentElement;
  root.style.setProperty('--accent', effective.accent);
  root.style.setProperty('--accent2', effective.accent2);
  root.style.setProperty('--glow', effective.glow);
  // 派生变量：让 CSS 里不必写死 rgba。
  root.style.setProperty('--accent-soft', softColor(accent, 0.18, 'rgba(0, 229, 255, 0.18)'));
  root.style.setProperty('--accent-line', softColor(accent, 0.45, 'rgba(0, 229, 255, 0.45)'));
  root.style.setProperty('--accent2-soft', softColor(accent2, 0.18, 'rgba(255, 43, 214, 0.18)'));
  root.style.setProperty('--glow-strong', softColor(accent, 0.85, 'rgba(0, 229, 255, 0.85)'));
  root.setAttribute('data-lab-theme', effective.name);

  return effective;
}

/** 页面标题也来自 lab-info，避免各靶场页面标题一模一样。 */
export function applyDocumentTitle(info) {
  const id = info && typeof info.id === 'string' ? info.id : '';
  const title = info && typeof info.title === 'string' ? info.title : '';
  document.title = title ? `${title}${id ? ` · ${id}` : ''}` : 'SSTI Lab Console';
}
