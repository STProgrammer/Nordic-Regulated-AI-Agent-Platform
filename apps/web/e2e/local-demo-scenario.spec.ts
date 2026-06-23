import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

import { expect, test, type Page } from '@playwright/test';

const caseWorkerEmail = 'kari.eksempel+caseworker@demo.invalid';
const password = process.env.NORDIC_LOCAL_SEED_PASSWORD;
const reviewerEmail = 'ole.eksempel+reviewer@demo.invalid';

type DemoFixture = {
  approval_id: string;
  approval_url: string;
  case_id: string;
  case_url: string;
  case_worker_email: string;
  document_id: string;
  evaluation_run_id: string;
  evaluation_url: string;
  rag_answer_request: { answer_language: string; case_id: string; question: string };
  reviewer_email: string;
  title: string;
  trace_workflow_run_id: string;
  trace_url: string;
};

type RagAnswerResponse = {
  data: {
    answer: string;
    citations: { label: string }[];
    language: string;
    outcome: string;
  };
};

let fixture: DemoFixture;

function requireE2eCredentials(): void {
  if (!password) {
    throw new Error('NORDIC_LOCAL_SEED_PASSWORD must be set for the Phase 34 demo scenario.');
  }
}

function parseFixture(output: string): DemoFixture {
  const jsonLine = output.trim().split(/\r?\n/).at(-1);
  if (!jsonLine) {
    throw new Error('Phase 34 demo seed returned no fixture reference.');
  }
  const parsed: unknown = JSON.parse(jsonLine);
  if (
    typeof parsed !== 'object' ||
    parsed === null ||
    !('approval_id' in parsed) ||
    !('approval_url' in parsed) ||
    !('case_id' in parsed) ||
    !('case_url' in parsed) ||
    !('case_worker_email' in parsed) ||
    !('document_id' in parsed) ||
    !('evaluation_run_id' in parsed) ||
    !('evaluation_url' in parsed) ||
    !('rag_answer_request' in parsed) ||
    !('reviewer_email' in parsed) ||
    !('title' in parsed) ||
    !('trace_workflow_run_id' in parsed) ||
    !('trace_url' in parsed)
  ) {
    throw new Error('Phase 34 demo seed returned an invalid fixture reference.');
  }
  const value = parsed as DemoFixture;
  if (
    value.case_worker_email !== caseWorkerEmail ||
    value.reviewer_email !== reviewerEmail ||
    value.rag_answer_request.case_id !== value.case_id
  ) {
    throw new Error('Phase 34 demo seed returned an inconsistent fixture reference.');
  }
  return value;
}

async function authenticate(page: Page, email: string): Promise<void> {
  const response = await page.request.post('/api/auth/login', {
    data: { email, password: password! },
  });
  expect(response.status()).toBe(200);
}

test.beforeAll(() => {
  requireE2eCredentials();
  const output = execFileSync(
    'docker',
    [
      'compose',
      '--env-file',
      '.env.example',
      'exec',
      '-T',
      '-e',
      'NORDIC_LOCAL_SEED_PASSWORD',
      'api',
      'python',
      'scripts/seed_phase34_demo.py',
      '--password-env',
      'NORDIC_LOCAL_SEED_PASSWORD',
    ],
    { cwd: resolve(process.cwd(), '../..'), encoding: 'utf8', env: process.env },
  );
  fixture = parseFixture(output);
});

test('the synthetic local demo covers the case, cited RAG, trace, approval, audit, and evaluation', async ({
  browser,
  page,
}) => {
  test.setTimeout(90_000);
  await authenticate(page, fixture.case_worker_email);
  await page.goto('/nb/cases');
  await expect(page.getByRole('heading', { level: 1, name: 'Saksinnboks' })).toBeVisible();
  await page.goto(fixture.case_url);
  await expect(page.getByRole('heading', { level: 1, name: fixture.title })).toBeVisible();
  await expect(
    page.getByText('Syntetisk rutine for saksbehandling', { exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId('case-approval-status')).toHaveAttribute(
    'data-case-status',
    'waiting_for_human_review',
  );

  const rag = await page.evaluate(async (request) => {
    const response = await fetch('/api/retrieval/answer', {
      body: JSON.stringify(request),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });
    return { body: (await response.json()) as RagAnswerResponse, status: response.status };
  }, fixture.rag_answer_request);
  expect(rag.status).toBe(200);
  const ragBody = rag.body;
  expect(ragBody.data.outcome).toBe('answered');
  expect(ragBody.data.language).toBe('nb');
  expect(ragBody.data.citations).toContainEqual(expect.objectContaining({ label: 'S1' }));
  expect(ragBody.data.answer).toContain('[S1]');

  await page.goto(fixture.trace_url);
  await expect(page.getByTestId('workflow-trace')).toBeVisible();
  await expect(page.getByRole('heading', { level: 3, name: 'hybrid_retrieval' })).toBeVisible();

  const reviewerContext = await browser.newContext();
  const reviewerPage = await reviewerContext.newPage();
  try {
    await authenticate(reviewerPage, fixture.reviewer_email);
    await reviewerPage.goto('/nb/approvals');
    const queueItem = reviewerPage.getByTestId(`approval-queue-item-${fixture.approval_id}`);
    await expect(queueItem).toBeVisible({ timeout: 15_000 });
    await reviewerPage.goto(fixture.approval_url);
    await expect(reviewerPage.getByTestId('approval-review-packet')).toBeVisible({
      timeout: 15_000,
    });
    await reviewerPage
      .getByTestId('approval-final-text-input')
      .fill('Syntetisk menneskegodkjent slutttekst.');
    await reviewerPage.getByTestId('approval-edit-and-approve').click();
    await reviewerPage.getByTestId('approval-decision-confirm').click();
    await expect(reviewerPage.getByTestId('approval-decision-status')).toHaveAttribute(
      'data-approval-status',
      'approved',
      { timeout: 30_000 },
    );
  } finally {
    await reviewerContext.close();
  }

  const adminContext = await browser.newContext();
  const adminPage = await adminContext.newPage();
  try {
    await authenticate(adminPage, 'per.eksempel+admin@demo.invalid');
    await adminPage.goto('/nb/audit');
    await expect(adminPage.getByTestId('audit-trail')).toBeVisible();
    const audit = await adminPage.request.get(`/api/audit/events?case_id=${fixture.case_id}`);
    expect(audit.status()).toBe(200);
    await adminPage.goto(fixture.evaluation_url);
    await expect(adminPage.getByTestId('evaluation-run-detail')).toBeVisible();
    await expect(adminPage.getByText('Fullført', { exact: true })).toBeVisible();
    const metrics = await adminPage.request.get('http://127.0.0.1:8000/metrics');
    expect(metrics.status()).toBe(200);
    expect(await metrics.text()).toContain('nordic_api_http');
  } finally {
    await adminContext.close();
  }
});
