import js from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';

export default [
  { ignores: ['dist', 'coverage', 'node_modules'] },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
      // Páginas e componentes nunca chamam fetch: o único ponto de acesso à API é services/api.js.
      'no-restricted-globals': [
        'error',
        { name: 'fetch', message: 'Use services/api.js para acessar a API.' },
      ],
    },
  },
  {
    files: ['src/services/api.js', 'tests/**/*.{js,jsx}'],
    rules: { 'no-restricted-globals': 'off' },
  },
  {
    files: ['tests/**/*.{js,jsx}'],
    languageOptions: { globals: { ...globals.vitest } },
  },
];
