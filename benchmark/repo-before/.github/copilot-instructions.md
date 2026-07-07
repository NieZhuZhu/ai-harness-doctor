# GitHub Copilot instructions

Use Node 16 for all local development.
Install dependencies with `npm install`.
Tests use Jest.
Run the unit tests with `npm run test:unit`.
Run coverage with `jest --coverage`.
Format JavaScript with `eslint --fix`.
Use double quotes and 4-space indentation.
Put tests in `__tests__/` directories.
Treat the app as CommonJS and run development with `npm start`.
CI is configured in `.circleci/config.yml`.
React components live in `src/ui/`.
Utility helpers live in `src/utils/`.
Keep functions small and readable.
Do not commit generated build output.
Ask before changing dependency versions.
Keep changes scoped to the task.
