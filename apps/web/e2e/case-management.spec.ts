import { expect, test } from '@playwright/test';

const email = process.env.NORDIC_E2E_CASE_WORKER_EMAIL;
const password = process.env.NORDIC_LOCAL_SEED_PASSWORD;

test.beforeEach(() => {
  if (!email || !password) {
    throw new Error(
      'NORDIC_E2E_CASE_WORKER_EMAIL and NORDIC_LOCAL_SEED_PASSWORD must be set for the local browser smoke test.',
    );
  }
});

test('case worker can inspect indexed synthetic document evidence in Bokmål', async ({ page }) => {
  test.setTimeout(90_000);
  const title = `E2E syntetisk sak ${Date.now()}`;
  await page.goto('/nb/login');
  await page.getByLabel('E-postadresse').fill(email!);
  await page.getByLabel('Passord').fill(password!);
  await page.getByRole('button', { name: 'Logg inn' }).click();
  await expect(page.getByRole('heading', { name: 'Saksinnboks' })).toBeVisible({ timeout: 15_000 });

  await page.getByRole('link', { name: 'Ny sak' }).click();
  await page.getByLabel('Tittel').fill(title);
  await page.getByLabel('Beskrivelse').fill('Syntetisk kontrollsak for lokal nettlesertest.');
  await page.getByRole('button', { name: 'Opprett sak' }).click();
  await expect(page.getByRole('heading', { name: title })).toBeVisible();
  const caseId = new URL(page.url()).pathname.split('/').at(-1);
  if (!caseId) throw new Error('The synthetic case identifier was unavailable.');

  const documentId = await page.evaluate(async (currentCaseId) => {
    const form = new FormData();
    form.set('case_id', currentCaseId);
    form.set(
      'email_text',
      'From: sender@example.invalid\n\nSyntetisk dokumenttekst for lokal nettlesertest. ' +
        'Kilden beskriver et syntetisk kontrollforhold og skal bare brukes i lokal validering. ' +
        'Det finnes ingen persondata eller produksjonsinnhold i denne teksten. ' +
        'Kildepakken trenger nok innhold til at den kontrollerte Evidence-flyten kan fullføres.',
    );
    form.set('title', 'E2E syntetisk dokument');
    form.set('source_status', 'approved');
    form.set('confidentiality_level', 'internal');
    const response = await fetch('/api/documents/upload', {
      body: form,
      credentials: 'include',
      method: 'POST',
    });
    if (!response.ok) throw new Error('Synthetic document setup failed.');
    return ((await response.json()) as { data: { document_id: string } }).data.document_id;
  }, caseId);
  await expect
    .poll(
      () =>
        page.evaluate(async (currentDocumentId) => {
          const response = await fetch(`/api/documents/${currentDocumentId}`, {
            credentials: 'include',
          });
          if (!response.ok) return 'unavailable';
          return ((await response.json()) as { data: { indexing_status: string } }).data
            .indexing_status;
        }, documentId),
      { timeout: 60_000 },
    )
    .toBe('indexed');
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Dokumenter' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'E2E syntetisk dokument' })).toBeVisible();
  await page.getByRole('button', { name: 'Se metadata' }).click();
  await expect(page.getByRole('button', { name: 'Be om reindeksering' })).toBeVisible();

  await page.getByLabel('Hva vil du finne i kildene?').fill('Syntetisk dokumenttekst');
  await page.getByLabel('Avgrens til dokument (valgfritt)').selectOption(documentId);
  await page.getByRole('button', { name: 'Søk i kilder' }).click();
  await expect(page.getByRole('heading', { name: 'Kilder' })).toBeVisible();
  await page.getByRole('button', { name: 'Åpne kildekontekst' }).first().click();
  const contextDialog = page.getByRole('dialog', { name: 'Avgrenset kildekontekst' });
  await expect(contextDialog).toBeVisible();
  await expect(
    contextDialog.getByText(/Syntetisk dokumenttekst for lokal nettlesertest\./),
  ).toBeVisible();
  await contextDialog.getByRole('button', { name: 'Lukk' }).click();

  await page.getByRole('button', { name: 'Bygg kildepakke' }).click();
  await expect(
    page.getByText(
      /Kildepakken er klar for videre vurdering\.|Det trengs mer kildegrunnlag før videre arbeid\./,
    ),
  ).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText('S1')).toBeVisible();

  await page.getByRole('button', { name: 'Start ekstraksjon' }).click();
  await expect(page.getByText('Ekstraksjon er klar for menneskelig kontroll.')).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByText('SYNTHETIC-1')).toBeVisible();
  await page.getByRole('button', { name: 'Rediger opplysning' }).click();
  const extractionEditor = page.getByLabel('Verdi (én opplysning per linje)');
  await extractionEditor.fill('SYNTHETIC-2');
  await page.getByRole('button', { name: 'Lagre endring' }).click();
  await expect(page.getByText('Redigert av menneske.')).toBeVisible();
  await expect(page.getByText('SYNTHETIC-2')).toBeVisible();

  await page.getByRole('button', { name: 'Be om reindeksering' }).click();
  await expect(page.getByText('Reindeksering er forespurt.')).toBeVisible();

  await page.getByRole('link', { name: 'Tilbake til saksinnboksen' }).click();
  await page.getByLabel('Søk i saker').fill(title);
  await page.getByRole('button', { name: 'Bruk filtre' }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get('q')).toBe(title);
  const result = page.getByRole('row', { name: new RegExp(title) });
  await expect(result).toBeVisible();
  await result.getByRole('link', { name: /^CASE-/ }).click();
  await expect(page.getByRole('heading', { name: title })).toBeVisible();
});
