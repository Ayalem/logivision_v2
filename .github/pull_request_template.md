<!-- Thanks for opening a PR. Keep the summary short — let the code speak. -->

## What

<!-- One or two sentences. What changes and why. Link the sprint/task ID if applicable (e.g. T1.1.1). -->

## Why

<!-- The motivation. Link issues, ADRs, runbooks, MLflow runs, screenshots. -->

## How to test

<!-- Concrete commands or steps a reviewer can run. -->

## Definition of Done

- [ ] Tests added / updated; coverage maintained.
- [ ] `make lint` passes locally.
- [ ] `make test` passes locally.
- [ ] Docs updated (README, docstrings, ADR if architectural, runbook if operational).
- [ ] New services expose `/health`, `/metrics`, and emit structured JSON logs.
- [ ] No secret committed; pre-commit suite green.
- [ ] Trivy scan: `CRITICAL=0`, `HIGH<5` (where applicable).
- [ ] Screenshot / GIF attached for any UI change.
- [ ] `docs/PROGRESS.md` updated.

## Notes for reviewer

<!-- Risk areas, follow-ups, anything that does not fit above. -->
