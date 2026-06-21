import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

import { expect, test, type Page } from '@playwright/test';

const auditorEmail = 'ida.eksempel+auditor@demo.invalid';
const caseWorkerEmail = 'kari.eksempel+caseworker@demo.invalid';
const managerEmail = 'elin.eksempel+manager@demo.invalid';
const password = process.env.NORDIC_LOCAL_SEED_PASSWORD;
const fixtureTitle = `E2E Phase 23 audit trace ${Date.now()}`;

type Fixture = {
  case_id: string;
  event_type: string;
  title: string;
  workflow_run_id: string;
};

let fixture: Fixture;

function parseFixture(output: string): Fixture {
  const parsed: unknown = JSON.parse(output);
  if (
    typeof parsed !== 'object' ||
    parsed === null ||
    !('case_id' in parsed) ||
    !('event_type' in parsed) ||
    !('title' in parsed) ||
    !('workflow_run_id' in parsed) ||
    typeof parsed.case_id !== 'string' ||
    typeof parsed.event_type !== 'string' ||
    typeof parsed.title !== 'string' ||
    typeof parsed.workflow_run_id !== 'string'
  ) {
    throw new Error('Phase 23 E2E fixture seed returned an invalid fixture reference.');
  }
  return parsed;
}

async function authenticate(page: Page, email: string): Promise<void> {
  if (!password)
    throw new Error('NORDIC_LOCAL_SEED_PASSWORD must be set for the local browser test.');
  const response = await page.request.post('/api/auth/login', { data: { email, password } });
  expect(response.status()).toBe(200);
}

test.beforeAll(() => {
  if (!password)
    throw new Error('NORDIC_LOCAL_SEED_PASSWORD must be set for the local browser test.');
  fixture = parseFixture(
    execFileSync(
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
        `NORDIC_E2E_TRACE_CASE_TITLE=${fixtureTitle}`,
        'api',
        'python',
        'scripts/seed_phase23_e2e.py',
        '--password-env',
        'NORDIC_LOCAL_SEED_PASSWORD',
      ],
      { cwd: resolve(process.cwd(), '../..'), encoding: 'utf8', env: process.env },
    ),
  );
});

test('case worker opens a safe trace and auditor filters the tenant audit trail', async ({
  browser,
  page,
}) => {
  test.setTimeout(60_000);
  await authenticate(page, caseWorkerEmail);
  await page.goto(`/nb/cases/${fixture.case_id}`);
  await expect(page.getByRole('heading', { level: 1, name: fixture.title })).toBeVisible();
  await page.getByRole('link', { name: 'Åpne arbeidsflytspor' }).click();
  await expect(page).toHaveURL(new RegExp(`/nb/workflows/${fixture.workflow_run_id}/trace$`));
  const trace = page.getByTestId('workflow-trace');
  await expect(trace).toContainText('extract_fields');
  await expect(trace).toContainText('phase23-fixture');
  await expect(trace).toContainText('S1');
  await expect(trace).not.toContainText('phase23-hidden-sentinel');

  const auditorContext = await browser.newContext();
  try {
    const auditorPage = await auditorContext.newPage();
    await authenticate(auditorPage, auditorEmail);
    await auditorPage.goto('/nb/audit');
    await expect(auditorPage.getByTestId('audit-trail')).toBeVisible();
    await auditorPage.getByLabel('Saks-ID').fill(fixture.case_id);
    await auditorPage.getByLabel('Hendelsestype').fill(fixture.event_type);
    await auditorPage.getByRole('button', { name: 'Bruk filtre' }).click();
    await expect(auditorPage.getByTestId('audit-trail')).toContainText(fixture.event_type);
  } finally {
    await auditorContext.close();
  }
});

test('manager cannot browse tenant-wide audit events and an unknown trace stays unavailable', async ({
  browser,
}) => {
  const managerContext = await browser.newContext();
  try {
    const managerPage = await managerContext.newPage();
    await authenticate(managerPage, managerEmail);
    await managerPage.goto('/nb/audit');
    await expect(managerPage.getByText('Revisjonssporet er ikke tilgjengelig')).toBeVisible();
    await managerPage.goto('/nb/workflows/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/trace');
    await expect(managerPage.getByText('Arbeidsflytsporet er ikke tilgjengelig')).toBeVisible();
  } finally {
    await managerContext.close();
  }
});
