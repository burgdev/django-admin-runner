## ADDED Requirements

### Requirement: Composite setup action
The system SHALL provide a composite action at `.github/actions/setup` that checks out code and sets up uv with a configurable Python version.

#### Scenario: Setup action used by workflow
- **WHEN** a workflow step uses `uses: ./.github/actions/setup`
- **THEN** the runner has the code checked out, uv installed, and Python available

#### Scenario: Setup action with custom Python version
- **WHEN** a workflow step uses `uses: ./.github/actions/setup` with `python-version: "3.12"`
- **THEN** Python 3.12 is configured via uv

### Requirement: Existing CI workflows updated for composite action
The `quality.yml` and `publish.yml` workflows SHALL use the composite setup action. The `test.yml` workflow SHALL remain unchanged (matrix Python versions prevent composite action usage).

#### Scenario: Quality workflow uses composite action
- **WHEN** the quality workflow runs
- **THEN** it uses `./.github/actions/setup` instead of inline checkout + uv setup steps

#### Scenario: Test workflow unchanged
- **WHEN** code is pushed or a PR is opened
- **THEN** the test workflow runs pytest on Python 3.12 and 3.13 matrix as before, with inline setup steps
