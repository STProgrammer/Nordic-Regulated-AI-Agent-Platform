import js from '@eslint/js';
import nextPlugin from '@next/eslint-plugin-next';
import tseslint from 'typescript-eslint';

const nextRules = Object.fromEntries(
  Object.entries(nextPlugin.configs.recommended.rules).map(([rule]) => [rule, 'error']),
);

export default tseslint.config(
  {
    ignores: [
      '**/node_modules/**',
      '**/.venv/**',
      '**/.next/**',
      '**/.turbo/**',
      '**/build/**',
      '**/coverage/**',
      '**/dist/**',
      '**/.mypy_cache/**',
      '**/.ruff_cache/**',
      'apps/web/next-env.d.ts',
    ],
  },
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    files: ['**/*.{js,mjs,cjs,ts,tsx,mts,cts}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
    },
  },
  {
    files: ['apps/web/**', 'eslint.config.mjs'],
    plugins: {
      '@next/next': nextPlugin,
    },
    rules: {
      ...nextRules,
      ...nextPlugin.configs['core-web-vitals'].rules,
      '@next/next/no-html-link-for-pages': 'off',
    },
  },
);
