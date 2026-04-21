## ADDED Requirements

### Requirement: Automatic version tagging
The system SHALL provide a `new-version.yml` workflow that runs after successful completion of the Main workflow on the main branch, checks if the current version in pyproject.toml has a corresponding `v*` git tag, and creates/pushes the tag if it doesn't exist.

#### Scenario: New version detected
- **WHEN** the Main workflow completes successfully on main branch
- **AND** the version in pyproject.toml (e.g., "0.2.0") does not have a corresponding tag ("v0.2.0")
- **THEN** the tag is created and pushed to origin

#### Scenario: Version already tagged
- **WHEN** the Main workflow completes successfully on main branch
- **AND** the version in pyproject.toml already has a corresponding tag
- **THEN** no tag is created and the workflow exits silently

#### Scenario: Tag creation triggers downstream workflows
- **WHEN** a new tag is created by new-version.yml
- **THEN** a `repository_dispatch` event with type `new-tag-created` is sent to trigger publish, release, and docu workflows

### Requirement: PyPI trusted publishing
The system SHALL publish packages to PyPI using OIDC trusted publishing when a version tag is pushed or when triggered by repository_dispatch.

#### Scenario: Publish on tag push
- **WHEN** a tag matching `v*.*.*` is pushed
- **THEN** the package is built and published to PyPI using trusted publishing (OIDC)

#### Scenario: Publish on repository dispatch
- **WHEN** a `new-tag-created` repository_dispatch event is received
- **THEN** the package is built and published to PyPI using trusted publishing (OIDC)

### Requirement: GitHub release creation
The system SHALL create a GitHub release with git-cliff generated changelog when a version tag is pushed or when triggered by repository_dispatch.

#### Scenario: Release created with changelog
- **WHEN** a tag matching `v*.*.*` is pushed or a `new-tag-created` dispatch is received
- **THEN** a GitHub release is created with the version name and git-cliff changelog body

### Requirement: Documentation deployment
The system SHALL deploy MkDocs documentation to GitHub Pages when a version tag is pushed or when triggered by repository_dispatch.

#### Scenario: Docs deployed on release
- **WHEN** a tag matching `v*.*.*` is pushed or a `new-tag-created` dispatch is received
- **THEN** `mkdocs gh-deploy --force` runs and documentation is published to the gh-pages branch
