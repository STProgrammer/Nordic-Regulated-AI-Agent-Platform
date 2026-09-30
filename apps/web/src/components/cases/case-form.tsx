'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { AppLocale } from '@/i18n/routing';
import { casesApi } from '@/lib/api/cases';
import {
  ApiFailure,
  caseDomainSchema,
  caseLanguageSchema,
  casePrioritySchema,
} from '@/lib/api/contracts';
import { caseQueryKeys } from '@/lib/cases/query';
import { domainMessageKey, languageMessageKey, priorityMessageKey } from '@/lib/cases/labels';
import { useCurrentUser } from '@/lib/auth/query';

const formSchema = z.object({
  title: z.string().trim().min(1).max(500),
  description: z.string().trim().min(1).max(20_000),
  domain: caseDomainSchema,
  priority: casePrioritySchema,
  language: caseLanguageSchema,
  due_date: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/)
    .or(z.literal('')),
  external_reference: z.string().trim().max(255),
});
type CaseFormValues = z.infer<typeof formSchema>;

function fieldError(error: unknown): keyof CaseFormValues | undefined {
  if (!(error instanceof ApiFailure)) return undefined;
  const location = error.details[0]?.field?.replace(/^body\./, '');
  return location &&
    [
      'title',
      'description',
      'domain',
      'priority',
      'language',
      'due_date',
      'external_reference',
    ].includes(location)
    ? (location as keyof CaseFormValues)
    : undefined;
}

export function CaseForm() {
  const locale = useLocale() as AppLocale;
  const router = useRouter();
  const queryClient = useQueryClient();
  const t = useTranslations('cases');
  const currentUser = useCurrentUser();
  const errorRef = useRef<HTMLParagraphElement>(null);
  const [submitFailure, setSubmitFailure] = useState<ApiFailure | null>(null);
  const form = useForm<CaseFormValues>({
    defaultValues: {
      description: '',
      domain: 'public_sector',
      due_date: '',
      external_reference: '',
      language: locale,
      priority: 'normal',
      title: '',
    },
    resolver: zodResolver(formSchema),
  });
  const mutation = useMutation({
    mutationFn: casesApi.submit,
    onSuccess: async (submittedCase) => {
      await queryClient.invalidateQueries({ queryKey: caseQueryKeys.lists() });
      queryClient.setQueryData(caseQueryKeys.detail(submittedCase.case_id), submittedCase);
      router.replace(`/${locale}/cases/${submittedCase.case_id}`);
    },
  });

  useEffect(() => {
    errorRef.current?.focus();
  }, [submitFailure]);

  async function submit(values: CaseFormValues) {
    setSubmitFailure(null);
    try {
      await mutation.mutateAsync({
        description: values.description,
        domain: values.domain,
        external_reference: values.external_reference || undefined,
        due_date: values.due_date || undefined,
        language: values.language,
        priority: values.priority,
        title: values.title,
      });
    } catch (error) {
      if (error instanceof ApiFailure) {
        setSubmitFailure(error);
        const field = fieldError(error);
        if (field) form.setError(field, { message: t('requiredError') });
      } else {
        setSubmitFailure(new ApiFailure({ code: 'submission_failed', status: 0 }));
      }
    }
  }

  function messageFor(name: keyof CaseFormValues): string | undefined {
    const error = form.formState.errors[name];
    if (!error) return undefined;
    return error.type === 'too_big' ? t('tooLongError') : t('requiredError');
  }

  if (
    currentUser.data &&
    !currentUser.data.roles.some((role) => ['Admin', 'Case Worker', 'Manager'].includes(role))
  ) {
    return (
      <Alert tone="warning">
        <p>{t('permissionDescription')}</p>
      </Alert>
    );
  }

  return (
    <form
      className="nordic-surface nordic-card space-y-5"
      noValidate
      onSubmit={form.handleSubmit(submit)}
    >
      {submitFailure ? (
        <Alert tone="error">
          <p aria-live="assertive" ref={errorRef} tabIndex={-1}>
            {t('submitError')}
          </p>
          {submitFailure.requestId ? (
            <p className="mt-2 text-sm">{t('requestId', { requestId: submitFailure.requestId })}</p>
          ) : null}
        </Alert>
      ) : null}
      <TextField
        error={messageFor('title')}
        id="case-title"
        label={t('fields.title')}
        registration={form.register('title')}
      />
      <TextField
        error={messageFor('description')}
        id="case-description"
        label={t('fields.description')}
        multiline
        registration={form.register('description')}
      />
      <SelectField
        error={messageFor('domain')}
        id="case-domain"
        label={t('fields.domain')}
        registration={form.register('domain')}
      >
        {caseDomainSchema.options.map((value) => (
          <option key={value} value={value}>
            {t(domainMessageKey[value])}
          </option>
        ))}
      </SelectField>
      <SelectField
        error={messageFor('priority')}
        id="case-priority"
        label={t('fields.priority')}
        registration={form.register('priority')}
      >
        {casePrioritySchema.options.map((value) => (
          <option key={value} value={value}>
            {t(priorityMessageKey[value])}
          </option>
        ))}
      </SelectField>
      <SelectField
        error={messageFor('language')}
        id="case-language"
        label={t('fields.language')}
        registration={form.register('language')}
      >
        {caseLanguageSchema.options.map((value) => (
          <option key={value} value={value}>
            {t(languageMessageKey[value])}
          </option>
        ))}
      </SelectField>
      <TextField
        error={messageFor('due_date')}
        id="case-due-date"
        label={t('fields.dueDate')}
        registration={form.register('due_date')}
        type="date"
      />
      <TextField
        error={messageFor('external_reference')}
        id="case-external-reference"
        label={t('fields.externalReference')}
        registration={form.register('external_reference')}
      />
      <div className="flex flex-wrap gap-3">
        <Button disabled={mutation.isPending} type="submit">
          {mutation.isPending ? t('submitting') : t('submit')}
        </Button>
        <Link
          className="nordic-button nordic-button-secondary inline-flex items-center"
          href={`/${locale}/cases`}
        >
          {t('cancel')}
        </Link>
      </div>
    </form>
  );
}

const inputClass = 'nordic-field mt-1 w-full';
type Registration = ReturnType<ReturnType<typeof useForm<CaseFormValues>>['register']>;
function TextField({
  error,
  id,
  label,
  multiline = false,
  registration,
  type = 'text',
}: {
  error?: string | undefined;
  id: string;
  label: string;
  multiline?: boolean;
  registration: Registration;
  type?: string;
}) {
  const describedBy = error ? `${id}-error` : undefined;
  return (
    <div>
      <label className="block font-medium" htmlFor={id}>
        {label}
      </label>
      {multiline ? (
        <textarea
          aria-describedby={describedBy}
          aria-invalid={Boolean(error)}
          className={`${inputClass} min-h-32`}
          id={id}
          {...registration}
        />
      ) : (
        <input
          aria-describedby={describedBy}
          aria-invalid={Boolean(error)}
          className={inputClass}
          id={id}
          type={type}
          {...registration}
        />
      )}
      {error ? (
        <p className="mt-1 text-sm font-medium text-[#b42318]" id={`${id}-error`}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
function SelectField({
  children,
  error,
  id,
  label,
  registration,
}: {
  children: ReactNode;
  error?: string | undefined;
  id: string;
  label: string;
  registration: Registration;
}) {
  return (
    <div>
      <label className="block font-medium" htmlFor={id}>
        {label}
      </label>
      <select
        aria-describedby={error ? `${id}-error` : undefined}
        aria-invalid={Boolean(error)}
        className={inputClass}
        id={id}
        {...registration}
      >
        {children}
      </select>
      {error ? (
        <p className="mt-1 text-sm font-medium text-[#b42318]" id={`${id}-error`}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
