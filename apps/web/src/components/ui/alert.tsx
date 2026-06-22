import type { HTMLAttributes, PropsWithChildren } from 'react';

export type AlertTone = 'info' | 'success' | 'warning' | 'error';

type AlertProps = PropsWithChildren<
  HTMLAttributes<HTMLDivElement> & {
    tone?: AlertTone;
  }
>;

export function Alert({ children, className = '', role, tone = 'info', ...props }: AlertProps) {
  return (
    <div
      className={`nordic-notice nordic-notice-${tone} ${className}`}
      role={role ?? (tone === 'error' ? 'alert' : undefined)}
      {...props}
    >
      {children}
    </div>
  );
}
