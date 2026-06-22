'use client';

import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { CaseErrorPanel } from '@/components/cases/case-error-panel';
import { PriorityBadge, RiskBadge, StatusBadge } from '@/components/cases/case-badge';
import { ProtectedPage } from '@/components/auth/protected-page';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { AppLocale } from '@/i18n/routing';
import { formatCalendarDate, formatTimestamp } from '@/lib/formatting';
import { useCaseAssignees, useCaseList } from '@/lib/cases/query';
import {
  CASE_PAGE_SIZE,
  caseFiltersFromSearchParams,
  caseFiltersToSearchParams,
  hasCaseFilters,
  normalizeCaseFilters,
  type CaseFilters,
} from '@/lib/cases/filters';
import {
  domainMessageKey,
  priorityMessageKey,
  riskMessageKey,
  statusMessageKey,
} from '@/lib/cases/labels';
import {
  caseDomainSchema,
  casePrioritySchema,
  caseRiskLevelSchema,
  caseStatusSchema,
} from '@/lib/api/contracts';
import { useCurrentUser } from '@/lib/auth/query';

function routeWithFilters(locale: AppLocale, filters: CaseFilters): string {
  const query = caseFiltersToSearchParams(filters).toString();
  return `/${locale}/cases${query ? `?${query}` : ''}`;
}

function canSubmit(roles: readonly string[]): boolean {
  return roles.some((role) => ['Admin', 'Case Worker', 'Manager'].includes(role));
}

export function CaseInbox() {
  const locale = useLocale() as AppLocale;
  const router = useRouter();
  const searchParams = useSearchParams();
  const t = useTranslations('cases');
  const currentUser = useCurrentUser();
  const filters = caseFiltersFromSearchParams(new URLSearchParams(searchParams.toString()));
  const [draft, setDraft] = useState<CaseFilters>(filters);
  const list = useCaseList(filters);
  const assignees = useCaseAssignees();

  function updateDraft(key: keyof CaseFilters, value: string | number | undefined) {
    setDraft((current) => normalizeCaseFilters({ ...current, [key]: value, offset: 0 }));
  }

  function applyFilters() {
    router.replace(routeWithFilters(locale, { ...draft, offset: 0 }));
  }

  function clearFilters() {
    const next = {
      ...filters,
      limit: CASE_PAGE_SIZE,
      offset: 0,
      query: undefined,
      status: undefined,
      riskLevel: undefined,
      assignedUserId: undefined,
      domain: undefined,
      priority: undefined,
    };
    setDraft(next);
    router.replace(routeWithFilters(locale, next));
  }

  function goToPage(offset: number) {
    router.replace(routeWithFilters(locale, { ...filters, offset }));
  }

  const hasCreatePermission = currentUser.data ? canSubmit(currentUser.data.roles) : false;
  const visibleAssignees = assignees.data?.items ?? [];

  return (
    <ProtectedPage>
      <section aria-labelledby="case-inbox-title" className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight" id="case-inbox-title">
              {t('title')}
            </h1>
            {list.data ? (
              <p aria-live="polite" className="mt-2 text-slate-700">
                {t('results', { count: list.data.total })}
              </p>
            ) : null}
          </div>
          {hasCreatePermission ? (
            <Link
              className="nordic-button nordic-button-primary inline-flex items-center"
              href={`/${locale}/cases/new`}
            >
              {t('newCase')}
            </Link>
          ) : null}
        </div>
        {currentUser.data && !hasCreatePermission ? (
          <Alert tone="warning">
            <p>{t('permissionDescription')}</p>
          </Alert>
        ) : null}
        <form
          className="nordic-surface grid gap-4 rounded-xl p-5 md:grid-cols-2 xl:grid-cols-3"
          onSubmit={(event) => {
            event.preventDefault();
            applyFilters();
          }}
        >
          <div className="md:col-span-2 xl:col-span-3">
            <label className="block font-medium" htmlFor="case-search">
              {t('searchLabel')}
            </label>
            <input
              aria-describedby="case-search-hint"
              className="nordic-field mt-1 w-full"
              id="case-search"
              onChange={(event) => updateDraft('query', event.target.value || undefined)}
              placeholder={t('searchPlaceholder')}
              value={draft.query ?? ''}
            />
            <p className="mt-1 text-sm text-slate-600" id="case-search-hint">
              {t('searchHint')}
            </p>
          </div>
          <FilterSelect
            id="case-status"
            label={t('filterStatus')}
            onChange={(value) => updateDraft('status', value || undefined)}
            value={draft.status ?? ''}
          >
            <option value="">{t('allStatuses')}</option>
            {caseStatusSchema.options.map((value) => (
              <option key={value} value={value}>
                {t(statusMessageKey[value])}
              </option>
            ))}
          </FilterSelect>
          <FilterSelect
            id="case-risk"
            label={t('filterRisk')}
            onChange={(value) => updateDraft('riskLevel', value || undefined)}
            value={draft.riskLevel ?? ''}
          >
            <option value="">{t('allRiskLevels')}</option>
            {caseRiskLevelSchema.options.map((value) => (
              <option key={value} value={value}>
                {t(riskMessageKey[value])}
              </option>
            ))}
          </FilterSelect>
          <FilterSelect
            id="case-assignee"
            label={t('filterAssignee')}
            onChange={(value) => updateDraft('assignedUserId', value || undefined)}
            value={draft.assignedUserId ?? ''}
          >
            <option value="">{t('allAssignees')}</option>
            {visibleAssignees.map((assignee) => (
              <option key={assignee.user_id} value={assignee.user_id}>
                {assignee.display_name}
              </option>
            ))}
          </FilterSelect>
          <FilterSelect
            id="case-domain"
            label={t('filterDomain')}
            onChange={(value) => updateDraft('domain', value || undefined)}
            value={draft.domain ?? ''}
          >
            <option value="">{t('allDomains')}</option>
            {caseDomainSchema.options.map((value) => (
              <option key={value} value={value}>
                {t(domainMessageKey[value])}
              </option>
            ))}
          </FilterSelect>
          <FilterSelect
            id="case-priority"
            label={t('filterPriority')}
            onChange={(value) => updateDraft('priority', value || undefined)}
            value={draft.priority ?? ''}
          >
            <option value="">{t('allPriorities')}</option>
            {casePrioritySchema.options.map((value) => (
              <option key={value} value={value}>
                {t(priorityMessageKey[value])}
              </option>
            ))}
          </FilterSelect>
          <div className="flex items-end gap-3">
            <Button type="submit">{t('applyFilters')}</Button>
            <Button onClick={clearFilters} variant="secondary">
              {t('clearFilters')}
            </Button>
          </div>
        </form>
        {list.isPending ? (
          <p aria-live="polite" role="status">
            {t('loading')}
          </p>
        ) : null}
        {list.isError ? (
          <CaseErrorPanel error={list.error} retry={() => void list.refetch()} />
        ) : null}
        {list.data ? (
          <InboxResults
            assignees={visibleAssignees}
            filters={filters}
            locale={locale}
            onPage={goToPage}
          />
        ) : null}
      </section>
    </ProtectedPage>
  );

  function InboxResults({
    assignees: currentAssignees,
    filters: currentFilters,
    locale: currentLocale,
    onPage,
  }: {
    assignees: typeof visibleAssignees;
    filters: CaseFilters;
    locale: AppLocale;
    onPage: (offset: number) => void;
  }) {
    const data = list.data!;
    const topScrollRef = useRef<HTMLDivElement>(null);
    const viewportRef = useRef<HTMLDivElement>(null);
    const tableRef = useRef<HTMLTableElement>(null);
    const [tableWidth, setTableWidth] = useState(0);

    useEffect(() => {
      const topScroll = topScrollRef.current;
      const viewport = viewportRef.current;
      const table = tableRef.current;
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
      const observer =
        typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(updateWidth);
      observer?.observe(table);

      return () => {
        topScroll.removeEventListener('scroll', syncFromTop);
        viewport.removeEventListener('scroll', syncFromViewport);
        observer?.disconnect();
      };
    }, [data.items.length]);

    if (!data.items.length)
      return (
        <Alert tone="info">
          <h2 className="font-semibold">
            {t(hasCaseFilters(currentFilters) ? 'filterEmptyTitle' : 'emptyTitle')}
          </h2>
          <p className="mt-2">
            {t(hasCaseFilters(currentFilters) ? 'filterEmptyDescription' : 'emptyDescription')}
          </p>
        </Alert>
      );
    const nameFor = (userId: string | null) =>
      userId
        ? (currentAssignees.find((option) => option.user_id === userId)?.display_name ??
          t('identityUnavailable'))
        : t('unassigned');
    return (
      <>
        <div className="nordic-data-table overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-slate-200 bg-slate-50 px-4 py-3">
            <p className="font-semibold text-slate-900">{t('tableCaption')}</p>
            <p className="text-sm text-slate-700" id="case-table-scroll-hint">
              {t('tableScrollHint')}
            </p>
          </div>
          <div
            aria-label={t('tableScrollHint')}
            className="nordic-table-scrollbar-top"
            data-testid="case-table-scrollbar-top"
            ref={topScrollRef}
            tabIndex={0}
          >
            <div style={{ width: tableWidth }} />
          </div>
          <div
            aria-describedby="case-table-scroll-hint"
            aria-label={t('tableCaption')}
            className="nordic-table-viewport"
            data-testid="case-table-viewport"
            ref={viewportRef}
            role="region"
            tabIndex={0}
          >
            <table className="nordic-table min-w-[72rem] text-left text-sm" ref={tableRef}>
              <caption className="sr-only">{t('tableCaption')}</caption>
              <thead>
                <tr>
                  {[
                    t('caseNumber'),
                    t('caseTitle'),
                    t('status'),
                    t('priority'),
                    t('risk'),
                    t('assignee'),
                    t('dueDate'),
                    t('updated'),
                    t('domain'),
                    t('workflow'),
                  ].map((heading) => (
                    <th
                      className="whitespace-nowrap px-3 py-3 font-semibold"
                      key={heading}
                      scope="col"
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.case_id}>
                    <td className="whitespace-nowrap px-3 py-3">
                      <Link
                        className="font-semibold text-[#075985] underline underline-offset-2"
                        href={`/${currentLocale}/cases/${item.case_id}`}
                      >
                        {item.case_number}
                      </Link>
                    </td>
                    <td className="min-w-48 px-3 py-3">{item.title}</td>
                    <td className="px-3 py-3">
                      <StatusBadge value={item.status} />
                    </td>
                    <td className="px-3 py-3">
                      <PriorityBadge value={item.priority} />
                    </td>
                    <td className="px-3 py-3">
                      <RiskBadge value={item.risk_level} />
                    </td>
                    <td className="px-3 py-3">{nameFor(item.assigned_user_id)}</td>
                    <td className="whitespace-nowrap px-3 py-3">
                      {item.due_date ? (
                        <time dateTime={item.due_date}>
                          {formatCalendarDate(item.due_date, currentLocale)}
                        </time>
                      ) : (
                        t('noDueDate')
                      )}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3">
                      <time dateTime={item.updated_at}>
                        {formatTimestamp(item.updated_at, currentLocale)}
                      </time>
                    </td>
                    <td className="px-3 py-3">{t(domainMessageKey[item.domain])}</td>
                    <td className="px-3 py-3">{t('workflowUnavailable')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <nav aria-label={t('title')} className="flex items-center justify-between gap-4">
          <Button
            disabled={data.offset === 0}
            onClick={() => onPage(Math.max(0, data.offset - data.limit))}
          >
            {t('previous')}
          </Button>
          <p aria-live="polite">{t('page', { page: Math.floor(data.offset / data.limit) + 1 })}</p>
          <Button disabled={!data.has_more} onClick={() => onPage(data.offset + data.limit)}>
            {t('next')}
          </Button>
        </nav>
      </>
    );
  }
}

function FilterSelect({
  children,
  id,
  label,
  onChange,
  value,
}: {
  children: ReactNode;
  id: string;
  label: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <div>
      <label className="block font-medium" htmlFor={id}>
        {label}
      </label>
      <select
        className="nordic-field mt-1 w-full"
        id={id}
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {children}
      </select>
    </div>
  );
}
