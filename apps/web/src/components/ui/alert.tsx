import type { PropsWithChildren } from 'react';

export function Alert({ children }: PropsWithChildren) {
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 p-4 text-slate-900" role="alert">
      {children}
    </div>
  );
}
