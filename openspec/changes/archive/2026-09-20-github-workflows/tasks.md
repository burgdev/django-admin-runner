## 1. Composite Setup Action

- [x] 1.1 Create `.github/actions/setup/action.yml` composite action (checkout + setup uv, with `python-version` input defaulting to 3.13)
- [x] 1.2 Update `quality.yml` to use the composite action
- [x] 1.3 Update `publish.yml` to use the composite action
- [x] 1.4 Verify `test.yml` remains unchanged (matrix makes composite action impractical)

## 2. New Version Workflow

- [x] 2.1 Create `.github/workflows/new-version.yml` that auto-tags after successful CI on main branch
- [x] 2.2 Verify tag-exists check and repository_dispatch trigger logic

## 3. Publish Workflow

- [x] 3.1 Update `.github/workflows/publish.yml` to use trusted publishing (OIDC) with `pypa/gh-action-pypi-publish`
- [x] 3.2 Add `repository_dispatch` trigger for `new-tag-created` events

## 4. Release Workflow

- [x] 4.1 Create `.github/workflows/release.yml` that creates GitHub releases with git-cliff changelog
- [x] 4.2 Add `repository_dispatch` trigger for `new-tag-created` events

## 5. Documentation Deployment

- [x] 5.1 Create `.github/workflows/docu.yml` that deploys MkDocs to gh-pages
- [x] 5.2 Add `repository_dispatch` trigger for `new-tag-created` events
