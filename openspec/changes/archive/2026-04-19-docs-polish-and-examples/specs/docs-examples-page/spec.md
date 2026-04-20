## ADDED Requirements

### Requirement: Examples page with tabbed sections
The documentation SHALL include a dedicated "Examples" page accessible from the main navigation. The page SHALL use content tabs to organize three example projects: Classic, Unfold + Celery, and Unfold + RQ.

#### Scenario: User navigates to examples page
- **WHEN** a user clicks "Examples" in the docs navigation
- **THEN** the examples page is displayed with three tabbed sections, one per example project

### Requirement: Each example section documents setup and architecture
Each example tab SHALL include: a brief overview of what the example demonstrates, an architecture diagram (mermaid), step-by-step setup instructions (clone, install, run), and key code snippets highlighting the example's focus area.

#### Scenario: User views the Classic example tab
- **WHEN** the Classic tab is selected
- **THEN** the page shows: overview (synchronous execution with ImmediateBackend), setup steps using `make init` and `make run`, and code showing `@register_command` with basic arguments

#### Scenario: User views the Unfold + Celery example tab
- **WHEN** the Unfold + Celery tab is selected
- **THEN** the page shows: overview (async Celery execution with Unfold theme), setup steps including Docker for Valkey and Celery worker, and code showing `FileOrPathField` and `ADMIN_RUNNER_BACKEND = "celery"`

#### Scenario: User views the Unfold + RQ example tab
- **WHEN** the Unfold + RQ tab is selected
- **THEN** the page shows: overview (custom runner implementation), setup steps including Docker for Valkey and RQ worker, and code showing `RqCommandRunner` subclassing `BaseCommandRunner`

### Requirement: Examples page is linked from landing page
The docs landing page (index.md) SHALL include a link to the examples page in the quick navigation section.

#### Scenario: User finds examples from landing page
- **WHEN** a user views the docs landing page
- **THEN** an "Examples" link is visible in the quick navigation area pointing to the examples page
