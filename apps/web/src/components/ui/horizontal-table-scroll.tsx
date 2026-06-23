'use client';

import { useEffect, useId, useRef, useState, type ReactNode } from 'react';

type HorizontalTableScrollProps = {
  ariaLabel: string;
  children: ReactNode;
  className?: string;
  scrollHint: string;
};

export function HorizontalTableScroll({
  ariaLabel,
  children,
  className,
  scrollHint,
}: HorizontalTableScrollProps) {
  const hintId = useId();
  const topScrollRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [tableWidth, setTableWidth] = useState(0);

  useEffect(() => {
    const topScroll = topScrollRef.current;
    const viewport = viewportRef.current;
    const table = viewport?.querySelector('table');
    if (!topScroll || !viewport || !table) return;

    let synchronizing = false;
    const updateWidth = () => setTableWidth(table.scrollWidth);
    const syncFromTop = () => {
      if (synchronizing) return;
      synchronizing = true;
      viewport.scrollLeft = topScroll.scrollLeft;
      synchronizing = false;
    };
    const syncFromViewport = () => {
      if (synchronizing) return;
      synchronizing = true;
      topScroll.scrollLeft = viewport.scrollLeft;
      synchronizing = false;
    };

    updateWidth();
    topScroll.addEventListener('scroll', syncFromTop);
    viewport.addEventListener('scroll', syncFromViewport);
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(updateWidth);
    observer?.observe(table);

    return () => {
      topScroll.removeEventListener('scroll', syncFromTop);
      viewport.removeEventListener('scroll', syncFromViewport);
      observer?.disconnect();
    };
  }, [children]);

  return (
    <div className={className}>
      <p className="sr-only" id={hintId}>
        {scrollHint}
      </p>
      <div
        aria-label={scrollHint}
        className="nordic-table-scrollbar-top"
        ref={topScrollRef}
        role="region"
        tabIndex={0}
      >
        <div style={{ width: tableWidth }} />
      </div>
      <div
        aria-describedby={hintId}
        aria-label={ariaLabel}
        className="nordic-table-scroll-window"
        ref={viewportRef}
        role="region"
        tabIndex={0}
      >
        {children}
      </div>
    </div>
  );
}
