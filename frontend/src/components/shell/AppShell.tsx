import { Suspense, useEffect, type ReactNode } from 'react';
import { Outlet, useNavigate } from 'react-router';
import { cn } from '@/lib/cn';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { sections } from '@/app/sections';
import { useUiStore } from '@/store/uiStore';
import { useChromeStore } from '@/store/chromeStore';
import { LoadingState } from '@/components/ui/EmptyState';
import { NavRail } from './NavRail';
import { InstrumentBar } from './InstrumentBar';
import { StatusBar } from './StatusBar';
import s from './AppShell.module.css';

function isEditable(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
}

export function AppShell() {
  const narrow = useMediaQuery('(max-width: 900px)');
  const railCollapsed = useUiStore((st) => st.railCollapsed);
  const detail = useChromeStore((c) => c.detail);
  const inspectorAvailable = useChromeStore((c) => c.inspectorAvailable);
  const navigate = useNavigate();

  // Digit shortcuts 1–8 switch sections when focus is not in a form control.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isEditable(e.target)) return;
      const sec = sections.find((x) => x.key === e.key);
      if (sec) {
        e.preventDefault();
        navigate(sec.path);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navigate]);

  return (
    <div className={cn(s.shell, (railCollapsed || narrow) && s.railCollapsed)}>
      <div className={s.rail}>
        <NavRail forceCollapsed={narrow} />
      </div>
      <div className={s.bar}>
        <InstrumentBar detail={detail ?? undefined} showInspectorToggle={inspectorAvailable} />
      </div>
      <main className={s.main}>
        <Suspense fallback={<LoadingState lines={4} />}>
          <Outlet />
        </Suspense>
      </main>
      <div className={s.status}>
        <StatusBar />
      </div>
    </div>
  );
}

/** Standard scrolling page surface with a title row. */
export function Page({ title, lede, actions, children, flush, className }: { title?: ReactNode; lede?: ReactNode; actions?: ReactNode; children: ReactNode; flush?: boolean; className?: string }) {
  if (flush) return <div className={cn(s.page, s.pageFlush, className)}>{children}</div>;
  return (
    <div className={cn(s.page, className)}>
      <div className={s.pageInner}>
        {(title || actions) && (
          <div className={s.pageHeader}>
            <div>
              {title && <h2 className={s.pageTitle}>{title}</h2>}
              {lede && <p className={s.pageLede}>{lede}</p>}
            </div>
            {actions && <div className={s.pageActions}>{actions}</div>}
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
