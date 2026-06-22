import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const adminEmail = 'per.eksempel+admin@demo.invalid';
const workerEmail = 'kari.eksempel+caseworker@demo.invalid';
const managerEmail = 'elin.eksempel+manager@demo.invalid';
const password = process.env.NORDIC_LOCAL_SEED_PASSWORD;
const browserOrigin = new URL(process.env.NORDIC_E2E_BASE_URL ?? 'http://127.0.0.1:3000').origin;
const fixtureTitle = `E2E Phase 24 controlled memory ${Date.now()}`;
const terminologySuffix = Date.now().toString(36);

type Fixture = { case_id: string; title: string };
let fixture: Fixture;

function parseFixture(output: string): Fixture {
  const parsed: unknown = JSON.parse(output);
  if (
    typeof parsed !== 'object' ||
    parsed === null ||
    !('case_id' in parsed) ||
    !('title' in parsed) ||
    typeof parsed.case_id !== 'string' ||
    typeof parsed.title !== 'string'
  ) {
    throw new Error('Phase 24 E2E fixture seed returned invalid references.');
  }
  return parsed;
}

async function authenticate(page: Page, email: string): Promise<void> {
  if (!password) throw new Error('NORDIC_LOCAL_SEED_PASSWORD must be set.');
  const response = await page.request.post('/api/auth/login', { data: { email, password } });
  expect(response.status()).toBe(200);
}

async function startAndWaitForDraft(request: APIRequestContext): Promise<void> {
  const start = await request.post(`/api/cases/${fixture.case_id}/workflows/run`, {
    data: { workflow: 'drafting', output_language: 'nb' },
    headers: { Origin: browserOrigin },
  });
  expect(start.status()).toBe(202);
  const workflowRunId = ((await start.json()) as { data: { workflow_run_id: string } }).data
    .workflow_run_id;
  await expect
    .poll(async () => (await request.get(`/api/workflows/${workflowRunId}`)).json())
    .toMatchObject({ data: { status: 'completed' } });
}

test.beforeAll(() => {
  if (!password) throw new Error('NORDIC_LOCAL_SEED_PASSWORD must be set.');
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
        `NORDIC_E2E_MEMORY_CASE_TITLE=${fixtureTitle}`,
        'api',
        'python',
        'scripts/seed_phase24_e2e.py',
        '--password-env',
        'NORDIC_LOCAL_SEED_PASSWORD',
      ],
      { cwd: resolve(process.cwd(), '../..'), encoding: 'utf8', env: process.env },
    ),
  );
});

test('Admin controls safe memory and disablement stops future Drafting application', async ({
  browser,
  page,
}) => {
  test.setTimeout(90_000);
  await authenticate(page, adminEmail);
  const reset = await page.request.put('/api/admin/memory/settings', {
    data: { enabled: false },
    headers: { Origin: browserOrigin },
  });
  expect(reset.status()).toBe(200);
  await page.goto('/nb/admin');
  await expect(page.getByTestId('controlled-memory')).toBeVisible();
  await page.getByRole('button', { name: 'Aktiver kontrollert minne' }).click();
  await page.getByLabel('Opprinnelig term').fill(`vedtak-${terminologySuffix}`);
  await page.getByLabel('Foretrukket term').fill(`avgjørelse-${terminologySuffix}`);
  await page.getByRole('button', { name: 'Opprett oppføring' }).click();
  await expect(page.getByText('Oppføringen er opprettet.')).toBeVisible();

  const workerContext = await browser.newContext();
  try {
    const workerPage = await workerContext.newPage();
    await authenticate(workerPage, workerEmail);
    await startAndWaitForDraft(workerPage.request);
  } finally {
    await workerContext.close();
  }
  const usageBefore = await page.request.get('/api/audit/events?event_type=memory.use_recorded');
  expect(usageBefore.status()).toBe(200);
  expect(JSON.stringify(await usageBefore.json())).not.toContain(`vedtak-${terminologySuffix}`);
  const usageCount = ((await usageBefore.json()) as { data: { items: unknown[] } }).data.items
    .length;

  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: 'Deaktiver kontrollert minne' }).click();
  const secondWorker = await browser.newContext();
  try {
    const secondWorkerPage = await secondWorker.newPage();
    await authenticate(secondWorkerPage, workerEmail);
    await startAndWaitForDraft(secondWorkerPage.request);
  } finally {
    await secondWorker.close();
  }
  const usageAfter = await page.request.get('/api/audit/events?event_type=memory.use_recorded');
  expect(((await usageAfter.json()) as { data: { items: unknown[] } }).data.items).toHaveLength(
    usageCount,
  );

  const managerContext = await browser.newContext();
  try {
    const managerPage = await managerContext.newPage();
    await authenticate(managerPage, managerEmail);
    await managerPage.goto('/nb/admin');
    await expect(
      managerPage.getByText('Du har ikke tilgang til organisasjonens kontrollerte minne.'),
    ).toBeVisible();
  } finally {
    await managerContext.close();
  }
});
