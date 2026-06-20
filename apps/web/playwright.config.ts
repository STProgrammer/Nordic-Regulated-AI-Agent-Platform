import { defineConfig } from '@playwright/test';

export default defineConfig({
  forbidOnly: Boolean(process.env.CI),
  outputDir: 'test-results',
  testDir: './e2e',
  timeout: 30_000,
  use: {
    baseURL: process.env.NORDIC_E2E_BASE_URL ?? 'http://127.0.0.1:3000',
    screenshot: 'off',
    trace: 'off',
    video: 'off',
  },
});
