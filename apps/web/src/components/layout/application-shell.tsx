'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { usePathname, useRouter } from 'next/navigation';
import type { PropsWithChildren } from 'react';

import { LanguageSwitcher } from '@/components/layout/language-switcher';
import { Button } from '@/components/ui/button';
import type { AppLocale } from '@/i18n/routing';
import { authApi } from '@/lib/api/auth';
import type { CurrentUser } from '@/lib/api/contracts';
import { authQueryKey } from '@/lib/auth/query';
import { loginPath } from '@/lib/auth/paths';

type NavigationItem = {
  href: '/cases' | '/approvals' | '/evaluations' | '/admin' | '/audit';
  key: 'cases' | 'approvals' | 'evaluations' | 'admin' | 'audit';
};

const navigationItems: readonly NavigationItem[] = [
  { href: '/cases', key: 'cases' },
  { href: '/approvals', key: 'approvals' },
  { href: '/evaluations', key: 'evaluations' },
  { href: '/admin', key: 'admin' },
  { href: '/audit', key: 'audit' },
];

type AccountTranslation = ReturnType<typeof useTranslations<'account'>>;
type AccountRoleKey =
  | 'role.admin'
  | 'role.caseWorker'
  | 'role.complianceReviewer'
  | 'role.manager'
  | 'role.readOnlyAuditor';

function roleLabel(role: CurrentUser['roles'][number], translate: AccountTranslation) {
  const keys: Record<CurrentUser['roles'][number], AccountRoleKey> = {
    Admin: 'role.admin',
    'Case Worker': 'role.caseWorker',
    'Compliance Reviewer': 'role.complianceReviewer',
    Manager: 'role.manager',
    'Read-only Auditor': 'role.readOnlyAuditor',
  };

  return translate(keys[role]);
}

function LogoutButton() {
  const locale = useLocale() as AppLocale;
  const queryClient = useQueryClient();
  const router = useRouter();
  const t = useTranslations('account');
  const mutation = useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      queryClient.removeQueries({ queryKey: authQueryKey });
      router.replace(loginPath(locale));
    },
  });

  return (
    <Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
      {mutation.isPending ? t('logoutPending') : t('logout')}
    </Button>
  );
}

export function ApplicationShell({ children, user }: PropsWithChildren<{ user: CurrentUser }>) {
  const locale = useLocale() as AppLocale;
  const pathname = usePathname();
  const tAccount = useTranslations('account');
  const tApp = useTranslations('app');
  const tCommon = useTranslations('common');
  const tNavigation = useTranslations('navigation');

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <a
        className="sr-only fixed left-4 top-4 z-50 rounded bg-white px-4 py-2 font-medium shadow focus:not-sr-only focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
        href="#main-content"
      >
        {tNavigation('skipToContent')}
      </a>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <div>
            <p className="text-lg font-semibold tracking-tight">{tApp('name')}</p>
            <p className="text-sm text-slate-600">{tAccount('label')}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <LanguageSwitcher />
            <div className="border-l border-slate-200 pl-3 text-right text-sm">
              <p className="font-medium">{user.display_name}</p>
              <p className="text-slate-600">
                {user.roles.map((role) => roleLabel(role, tAccount)).join(', ')}
              </p>
            </div>
            <LogoutButton />
          </div>
        </div>
      </header>
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:flex-row">
        <nav aria-label={tNavigation('label')} className="lg:w-56">
          <ul className="flex flex-wrap gap-2 lg:flex-col">
            {navigationItems.map((item) => {
              const href = `/${locale}${item.href}`;
              const active =
                pathname === href || (item.href === '/cases' && pathname.startsWith(`${href}/`));
              return (
                <li key={item.href}>
                  <Link
                    aria-current={active ? 'page' : undefined}
                    className={`inline-flex rounded-md border px-3 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700 ${
                      active
                        ? 'border-slate-900 bg-slate-900 text-white'
                        : 'border-slate-300 bg-white text-slate-800 hover:border-slate-500'
                    }`}
                    href={href}
                  >
                    {tNavigation(item.key)}
                    {active ? <span className="sr-only"> {tCommon('current')}</span> : null}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <main className="min-w-0 flex-1" id="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
