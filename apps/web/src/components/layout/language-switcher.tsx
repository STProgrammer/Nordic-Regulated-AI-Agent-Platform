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
    <div
      aria-label={t('label')}
      className="flex items-center gap-1 rounded-lg border border-slate-300 bg-slate-50 p-1"
      role="group"
    >
      {supportedLocales.map((supportedLocale) => (
        <button
          aria-pressed={locale === supportedLocale}
          className="min-h-9 rounded-md px-3 py-1 text-sm font-semibold text-slate-800 transition hover:bg-slate-200 aria-pressed:bg-[#123c5a] aria-pressed:text-white"
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
