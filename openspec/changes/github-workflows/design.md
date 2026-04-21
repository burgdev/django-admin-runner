## Context

django-admin-runner currently has three separate GitHub Actions workflows: `quality.yml`, `test.yml`, and `publish.yml`. These were created as minimal CI and lack the automated release pipeline established in immichporter. The project already has `git-cliff` configured (cliff.toml), `mkdocs` configured (mkdocs.yml), and a `just` task runner with `project version`, `changelog`, and `docs` commands available.

The immichporter repo has a mature workflow setup with:
- Composite setup action (`.github/actions/setup-venv`)
- Consolidated main CI (`main.yml`)
- Auto-tagging on CI success (`new-version.yml`)
- GitHub releases with changelog (`release.yml`)
- Documentation deployment (`docu.yml`)
- Trusted PyPI publishing (`publish-pypi.yml`)

## Goals / Non-Goals

**Goals:**
- Add the missing release automation pipeline: tag → publish + release + docs
- Use trusted publishing (OIDC) instead of token-based PyPI auth
- Deduplicate environment setup via composite action
- Add documentation build and deployment
- Keep existing quality.yml and test.yml workflows as-is

**Non-Goals:**
- Consolidating or replacing existing quality.yml and test.yml
- Changing source code or package configuration
- Modifying existing `just` tasks or `cliff.toml`
- Supporting matrix Python versions beyond what's already configured (3.12, 3.13)

## Decisions

### 1. Composite setup action pattern
Create `.github/actions/setup` composite action (renamed from `setup-venv` since uv manages the venv automatically). This bundles `actions/checkout@v4` + `astral-sh/setup-uv@v4` into a single reusable step. It accepts a `python-version` input (defaulting to `3.13`). The `uv sync` step is NOT included in the composite action since different workflows need different dependency groups (e.g., `--group dev --group test --all-extras` vs `--all-groups --all-extras` vs just build deps for publish).

Note: `test.yml` uses a Python matrix (3.12, 3.13) and will NOT use the composite action — the matrix makes the composite action impractical there. It keeps its inline setup steps.

### 2. Update existing workflows to use composite action where practical
Update `quality.yml` and `publish.yml` to use the composite `.github/actions/setup` action. Keep `test.yml` as-is with its inline setup because of the Python version matrix.

### 3. new-version.yml with repository_dispatch chain
After successful main.yml run on `main` branch, check if the current version in pyproject.toml has a corresponding git tag. If not, create and push the tag, then dispatch events to trigger publish, release, and docu workflows. This creates the automation: bump version in pyproject.toml → merge to main → everything else is automatic.

### 4. Trusted publishing for PyPI
Switch from `UV_PUBLISH_TOKEN` to `pypa/gh-action-pypi-publish` with OIDC. Requires configuring trusted publishing on PyPI side.

### 5. Release workflow uses git-cliff
The `just changelog` command (which runs git-cliff) generates release notes. The release workflow calls this and creates a GitHub release via `softprops/action-gh-release`.

### 6. Docu workflow builds and deploys to gh-pages
Uses `mkdocs gh-deploy --force` to push to `gh-pages` branch, consistent with immichporter.

## Risks / Trade-offs

- **[Trusted publishing setup]** → Requires one-time PyPI configuration. Mitigation: document the setup steps in the PR.
- **[Tag automation race condition]** → If multiple merges happen quickly, tags could conflict. Mitigation: the tag-exists check prevents duplicates.
- **[gh-pages branch]** → Must be created and GitHub Pages configured to serve from it. Mitigation: one-time setup, documented.
