import type { SVGProps } from 'react';

/**
 * In-repo 16px stroke icon set. Kept deliberately small; every icon is a
 * single path group drawn on a 16×16 grid with 1.25px strokes.
 */
export type IconName =
  | 'overview'
  | 'universe'
  | 'agents'
  | 'civilization'
  | 'realities'
  | 'observatory'
  | 'experiments'
  | 'settings'
  | 'play'
  | 'pause'
  | 'step'
  | 'zoomIn'
  | 'zoomOut'
  | 'fit'
  | 'cursor'
  | 'hand'
  | 'chevronRight'
  | 'chevronDown'
  | 'chevronLeft'
  | 'panelRight'
  | 'close'
  | 'search'
  | 'plus'
  | 'minus'
  | 'arrowUpRight'
  | 'dot'
  | 'link'
  | 'menu'
  | 'info'
  | 'check'
  | 'warn';

const paths: Record<IconName, React.ReactNode> = {
  overview: (
    <>
      <rect x="2" y="2" width="5" height="5" rx="0.5" />
      <rect x="9" y="2" width="5" height="5" rx="0.5" />
      <rect x="2" y="9" width="5" height="5" rx="0.5" />
      <rect x="9" y="9" width="5" height="5" rx="0.5" />
    </>
  ),
  universe: (
    <>
      <circle cx="8" cy="8" r="6" />
      <path d="M2 8h12M8 2c2 2 2 10 0 12M8 2c-2 2-2 10 0 12" />
    </>
  ),
  agents: (
    <>
      <circle cx="6" cy="5.5" r="2.25" />
      <path d="M2 13.5c0-2.3 1.8-4 4-4s4 1.7 4 4" />
      <circle cx="11.5" cy="5" r="1.5" />
      <path d="M14 12.5c0-1.6-1-3-2.5-3" />
    </>
  ),
  civilization: (
    <>
      <path d="M2 14h12M3 14V7l5-3.5L13 7v7" />
      <path d="M6.5 14v-4h3v4" />
    </>
  ),
  realities: (
    <>
      <rect x="1.5" y="1.5" width="13" height="13" rx="0.5" />
      <rect x="4" y="4" width="8" height="8" rx="0.5" />
      <rect x="6.5" y="6.5" width="3" height="3" rx="0.5" />
    </>
  ),
  observatory: (
    <>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.3 10.3L14 14" />
      <path d="M5 7h4M7 5v4" />
    </>
  ),
  experiments: (
    <>
      <path d="M6 2v5L2.5 13a1 1 0 00.9 1.5h9.2a1 1 0 00.9-1.5L10 7V2" />
      <path d="M5 2h6M4.5 10h7" />
    </>
  ),
  settings: (
    <>
      <path d="M3 4h10M3 8h10M3 12h10" />
      <circle cx="6" cy="4" r="1.25" fill="currentColor" stroke="none" />
      <circle cx="10.5" cy="8" r="1.25" fill="currentColor" stroke="none" />
      <circle cx="7" cy="12" r="1.25" fill="currentColor" stroke="none" />
    </>
  ),
  play: <path d="M4.5 3v10l8-5z" fill="currentColor" stroke="none" />,
  pause: (
    <>
      <rect x="4" y="3" width="2.5" height="10" fill="currentColor" stroke="none" />
      <rect x="9.5" y="3" width="2.5" height="10" fill="currentColor" stroke="none" />
    </>
  ),
  step: (
    <>
      <path d="M3.5 3v10l7-5z" fill="currentColor" stroke="none" />
      <rect x="11.5" y="3" width="1.75" height="10" fill="currentColor" stroke="none" />
    </>
  ),
  zoomIn: (
    <>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.3 10.3L14 14M5 7h4M7 5v4" />
    </>
  ),
  zoomOut: (
    <>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.3 10.3L14 14M5 7h4" />
    </>
  ),
  fit: (
    <>
      <path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4" />
      <rect x="5.5" y="5.5" width="5" height="5" rx="0.5" />
    </>
  ),
  cursor: <path d="M3 2.5l9.5 5.5-4.2 1.3L7 13.5z" strokeLinejoin="round" />,
  hand: (
    <>
      <path d="M5 8V3.5a1 1 0 012 0V8M7 7.5V2.75a1 1 0 012 0V8M9 7.5V3.5a1 1 0 012 0V9" />
      <path d="M11 9v1.5a4 4 0 01-4 4H6.5a3 3 0 01-2.6-1.5L2.2 10a1 1 0 011.7-1l1.1 1.7" />
    </>
  ),
  chevronRight: <path d="M6 3.5L10.5 8 6 12.5" />,
  chevronDown: <path d="M3.5 6L8 10.5 12.5 6" />,
  chevronLeft: <path d="M10 3.5L5.5 8 10 12.5" />,
  panelRight: (
    <>
      <rect x="2" y="3" width="12" height="10" rx="1" />
      <path d="M10 3v10" />
    </>
  ),
  close: <path d="M4 4l8 8M12 4l-8 8" />,
  search: (
    <>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.3 10.3L14 14" />
    </>
  ),
  plus: <path d="M8 3v10M3 8h10" />,
  minus: <path d="M3 8h10" />,
  arrowUpRight: <path d="M4 12L12 4M6 4h6v6" />,
  dot: <circle cx="8" cy="8" r="2" fill="currentColor" stroke="none" />,
  link: (
    <>
      <path d="M6.5 9.5l3-3" />
      <path d="M7 4.5l1-1a2.5 2.5 0 013.5 3.5l-1 1M9 11.5l-1 1A2.5 2.5 0 014.5 9l1-1" />
    </>
  ),
  menu: <path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11" />,
  info: (
    <>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 7v4M8 5v.5" />
    </>
  ),
  check: <path d="M3.5 8.5l3 3 6-7" />,
  warn: (
    <>
      <path d="M8 2.5l6 10.5H2z" strokeLinejoin="round" />
      <path d="M8 6.5v3M8 11.5v.5" />
    </>
  ),
};

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'name'> {
  name: IconName;
  size?: number;
}

export function Icon({ name, size = 16, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {paths[name]}
    </svg>
  );
}
