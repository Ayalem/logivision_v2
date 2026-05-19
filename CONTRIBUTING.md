# Contributing to LOGIVISION

The authoritative plan is in [`CLAUDE.md`](CLAUDE.md). This document covers the day-to-day workflow.

## Branching model — simplified Gitflow

| Branch | Purpose | Protected? |
|---|---|---|
| `main` | Production. Tagged releases. | Yes — PR only, CI green. |
| `develop` | Staging / integration. | Yes — PR only, CI green. |
| `feature/<short>` | New feature. Branch from `develop`. | No |
| `fix/<short>` | Bug fix. Branch from `develop`. | No |
| `chore/<short>` | Tooling, docs, refactor. Branch from `develop`. | No |
| `hotfix/<short>` | Urgent production fix. Branch from `main`. | No |
| `release/v*` | Release preparation. Branch from `develop`, merged to `main` + `develop`. | No |

Never commit directly to `main` or `develop`. Always open a PR.

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

## Pull request checklist

The template (`.github/pull_request_template.md`) is required. In short:
- [ ] Tests added / updated, coverage maintained.
- [ ] Documentation updated (README, docstrings, ADR if architectural decision, runbook if new operational scenario).
- [ ] New services expose `/health` and `/metrics`, log JSON.
- [ ] No secret in clear; Trivy scan: `CRITICAL=0`, `HIGH<5`.
- [ ] Screenshot / GIF if UI-visible change.
- [ ] `docs/PROGRESS.md` updated.

## CI / CD

Repo is **public** → GitHub Actions minutes are **unlimited** for public repos. Use them: lint, type-check, test, build, scan on every PR. See `.github/workflows/` (added per Phase 5).

## Architecture decisions

Significant decisions go in `docs/architecture/adr/NNNN-title.md` (MADR format). Numbering starts at `0001` and increments. Each ADR is referenced by the PR that introduces the decision.

## Secrets

Never commit secrets. The pre-commit suite runs `detect-secrets` and `gitleaks`. Local config goes in `.env` (gitignored). Staging / prod use Sealed Secrets (see Phase 5).
