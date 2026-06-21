import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

import { expect, test } from '@playwright/test';

const caseWorkerEmail = process.env.NORDIC_E2E_CASE_WORKER_EMAIL;
const password = process.env.NORDIC_LOCAL_SEED_PASSWORD;
const reviewerEmail = 'ole.eksempel+reviewer@demo.invalid';
const fixtureTitle = `E2E Phase 22 human approval ${Date.now()}`;

function requireE2eCredentials() {
  if (!caseWorkerEmail || !password) {
    throw new Error(
      'NORDIC_E2E_CASE_WORKER_EMAIL and NORDIC_LOCAL_SEED_PASSWORD must be set for the local browser smoke test.',
    );
  }
}

test.beforeAll(() => {
  requireE2eCredentials();
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
    { cwd: resolve(process.cwd(), '../..'), env: process.env, stdio: 'inherit' },
  );
});

test('reviewer resolves a pre-seeded human approval and the case worker sees approval', async ({
  browser,
  page,
}) => {
  test.setTimeout(60_000);
  await page.goto('/nb/login');
  await page.getByLabel('E-postadresse').fill(reviewerEmail);
  await page.getByLabel('Passord').fill(password!);
  await page.getByRole('button', { name: 'Logg inn' }).click();
  await page.goto('/nb/approvals');
  await expect(page.getByRole('heading', { name: 'Godkjenningskø' })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(fixtureTitle)).toBeVisible();
  await page
    .locator('li')
    .filter({ hasText: fixtureTitle })
    .getByRole('link', { name: 'Åpne vurderingspakke' })
    .click();
  await expect(page.getByText('Dette uforanderlige KI-utkastet er ikke endelig.')).toBeVisible();
  await expect(
    page.getByText('Syntetisk uforanderlig KI-utkast for lokal Phase 22-validering.'),
  ).toBeVisible();
  await page
    .getByLabel('Endelig mennesketekst (kun ved rediger og godkjenn)')
    .fill('Syntetisk menneskegodkjent slutttekst.');
  await page.getByRole('button', { name: 'Rediger og godkjenn' }).click();
  const confirmation = page.getByRole('alertdialog', {
    name: 'Bekreft vurdererbeslutning',
  });
  await expect(confirmation).toBeVisible();
  await confirmation.getByRole('button', { name: 'Bekreft' }).click();
  await expect(page.getByText('Godkjent av menneske')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Syntetisk menneskegodkjent slutttekst.')).toBeVisible();

  const workerContext = await browser.newContext();
  const workerPage = await workerContext.newPage();
  await workerPage.goto('/nb/login');
  await workerPage.getByLabel('E-postadresse').fill(caseWorkerEmail!);
  await workerPage.getByLabel('Passord').fill(password!);
  await workerPage.getByRole('button', { name: 'Logg inn' }).click();
  await expect(workerPage.getByRole('heading', { name: 'Saksinnboks' })).toBeVisible({
    timeout: 15_000,
  });
  await workerPage.getByLabel('Søk i saker').fill(fixtureTitle);
  await workerPage.getByRole('button', { name: 'Bruk filtre' }).click();
  const result = workerPage.getByRole('row', { name: new RegExp(fixtureTitle) });
  await expect(result).toBeVisible();
  await result.getByRole('link', { name: /^CASE-/ }).click();
  await expect(workerPage.getByText('Denne saken har et menneskegodkjent utfall.')).toBeVisible({
    timeout: 30_000,
  });
  await workerContext.close();
});
