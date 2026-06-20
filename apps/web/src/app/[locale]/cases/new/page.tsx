import { CaseForm } from '@/components/cases/case-form';
import { ProtectedPage } from '@/components/auth/protected-page';
import { getTranslations } from 'next-intl/server';

export async function generateMetadata() {
  const t = await getTranslations('cases');
  return { title: t('newCaseTitle') };
}
export default async function NewCasePage() {
  const t = await getTranslations('cases');
  return (
    <ProtectedPage>
      <section aria-labelledby="new-case-title" className="mx-auto max-w-3xl">
        <h1 className="text-3xl font-semibold tracking-tight" id="new-case-title">
          {t('newCaseTitle')}
        </h1>
        <p className="mt-2 text-slate-700">{t('newCaseDescription')}</p>
        <div className="mt-6">
          <CaseForm />
        </div>
      </section>
    </ProtectedPage>
  );
}
