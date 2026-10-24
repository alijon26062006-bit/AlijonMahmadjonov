// Проверка кода всех трёх приложений: npx eslint .
// Только правила, которые ловят настоящие ошибки (код не выполнится, выполнится не так, мёртвый код).
// Имена переменных и модули проверяет TypeScript (npx tsc), стиль — не здесь.
const rules = {
      'no-unused-vars': ['error', { args: 'none', caughtErrors: 'none', ignoreRestSiblings: true }],
      'no-dupe-keys': 'error', 'no-duplicate-case': 'error', 'no-dupe-else-if': 'error', 'no-dupe-args': 'error',
      'no-unreachable': 'error', 'no-fallthrough': 'error', 'no-unsafe-finally': 'error', 'no-unsafe-optional-chaining': 'error',
      'no-self-compare': 'error', 'no-self-assign': 'error', 'no-constant-condition': ['error', { checkLoops: false }], 'no-constant-binary-expression': 'error',
      'no-cond-assign': ['error', 'except-parens'], 'use-isnan': 'error', 'valid-typeof': 'error', 'no-compare-neg-zero': 'error',
      'no-sparse-arrays': 'error', 'no-loss-of-precision': 'error', 'no-empty': ['error', { allowEmptyCatch: false }],
      'no-func-assign': 'error', 'no-import-assign': 'error', 'no-redeclare': 'error', 'no-shadow-restricted-names': 'error',
      'no-useless-catch': 'error', 'no-async-promise-executor': 'error',
      'no-unmodified-loop-condition': 'error', 'no-unused-private-class-members': 'error', 'eqeqeq': ['error', 'smart'],
      'no-var': 'error', 'prefer-const': ['error', { destructuring: 'all' }],
};
export default [
  { ignores: ['**/vendor/**', 'node_modules/**', 'e2e/report/**'] },
  { linterOptions: { reportUnusedDisableDirectives: 'error' } },
  // приложения — модули в браузере
  { files: ['seller/js/**/*.js', 'client/js/**/*.js', 'courier/js/**/*.js'], languageOptions: { ecmaVersion: 2023, sourceType: 'module' }, rules },
  // service worker и подмена базы в тестах — обычные скрипты
  { files: ['*/sw.js', 'e2e/**/*.js'], languageOptions: { ecmaVersion: 2023, sourceType: 'script' }, rules },
  // тесты — Node.js
  { files: ['e2e/**/*.cjs'], languageOptions: { ecmaVersion: 2023, sourceType: 'commonjs' }, rules },
];
