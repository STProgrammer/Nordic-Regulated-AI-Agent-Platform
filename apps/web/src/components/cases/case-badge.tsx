import { useTranslations } from 'next-intl';
import type { ReactNode } from 'react';

import type { CasePriority, CaseRiskLevel, CaseStatus } from '@/lib/api/contracts';
import { priorityMessageKey, riskMessageKey, statusMessageKey } from '@/lib/cases/labels';

type StatusTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';

const statusTones: Record<CaseStatus, StatusTone> = {
  new: 'neutral',
  processing: 'info',
  waiting_for_human_review: 'warning',
  needs_more_evidence: 'warning',
  approved: 'success',
  rejected: 'danger',
  completed: 'success',
  failed: 'danger',
  archived: 'neutral',
};

const priorityTones: Record<CasePriority, StatusTone> = {
  low: 'neutral',
  normal: 'info',
  high: 'warning',
  urgent: 'danger',
};

const riskTones: Record<NonNullable<CaseRiskLevel>, StatusTone> = {
  low: 'success',
  medium: 'warning',
  high: 'danger',
  critical: 'danger',
};

function Badge({ children, tone }: { children: ReactNode; tone: StatusTone }) {
  return (
    <span className={`nordic-status nordic-status-${tone}`}>
      <span aria-hidden="true">●</span>
      {children}
    </span>
  );
}

export function StatusBadge({ value }: { value: CaseStatus }) {
  const t = useTranslations('cases');
  return <Badge tone={statusTones[value]}>{t(statusMessageKey[value])}</Badge>;
}

export function PriorityBadge({ value }: { value: CasePriority }) {
  const t = useTranslations('cases');
  return <Badge tone={priorityTones[value]}>{t(priorityMessageKey[value])}</Badge>;
}

export function RiskBadge({ value }: { value: CaseRiskLevel | null }) {
  const t = useTranslations('cases');
  return (
    <Badge tone={value ? riskTones[value] : 'neutral'}>
      {value ? t(riskMessageKey[value]) : t('notAssessed')}
    </Badge>
  );
}
