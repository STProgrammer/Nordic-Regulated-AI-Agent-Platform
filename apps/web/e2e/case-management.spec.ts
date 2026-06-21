import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

import { expect, test, type Page } from '@playwright/test';

const caseWorkerEmail = 'kari.eksempel+caseworker@demo.invalid';
const password = process.env.NORDIC_LOCAL_SEED_PASSWORD;
const reviewerEmail = 'ole.eksempel+reviewer@demo.invalid';
const fixtureTitle = `E2E Phase 22 human approval ${Date.now()}`;

type SeededApprovalFixture = {
  approval_id: string;
  case_id: string;
  title: string;
};

let fixture: SeededApprovalFixture;

function requireE2eCredentials() {
  if (!password) {
    throw new Error('NORDIC_LOCAL_SEED_PASSWORD must be set for the local browser smoke test.');
  }
}

function parseFixture(output: string): SeededApprovalFixture {
  const parsed: unknown = JSON.parse(output);
  if (
    typeof parsed !== 'object' ||
    parsed === null ||
    !('approval_id' in parsed) ||
    !('case_id' in parsed) ||
    !('title' in parsed) ||
    typeof parsed.approval_id !== 'string' ||
    typeof parsed.case_id !== 'string' ||
    typeof parsed.title !== 'string'
  ) {
    throw new Error('Phase 22 E2E fixture seed returned an invalid fixture reference.');
  }
  return parsed;
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
      '-e',
      `NORDIC_E2E_APPROVAL_CASE_TITLE=${fixtureTitle}`,
      'api',
      'python',
      'scripts/seed_phase22_e2e.py',
      '--password-env',
      'NORDIC_LOCAL_SEED_PASSWORD',
    ],
    { cwd: resolve(process.cwd(), '../..'), encoding: 'utf8', env: process.env },
  );
  fixture = parseFixture(output);
});

test('reviewer resolves a pre-seeded human approval and the case worker sees approval', async ({
  browser,
  page,
}) => {
  test.setTimeout(60_000);
  await authenticate(page, reviewerEmail);
  await page.goto('/nb/approvals');
  await expect(page).toHaveURL(/\/nb\/approvals$/);
  await expect(page.getByTestId('approval-queue')).toBeVisible();
  const queueItem = page.getByTestId(`approval-queue-item-${fixture.approval_id}`);
  await expect(queueItem).toBeVisible({ timeout: 15_000 });
  await queueItem.getByTestId('open-approval-packet').click();
  await expect(page).toHaveURL(new RegExp(`/nb/approvals/${fixture.approval_id}$`));
  const packet = page.getByTestId('approval-review-packet');
  await expect(packet).toBeVisible({ timeout: 15_000 });
  await expect(packet.getByRole('heading', { level: 1, name: fixture.title })).toBeVisible();
  await page
    .getByTestId('approval-final-text-input')
    .fill('Syntetisk menneskegodkjent slutttekst.');
  await page.getByTestId('approval-edit-and-approve').click();
  const confirmation = page.getByTestId('approval-decision-confirmation');
  await expect(confirmation).toBeVisible();
  await confirmation.getByTestId('approval-decision-confirm').click();
  await expect(page.getByTestId('approval-decision-status')).toHaveAttribute(
    'data-approval-status',
    'approved',
    { timeout: 30_000 },
  );
  await expect(page.getByTestId('approval-final-text')).toHaveText(
    'Syntetisk menneskegodkjent slutttekst.',
  );
  const downloadPromise = page.waitForEvent('download');
  await page.getByTestId('approved-output-download-pdf').click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('approved-output.pdf');
  await page.getByTestId('mock-handoff-teams').click();
  await expect(page.getByTestId('mock-handoff-confirmation')).toBeVisible();
  await page.getByTestId('mock-handoff-confirm').click();
  await expect(page.getByText('Den simulerte overleveringen er registrert.')).toBeVisible();

  const workerContext = await browser.newContext();
  const workerPage = await workerContext.newPage();
  try {
    await authenticate(workerPage, caseWorkerEmail);
    await workerPage.goto(`/nb/cases/${fixture.case_id}`);
    await expect(workerPage).toHaveURL(new RegExp(`/nb/cases/${fixture.case_id}$`));
    await expect(workerPage.getByTestId('case-approval-status')).toHaveAttribute(
      'data-case-status',
      'approved',
      { timeout: 30_000 },
    );
  } finally {
    await workerContext.close();
  }
});
