import { useTranslations } from 'next-intl';

import type { CasePriority, CaseRiskLevel, CaseStatus } from '@/lib/api/contracts';
import { priorityMessageKey, riskMessageKey, statusMessageKey } from '@/lib/cases/labels';

const badgeClass =
  'inline-flex rounded-full border border-slate-300 bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-800';

export function StatusBadge({ value }: { value: CaseStatus }) {
  const t = useTranslations('cases');
  return <span className={badgeClass}>{t(statusMessageKey[value])}</span>;
}

export function PriorityBadge({ value }: { value: CasePriority }) {
  const t = useTranslations('cases');
  return <span className={badgeClass}>{t(priorityMessageKey[value])}</span>;
}

export function RiskBadge({ value }: { value: CaseRiskLevel | null }) {
  const t = useTranslations('cases');
  return <span className={badgeClass}>{value ? t(riskMessageKey[value]) : t('notAssessed')}</span>;
}
