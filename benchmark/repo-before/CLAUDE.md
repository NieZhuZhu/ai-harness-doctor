# Claude Code guidance

This file contains project instructions for Claude Code contributors.

## Project setup

- Use Node 16 for all local development.
- Install dependencies with `npm install`.
- The repository is a small React application.
- The project is CommonJS; do not add ESM-only configuration.
- Start the dev server with `npm start`.
- Always read this file before touching code.

## Test workflow

- Tests use Jest.
- Run the unit tests with `npm run test:unit`.
- Run coverage with `jest --coverage`.
- Tests live in a top-level `__tests__/` directory.
- Add Jest tests near the component being changed.
- Use snapshots when they make review easier.

## Build workflow

- Run `npm run build` before opening a pull request.
- Run type checks after the build when changing TypeScript.
- Keep CI green before requesting review.

## Source layout

- React components live in `src/ui/`.
- Utility helpers live in `src/utils/`.
- Place reusable hooks in `src/hooks/`.
- Avoid creating new top-level directories without approval.

## Coding rules

- Prefer TypeScript for all source files.
- Use double quotes in TypeScript and JSX.
- Use 4 spaces for indentation.
- Format changed files with `eslint --fix`.
- Keep functions small and readable.
- Avoid broad refactors in feature branches.
- Prefer explicit names over abbreviations.
- Handle loading and error states in UI work.
- Keep comments focused on surprising behavior.

## Review rules

- Explain user-visible behavior in the PR description.
- Include screenshots for visual changes.
- Mention any manual testing performed.
- Do not commit generated build output.
- Ask before changing dependency versions.
- Keep changes scoped to the task.
