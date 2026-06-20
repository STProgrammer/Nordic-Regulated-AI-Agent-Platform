import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';

type ButtonProps = PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>>;

export function Button({ children, className = '', type = 'button', ...props }: ButtonProps) {
  return (
    <button
      className={`inline-flex min-h-10 items-center justify-center rounded-md bg-slate-900 px-4 py-2 font-medium text-white transition hover:bg-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700 disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
      type={type}
      {...props}
    >
      {children}
    </button>
  );
}
