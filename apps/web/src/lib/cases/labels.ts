import type {
  CaseDomain,
  CaseLanguage,
  CasePriority,
  CaseRiskLevel,
  CaseStatus,
} from '@/lib/api/contracts';

export const statusMessageKey: Record<CaseStatus, `statusLabels.${CaseStatus}`> = {
  approved: 'statusLabels.approved',
  archived: 'statusLabels.archived',
  completed: 'statusLabels.completed',
  failed: 'statusLabels.failed',
  needs_more_evidence: 'statusLabels.needs_more_evidence',
  new: 'statusLabels.new',
  processing: 'statusLabels.processing',
  rejected: 'statusLabels.rejected',
  waiting_for_human_review: 'statusLabels.waiting_for_human_review',
};
export const priorityMessageKey: Record<CasePriority, `priorityLabels.${CasePriority}`> = {
  high: 'priorityLabels.high',
  low: 'priorityLabels.low',
  normal: 'priorityLabels.normal',
  urgent: 'priorityLabels.urgent',
};
export const riskMessageKey: Record<CaseRiskLevel, `riskLabels.${CaseRiskLevel}`> = {
  critical: 'riskLabels.critical',
  high: 'riskLabels.high',
  low: 'riskLabels.low',
  medium: 'riskLabels.medium',
};
export const domainMessageKey: Record<CaseDomain, `domainLabels.${CaseDomain}`> = {
  banking_compliance: 'domainLabels.banking_compliance',
  energy_operations: 'domainLabels.energy_operations',
  internal_policy: 'domainLabels.internal_policy',
  public_sector: 'domainLabels.public_sector',
};
export const languageMessageKey: Record<CaseLanguage, `languageLabels.${CaseLanguage}`> = {
  en: 'languageLabels.en',
  nb: 'languageLabels.nb',
};
