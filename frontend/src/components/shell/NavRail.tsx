import { NavLink } from 'react-router';
import { cn } from '@/lib/cn';
import { sections } from '@/app/sections';
import { useUiStore } from '@/store/uiStore';
import { Icon } from '@/components/ui/Icon';
import { Kbd } from '@/components/ui/Forms';
import { Button } from '@/components/ui/Button';
import s from './NavRail.module.css';

function BrandMark() {
  return (
    <svg className={s.mark} viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1" aria-hidden="true">
      <rect x="1.5" y="1.5" width="19" height="19" rx="1.5" />
      <rect x="5.5" y="5.5" width="11" height="11" rx="1" />
      <rect x="9.5" y="9.5" width="3" height="3" rx="0.5" fill="var(--acc-live)" stroke="none" />
    </svg>
  );
}

export function NavRail({ forceCollapsed }: { forceCollapsed: boolean }) {
  const collapsedPref = useUiStore((st) => st.railCollapsed);
  const toggleRail = useUiStore((st) => st.toggleRail);
  const collapsed = forceCollapsed || collapsedPref;

  const primary = sections.filter((x) => x.id !== 'settings');
  const settings = sections.find((x) => x.id === 'settings')!;

  const renderLink = (sec: (typeof sections)[number]) => (
    <NavLink
      key={sec.id}
      to={sec.path}
      end={sec.path === '/'}
      className={({ isActive }) => cn(s.link, isActive && s.active)}
      title={collapsed ? `${sec.label} (${sec.key})` : sec.description}
      aria-label={sec.label}
    >
      <Icon name={sec.icon} size={15} className={s.linkIcon} />
      <span className={s.linkLabel}>{sec.label}</span>
      <span className={s.linkKey}>
        <Kbd>{sec.key}</Kbd>
      </span>
    </NavLink>
  );

  return (
    <aside className={cn(s.rail, collapsed && s.collapsed)} aria-label="Primary">
      <div className={s.brand}>
        <BrandMark />
        <div className={s.brandText}>
          <span className={s.brandName}>RECURSION</span>
          <span className={s.brandSub}>Artificial life observatory</span>
        </div>
      </div>
      <nav className={s.nav} aria-label="Sections">
        {primary.map(renderLink)}
        <div className={s.divider} />
        {renderLink(settings)}
      </nav>
      {!forceCollapsed && (
        <div className={s.footer}>
          <Button variant="ghost" size="sm" className={s.collapseBtn} icon={collapsed ? 'chevronRight' : 'chevronLeft'} onClick={toggleRail} aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}>
            {!collapsed && 'Collapse'}
          </Button>
        </div>
      )}
    </aside>
  );
}
