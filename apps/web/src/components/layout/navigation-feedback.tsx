'use client';

import { useTranslations } from 'next-intl';
import { usePathname, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';

function isInternalNavigation(event: MouseEvent) {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey ||
    !(event.target instanceof Element)
  ) {
    return false;
  }

  const link = event.target.closest<HTMLAnchorElement>('a[href]');
  if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) {
    return false;
  }

  const nextUrl = new URL(link.href, window.location.href);
  const currentUrl = new URL(window.location.href);
  return (
    nextUrl.origin === currentUrl.origin &&
    (nextUrl.pathname !== currentUrl.pathname || nextUrl.search !== currentUrl.search)
  );
}

export function NavigationFeedback() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const t = useTranslations('common');
  const [isNavigating, setIsNavigating] = useState(false);
  const routeKey = `${pathname}?${searchParams.toString()}`;

  useEffect(() => {
    setIsNavigating(false);
  }, [routeKey]);

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (isInternalNavigation(event)) setIsNavigating(true);
    };

    // Next.js prevents the browser default for <Link> after this capture handler. Starting here
    // keeps the feedback global for every internal link without requiring each page to opt in.
    document.addEventListener('click', handleClick, true);
    return () => document.removeEventListener('click', handleClick, true);
  }, []);

  if (!isNavigating) return null;

  return (
    <div aria-live="polite" className="nordic-navigation-feedback" role="status">
      <div aria-hidden="true" className="nordic-navigation-progress" />
      <span className="sr-only">{t('navigationLoading')}</span>
    </div>
  );
}
