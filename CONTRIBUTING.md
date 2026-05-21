# Contributing to LOGIVISION

The authoritative plan is in [`PROJECT_PLAN.md`](PROJECT_PLAN.md). This document covers the day-to-day workflow.

## Branching model — single-branch on `main`

Single-branch workflow (decision made 2026-05-20 when collapsing the prior gitflow).

| Branch | Purpose |
|---|---|
| `main` | The one and only long-lived branch. All work lands here. |
| `feature/*` / `fix/*` / `chore/*` | **Short-lived**, optional. Use only when a collaborator opens a PR. Solo contributors commit straight to `main`. |

**For collaborators** (not the repo owner): never push directly to `main`. Open a PR from a short-lived branch, await review, then squash-merge. The owner enforces this with branch protection rules (require PR + 1 approval, disallow force-pushes, disallow deletions).

**For the repo owner**: commit and push straight to `main`. Keep commits Conventional and atomic — every commit on `main` is shippable.

## Commit messages — Conventional Commits

Format: `<type>(<scope>): <summary>`

Allowed types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `revert`.

Examples:
- `feat(api): add detection history endpoint`
- `fix(inference): handle empty frames`
- `chore(deps): bump ultralytics to 8.3.40`
- `docs(mlops): add training guide`

The `commit-msg` pre-commit hook enforces this.

## Development environment

```bash
make install              # uv sync dev deps
make pre-commit-install   # install Git hooks
make lint                 # ruff + mypy
make test                 # pytest
make format               # auto-fix
```

All Python code targets Python **3.11**. Service code is `mypy --strict`; ML scripts/notebooks are more permissive (see `pyproject.toml`).

## Pull request checklist (when a PR is opened)

The template (`.github/pull_request_template.md`) is required. In short:
- [ ] Tests added / updated, coverage maintained.
- [ ] Documentation updated (README, docstrings, ADR if architectural decision, runbook if new operational scenario).
- [ ] New services expose `/health` and `/metrics`, log JSON.
- [ ] No secret in clear; Trivy scan: `CRITICAL=0`, `HIGH<5`.
- [ ] Screenshot / GIF if UI-visible change.
- [ ] `docs/PROGRESS.md` updated.

## Branch protection settings (recommended)

Apply at `https://github.com/Ayalem/logivision_v2/settings/branches` with pattern `main`:
- Require a pull request before merging  (collaborators only)
- Require approvals: 1
- Dismiss stale approvals when new commits are pushed
- Require linear history
- **Allow force pushes**: NO
- **Allow deletions**: NO
- Do not allow bypassing the above settings: leave OFF for the owner during active development; turn ON once a collaborator joins.

## CI / CD

Repo is **public** → GitHub Actions minutes are **unlimited** for public repos. Use them: lint, type-check, test, build, scan on every PR. See `.github/workflows/` (added per Phase 5).

## Architecture decisions

Significant decisions go in `docs/architecture/adr/NNNN-title.md` (MADR format). Numbering starts at `0001` and increments. Each ADR is referenced by the PR that introduces the decision.

## Secrets

Never commit secrets. The pre-commit suite runs `detect-secrets` and `gitleaks`. Local config goes in `.env` (gitignored). Staging / prod use Sealed Secrets (see Phase 5).
