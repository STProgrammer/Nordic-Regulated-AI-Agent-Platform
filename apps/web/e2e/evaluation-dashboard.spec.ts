import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

import { expect, test, type Page } from '@playwright/test';

const adminEmail = 'per.eksempel+admin@demo.invalid';
const managerEmail = 'elin.eksempel+manager@demo.invalid';
const password = process.env.NORDIC_LOCAL_SEED_PASSWORD;

type Fixture = {
  case_key: string;
  evaluation_result_id: string;
  evaluation_run_id: string;
};

let fixture: Fixture;

function parseFixture(output: string): Fixture {
  const parsed: unknown = JSON.parse(output);
  if (
    typeof parsed !== 'object' ||
    parsed === null ||
    !('case_key' in parsed) ||
    !('evaluation_result_id' in parsed) ||
    !('evaluation_run_id' in parsed) ||
    typeof parsed.case_key !== 'string' ||
    typeof parsed.evaluation_result_id !== 'string' ||
    typeof parsed.evaluation_run_id !== 'string'
  ) {
    throw new Error('Phase 26 E2E fixture seed returned invalid references.');
  }
  return parsed;
}

async function authenticate(page: Page, email: string): Promise<void> {
  if (!password) throw new Error('NORDIC_LOCAL_SEED_PASSWORD must be set.');
  const response = await page.request.post('/api/auth/login', { data: { email, password } });
  expect(response.status()).toBe(200);
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
        'api',
        'python',
        'scripts/seed_phase26_e2e.py',
        '--password-env',
        'NORDIC_LOCAL_SEED_PASSWORD',
      ],
      { cwd: resolve(process.cwd(), '../..'), encoding: 'utf8', env: process.env },
    ),
  );
});

test('Admin follows the safe evaluation dashboard, failure detail, and Markdown report path', async ({
  page,
}) => {
  test.setTimeout(90_000);
  await authenticate(page, adminEmail);
  await page.goto('/nb/evaluations');
  await expect(page.getByTestId('evaluation-dashboard')).toBeVisible();
  await page.getByRole('link', { name: 'Åpne kjøring' }).first().click();
  await expect(page).toHaveURL(new RegExp(`/nb/evaluations/runs/${fixture.evaluation_run_id}$`));
  await expect(page.getByTestId('evaluation-run-detail')).toContainText('citation_mismatch');

  const downloadPromise = page.waitForEvent('download');
  await page.getByTestId('evaluation-report-download').click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('evaluation-report.md');

  await page.getByRole('link', { name: fixture.case_key }).click();
  await expect(page).toHaveURL(
    new RegExp(
      `/nb/evaluations/runs/${fixture.evaluation_run_id}/results/${fixture.evaluation_result_id}$`,
    ),
  );
  await expect(page.getByTestId('evaluation-result-detail')).toContainText('citation_mismatch');
});

test('non-Admin cannot browse evaluation data', async ({ browser }) => {
  const managerContext = await browser.newContext();
  try {
    const managerPage = await managerContext.newPage();
    await authenticate(managerPage, managerEmail);
    await managerPage.goto('/nb/evaluations');
    await expect(
      managerPage.getByText('Du har ikke tilgang til organisasjonens evalueringer.'),
    ).toBeVisible();
  } finally {
    await managerContext.close();
  }
});
