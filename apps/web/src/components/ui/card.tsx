import type { HTMLAttributes, PropsWithChildren } from 'react';

type CardProps = PropsWithChildren<HTMLAttributes<HTMLElement>>;

export function Card({ children, className = '', ...props }: CardProps) {
  return (
    <section className={`nordic-surface nordic-card ${className}`} {...props}>
      {children}
    </section>
  );
}
