import { useEffect, useRef, type FormEvent, type ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { Button, IconButton } from './Button';
import s from './Modal.module.css';

export interface ModalProps {
  open: boolean;
  title: ReactNode;
  onClose: () => void;
  /** When provided the body is a form; Enter submits and the primary button is type=submit. */
  onSubmit?: () => void | Promise<void>;
  submitLabel?: string;
  submitDisabled?: boolean;
  busy?: boolean;
  error?: string | null;
  wide?: boolean;
  children: ReactNode;
}

/**
 * Native <dialog>-based modal. Kept deliberately small: one title, a scrolling
 * body and a footer with cancel/submit. Escape and backdrop click close it.
 */
export function Modal({ open, title, onClose, onSubmit, submitLabel = 'Create', submitDisabled, busy, error, wide, children }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!busy && !submitDisabled) void onSubmit?.();
  };

  return (
    <dialog
      ref={ref}
      className={cn(s.dialog, wide && s.wide)}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current && !busy) onClose();
      }}
    >
      <form className={s.form} onSubmit={submit} method="dialog">
        <header className={s.header}>
          <span className={s.title}>{title}</span>
          <IconButton icon="close" label="Close" size="sm" variant="ghost" type="button" onClick={onClose} disabled={busy} />
        </header>
        <div className={s.body}>{children}</div>
        <footer className={s.footer}>
          {error && (
            <span className={s.error} title={error}>
              {error}
            </span>
          )}
          <Button type="button" variant="ghost" size="sm" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          {onSubmit && (
            <Button type="submit" variant="primary" size="sm" disabled={busy || submitDisabled}>
              {busy ? 'Working…' : submitLabel}
            </Button>
          )}
        </footer>
      </form>
    </dialog>
  );
}
