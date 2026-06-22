'use client';

import { useEffect, useId, useRef } from 'react';
import type { PropsWithChildren } from 'react';

type DialogKind = 'dialog' | 'alertdialog';

type DialogProps = PropsWithChildren<{
  description?: string;
  kind?: DialogKind;
  onClose: () => void;
  title: string;
  trigger?: HTMLElement | null;
  testId?: string;
}>;

const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function focusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(focusableSelector)).filter(
    (element) => !element.hasAttribute('hidden'),
  );
}

/** A small dependency-free modal with keyboard containment and deterministic focus restoration. */
export function Dialog({
  children,
  description,
  kind = 'dialog',
  onClose,
  testId,
  title,
  trigger,
}: DialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    returnFocusRef.current = trigger ?? (document.activeElement as HTMLElement | null);
    const dialog = dialogRef.current;
    const initialFocus = dialog ? focusableElements(dialog)[0] : null;
    initialFocus?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !dialog) return;

      const focusable = focusableElements(dialog);
      if (!focusable.length) {
        event.preventDefault();
        dialog.focus();
        return;
      }

      const first = focusable[0]!;
      const last = focusable.at(-1)!;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      returnFocusRef.current?.focus();
    };
  }, [onClose, trigger]);

  return (
    <div className="nordic-dialog-backdrop fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        aria-describedby={description ? descriptionId : undefined}
        aria-labelledby={titleId}
        aria-modal="true"
        className="nordic-dialog-panel max-h-[85vh] w-full max-w-2xl overflow-y-auto p-6"
        data-testid={testId}
        ref={dialogRef}
        role={kind}
        tabIndex={-1}
      >
        <h2 className="text-xl font-bold tracking-tight" id={titleId}>
          {title}
        </h2>
        {description ? (
          <p className="mt-2 text-slate-700" id={descriptionId}>
            {description}
          </p>
        ) : null}
        {children}
      </div>
    </div>
  );
}
