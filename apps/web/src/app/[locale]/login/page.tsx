import { getTranslations } from 'next-intl/server';

import { LoginForm } from '@/components/auth/login-form';
import { LanguageSwitcher } from '@/components/layout/language-switcher';
import { Card } from '@/components/ui/card';
import type { AppLocale } from '@/i18n/routing';

type LoginPageProps = {
  params: Promise<{ locale: string }>;
};

export async function generateMetadata({ params }: LoginPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale: locale as AppLocale, namespace: 'login' });
  return { title: t('title') };
}

export default async function LoginPage() {
  const t = await getTranslations('login');
  const app = await getTranslations('app');

  return (
    <main className="mx-auto flex min-h-screen max-w-xl items-center px-4 py-10">
      <Card>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-slate-600">{app('name')}</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">{t('title')}</h1>
          </div>
          <LanguageSwitcher />
        </div>
        <p className="mt-3 text-slate-700">{t('description')}</p>
        <div className="mt-6">
          <LoginForm />
        </div>
      </Card>
    </main>
  );
}
