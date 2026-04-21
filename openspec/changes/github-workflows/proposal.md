## Why

The project currently has basic CI (quality, tests, publish) but lacks the automated release pipeline that immichporter has. There is no documentation deployment, no automatic version tagging after successful CI, and no GitHub release creation with changelog. The publish workflow uses token-based auth instead of trusted publishing. Setup steps (checkout + uv) are duplicated across workflows.

## What Changes

- Add a composite `.github/actions/setup` action to deduplicate checkout + uv setup across workflows
- Update existing workflows (`quality.yml`, `publish.yml`) to use the composite action
- Keep `test.yml` as-is (matrix Python versions make composite action impractical)
- Add `new-version.yml` workflow that auto-tags after successful CI runs
- Add `docu.yml` workflow to build and deploy MkDocs documentation to GitHub Pages
- Add `release.yml` workflow to create GitHub releases with git-cliff changelog
- Update `publish.yml` to use trusted publishing (PyPI OIDC) instead of token-based auth
- Trigger publish, release, and docu workflows both on tag push and via `repository_dispatch` from new-version

## Capabilities

### New Capabilities
- `github-ci`: Add composite setup action, update existing workflows to use it, and add doc build verification
- `github-release-automation`: Automated version tagging, GitHub release creation, and documentation deployment

### Modified Capabilities

## Impact

- `.github/workflows/`: Existing quality.yml and test.yml kept; publish.yml updated; new workflows added
- `.github/actions/setup-venv/`: New composite action
- No source code changes required
- Requires configuring GitHub Pages to deploy from `gh-pages` branch
- Requires configuring PyPI trusted publishing for the repository
