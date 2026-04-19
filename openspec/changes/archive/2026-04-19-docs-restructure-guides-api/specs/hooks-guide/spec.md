## ADDED Requirements

### Requirement: Dedicated hooks guide page
The documentation SHALL include a standalone `docs/hooks.md` guide page that documents the hooks system including TempFileHook, custom hook creation, hook lifecycle, and settings.

#### Scenario: Hooks guide accessible from navigation
- **WHEN** a user views the Guides section in the site navigation
- **THEN** a "Hooks" entry appears after "Execution Context" linking to the hooks guide

#### Scenario: Hooks guide covers all hook topics
- **WHEN** a user reads the hooks guide
- **THEN** the page documents TempFileHook, custom hook creation with code examples, the hook lifecycle table (setup/pre_save/post_save), HookContext, and the ADMIN_RUNNER_HOOKS setting

### Requirement: Hooks guide placed after execution context in nav
The hooks guide SHALL appear in the Guides nav section immediately after the execution context page.

#### Scenario: Navigation ordering
- **WHEN** the Guides nav section is rendered
- **THEN** hooks.md appears directly after execution-context.md in the section listing
