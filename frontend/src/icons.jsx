/**
 * 零依赖内联 SVG 图标集。
 *
 * 刻意不使用图标库 / CDN / 远程字体：产物必须完全离线可用，
 * 且要被塞进每个靶场容器，体积越小越好。
 * 所有图标都继承 currentColor，尺寸由 CSS 控制。
 */

const base = {
  xmlns: 'http://www.w3.org/2000/svg',
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': 'true',
  focusable: 'false',
};

function Svg({ children, className, size = 16, ...rest }) {
  return (
    <svg {...base} width={size} height={size} className={className} {...rest}>
      {children}
    </svg>
  );
}

export function TerminalIcon(props) {
  return (
    <Svg {...props}>
      <rect x="2.5" y="4" width="19" height="16" rx="2.5" />
      <path d="M6.5 9.5l2.6 2.5-2.6 2.5" />
      <path d="M12.5 15h5" />
    </Svg>
  );
}

export function CodeIcon(props) {
  return (
    <Svg {...props}>
      <path d="M9 7l-5 5 5 5" />
      <path d="M15 7l5 5-5 5" />
    </Svg>
  );
}

export function ShieldIcon(props) {
  return (
    <Svg {...props}>
      <path d="M12 3l7 3v5.5c0 4.2-2.9 7.9-7 9.5-4.1-1.6-7-5.3-7-9.5V6z" />
      <path d="M9.2 12.2l2 2 3.6-3.8" />
    </Svg>
  );
}

export function ZapIcon(props) {
  return (
    <Svg {...props}>
      <path d="M13.5 2.5L4.8 13.2h5.6l-.9 8.3 8.7-10.7h-5.6z" />
    </Svg>
  );
}

export function TargetIcon(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="1" />
    </Svg>
  );
}

export function AlertTriangleIcon(props) {
  return (
    <Svg {...props}>
      <path d="M12 3.8l9 15.4H3z" />
      <path d="M12 9.5v4.2" />
      <path d="M12 16.6h.01" />
    </Svg>
  );
}

export function CheckCircleIcon(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M8.2 12.3l2.6 2.6 5-5.4" />
    </Svg>
  );
}

export function XCircleIcon(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M9.2 9.2l5.6 5.6" />
      <path d="M14.8 9.2l-5.6 5.6" />
    </Svg>
  );
}

export function FlagIcon(props) {
  return (
    <Svg {...props}>
      <path d="M6 21V4" />
      <path d="M6 4.8h11.5l-2.2 4 2.2 4H6z" />
    </Svg>
  );
}

export function EyeOffIcon(props) {
  return (
    <Svg {...props}>
      <path d="M3 3l18 18" />
      <path d="M10.6 6.3A8.6 8.6 0 0112 6.2c4.4 0 8 3.6 9 5.8-.5 1.2-1.6 2.8-3.2 4" />
      <path d="M6.3 8.1C4.7 9.3 3.6 11 3 12c1 2.2 4.6 5.8 9 5.8 1 0 2-.2 2.8-.5" />
      <path d="M9.9 10.2a3 3 0 004 4" />
    </Svg>
  );
}

export function BanIcon(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="8.8" />
      <path d="M5.9 5.9l12.2 12.2" />
    </Svg>
  );
}

export function LayersIcon(props) {
  return (
    <Svg {...props}>
      <path d="M12 3l8.5 4.6L12 12.2 3.5 7.6z" />
      <path d="M3.5 12.4L12 17l8.5-4.6" />
      <path d="M3.5 16.9L12 21.5l8.5-4.6" />
    </Svg>
  );
}

export function RefreshIcon(props) {
  return (
    <Svg {...props}>
      <path d="M20 11.5A8 8 0 006.4 6.6L4 9" />
      <path d="M4 4.5V9h4.5" />
      <path d="M4 12.5A8 8 0 0017.6 17.4L20 15" />
      <path d="M20 19.5V15h-4.5" />
    </Svg>
  );
}

export function PlayIcon(props) {
  return (
    <Svg {...props}>
      <path d="M7.5 4.8l11 7.2-11 7.2z" />
    </Svg>
  );
}

export function BulbIcon(props) {
  return (
    <Svg {...props}>
      <path d="M9.2 17.5h5.6" />
      <path d="M10 20.6h4" />
      <path d="M12 3.4a5.6 5.6 0 00-3.3 10.1c.5.4.8 1 .8 1.6h5c0-.6.3-1.2.8-1.6A5.6 5.6 0 0012 3.4z" />
    </Svg>
  );
}

export function ChevronIcon({ open, ...props }) {
  return (
    <Svg {...props} className={open ? 'chev open' : 'chev'}>
      <path d="M8.5 5.5l6.5 6.5-6.5 6.5" />
    </Svg>
  );
}

export function BugIcon(props) {
  return (
    <Svg {...props}>
      <path d="M8.5 8.2V6.8a3.5 3.5 0 017 0v1.4" />
      <rect x="7" y="8.2" width="10" height="10.3" rx="5" />
      <path d="M3.6 11.4h3.4M17 11.4h3.4M3.6 16.4h3.4M17 16.4h3.4" />
      <path d="M6.4 6.6L4.2 4.6M17.6 6.6l2.2-2" />
    </Svg>
  );
}

export function WifiOffIcon(props) {
  return (
    <Svg {...props}>
      <path d="M3 3l18 18" />
      <path d="M8.6 15.6a4.8 4.8 0 016.8 0" />
      <path d="M5.2 12.2a9.7 9.7 0 013.1-1.7" />
      <path d="M15.6 10.5a9.7 9.7 0 013.2 1.7" />
      <path d="M2 8.8a14.6 14.6 0 014.2-2.4" />
      <path d="M17.9 6.4A14.6 14.6 0 0122 8.8" />
      <path d="M12 19.5h.01" />
    </Svg>
  );
}

export function DiffIcon(props) {
  return (
    <Svg {...props}>
      <circle cx="6.5" cy="6.5" r="2.6" />
      <circle cx="17.5" cy="17.5" r="2.6" />
      <path d="M6.5 9.1v8.4h8.4" />
      <path d="M17.5 14.9V6.5h-8.4" />
    </Svg>
  );
}

export function BookIcon(props) {
  return (
    <Svg {...props}>
      <path d="M4 5.2A1.7 1.7 0 015.7 3.5H19v17H5.7A1.7 1.7 0 014 18.8z" />
      <path d="M8 3.5v17" />
    </Svg>
  );
}
