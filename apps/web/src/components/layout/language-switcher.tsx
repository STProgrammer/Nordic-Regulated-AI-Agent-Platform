'use client';

import { useLocale, useTranslations } from 'next-intl';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import type { AppLocale } from '@/i18n/routing';
import { authApi } from '@/lib/api/auth';
import { authQueryKey } from '@/lib/auth/query';

const supportedLocales: readonly AppLocale[] = ['nb', 'en'];

export function LanguageSwitcher() {
  const locale = useLocale() as AppLocale;
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const t = useTranslations('language');
  const preference = useMutation({
    mutationFn: authApi.updatePreferredLanguage,
    onSuccess: (user) => {
      queryClient.setQueryData(authQueryKey, user);
    },
  });

  function switchLocale(nextLocale: AppLocale) {
    if (nextLocale === locale) {
      return;
    }

    void preference
      .mutateAsync(nextLocale)
      .catch(() => undefined)
      .finally(() => {
        const localizedPath = pathname.replace(/^\/(nb|en)(?=\/|$)/, `/${nextLocale}`);
        const query = searchParams.toString();
        router.replace(query ? `${localizedPath}?${query}` : localizedPath);
      });
  }

  return (
    <div aria-label={t('label')} className="flex items-center gap-1" role="group">
      {supportedLocales.map((supportedLocale) => (
        <button
          aria-pressed={locale === supportedLocale}
          className="rounded px-2 py-1 text-sm font-medium text-slate-700 underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700 aria-pressed:bg-slate-900 aria-pressed:text-white"
          key={supportedLocale}
          lang={supportedLocale}
          disabled={preference.isPending}
          onClick={() => switchLocale(supportedLocale)}
          type="button"
        >
          {t(supportedLocale)}
        </button>
      ))}
    </div>
  );
}
