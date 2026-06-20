'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';

import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { AppLocale } from '@/i18n/routing';
import { authApi } from '@/lib/api/auth';
import { ApiFailure } from '@/lib/api/contracts';
import { safeReturnPath } from '@/lib/auth/paths';
import { refreshCurrentUser } from '@/lib/auth/query';
import { loginSchema, type LoginFormValues } from '@/lib/validation/login';

type LoginTranslation = ReturnType<typeof useTranslations<'login'>>;

function errorMessage(error: unknown, translate: LoginTranslation): string {
  if (!(error instanceof ApiFailure)) {
    return translate('genericError');
  }

  if (error.code === 'invalid_credentials') {
    return translate('invalidCredentials');
  }

  if (error.code === 'login_rate_limited') {
    return translate('rateLimited', { seconds: error.retryAfterSeconds ?? 0 });
  }

  if (error.code === 'authentication_unavailable' || error.status === 503) {
    return translate('unavailable');
  }

  return translate('genericError');
}

export function LoginForm() {
  const locale = useLocale() as AppLocale;
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const t = useTranslations('login');
  const errorRef = useRef<HTMLParagraphElement>(null);
  const [submissionError, setSubmissionError] = useState<ApiFailure | null>(null);
  const form = useForm<LoginFormValues>({
    defaultValues: { email: '', password: '' },
    mode: 'onBlur',
    resolver: zodResolver(loginSchema),
  });
  const mutation = useMutation({
    mutationFn: async (values: LoginFormValues) => {
      await authApi.login(values);
      return refreshCurrentUser(queryClient);
    },
  });

  async function submit(values: LoginFormValues) {
    setSubmissionError(null);
    try {
      await mutation.mutateAsync(values);
      router.replace(safeReturnPath(searchParams.get('returnTo'), locale));
    } catch (error) {
      setSubmissionError(error instanceof ApiFailure ? error : null);
    } finally {
      form.setValue('password', '');
    }
  }

  const emailError = form.formState.errors.email;
  const passwordError = form.formState.errors.password;

  useEffect(() => {
    errorRef.current?.focus();
  }, [submissionError]);

  return (
    <form className="space-y-5" noValidate onSubmit={form.handleSubmit(submit)}>
      {submissionError !== null ? (
        <Alert>
          <p aria-live="assertive" ref={errorRef} tabIndex={-1}>
            {errorMessage(submissionError, t)}
          </p>
          {submissionError.requestId ? (
            <p className="mt-2 text-sm">
              {t('requestId', { requestId: submissionError.requestId })}
            </p>
          ) : null}
        </Alert>
      ) : null}
      <div>
        <label className="block font-medium" htmlFor="email">
          {t('emailLabel')}
        </label>
        <input
          aria-describedby={emailError ? 'email-hint email-error' : 'email-hint'}
          aria-invalid={Boolean(emailError)}
          autoComplete="username"
          className="mt-1 w-full rounded-md border border-slate-400 bg-white px-3 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
          id="email"
          inputMode="email"
          {...form.register('email')}
        />
        <p className="mt-1 text-sm text-slate-600" id="email-hint">
          {t('emailHint')}
        </p>
        {emailError ? (
          <p className="mt-1 text-sm text-red-700" id="email-error">
            {t('emailRequired')}
          </p>
        ) : null}
      </div>
      <div>
        <label className="block font-medium" htmlFor="password">
          {t('passwordLabel')}
        </label>
        <input
          aria-describedby={passwordError ? 'password-error' : undefined}
          aria-invalid={Boolean(passwordError)}
          autoComplete="current-password"
          className="mt-1 w-full rounded-md border border-slate-400 bg-white px-3 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
          id="password"
          type="password"
          {...form.register('password')}
        />
        {passwordError ? (
          <p className="mt-1 text-sm text-red-700" id="password-error">
            {passwordError.type === 'too_big' ? t('passwordTooLong') : t('passwordRequired')}
          </p>
        ) : null}
      </div>
      <Button disabled={mutation.isPending} type="submit">
        {mutation.isPending ? t('submitting') : t('submit')}
      </Button>
    </form>
  );
}
