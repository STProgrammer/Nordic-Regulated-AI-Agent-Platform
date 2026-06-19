import js from '@eslint/js';
import tseslint from 'typescript-eslint';

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
);
