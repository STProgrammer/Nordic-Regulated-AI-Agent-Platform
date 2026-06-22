import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const reviewerEmail = 'ole.eksempel+reviewer@demo.invalid';
const password = process.env.NORDIC_LOCAL_SEED_PASSWORD;
const fixtureTitle = `E2E Phase 30 accessibility ${Date.now()}`;

type Fixture = {
  approval_id: string;
  case_id: string;
  title: string;
};

let fixture: Fixture;

function parseFixture(output: string): Fixture {
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
    throw new Error('Phase 30 accessibility fixture seed returned invalid references.');
  }
  return parsed;
}

async function authenticate(page: Page): Promise<void> {
  if (!password) throw new Error('NORDIC_LOCAL_SEED_PASSWORD must be set.');
  const response = await page.request.post('/api/auth/login', {
    data: { email: reviewerEmail, password },
  });
  expect(response.status()).toBe(200);
}

async function expectWcagAAndAa(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  expect(results.violations).toEqual([]);
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
        `NORDIC_E2E_APPROVAL_CASE_TITLE=${fixtureTitle}`,
        'api',
        'python',
        'scripts/seed_phase22_e2e.py',
        '--password-env',
        'NORDIC_LOCAL_SEED_PASSWORD',
      ],
      { cwd: resolve(process.cwd(), '../..'), encoding: 'utf8', env: process.env },
    ),
  );
});

test('critical Norwegian workflow pages meet WCAG A/AA and remain keyboard-operable', async ({
  page,
}) => {
  test.setTimeout(90_000);

  await page.goto('/nb/login');
  await expect(page.getByRole('heading', { level: 1, name: 'Logg inn' })).toBeVisible();
  await expectWcagAAndAa(page);
  await page.getByRole('button', { name: 'English' }).focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/en\/login$/);

  await authenticate(page);
  await page.goto('/nb/cases');
  const skipLink = page.getByRole('link', { name: 'Hopp til hovedinnhold' });
  await expect(page.getByRole('heading', { level: 1, name: 'Saksinnboks' })).toBeVisible();
  // Next.js development tooling adds one framework-owned portal to the tab
  // order. The skip link must still be the first application-owned target.
  await page.keyboard.press('Tab');
  if (!(await skipLink.evaluate((element) => element === document.activeElement))) {
    await page.keyboard.press('Tab');
  }
  await expect(skipLink).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main-content')).toBeFocused();
  await expect(page.getByRole('heading', { level: 1, name: 'Saksinnboks' })).toBeVisible();
  await expectWcagAAndAa(page);

  await page.goto(`/nb/cases/${fixture.case_id}`);
  await expect(page.getByRole('heading', { level: 1, name: fixture.title })).toBeVisible();
  await expectWcagAAndAa(page);

  await page.goto(`/nb/approvals/${fixture.approval_id}`);
  await expect(page.getByTestId('approval-review-packet')).toBeVisible();
  await expectWcagAAndAa(page);
  const approvalAction = page.getByTestId('approval-edit-and-approve');
  await approvalAction.focus();
  await page
    .getByTestId('approval-final-text-input')
    .fill('Syntetisk tekst for tastaturnavigasjon.');
  await approvalAction.click();
  await expect(page.getByTestId('approval-decision-confirmation')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('approval-decision-confirmation')).toBeHidden();
  await expect(approvalAction).toBeFocused();
});
