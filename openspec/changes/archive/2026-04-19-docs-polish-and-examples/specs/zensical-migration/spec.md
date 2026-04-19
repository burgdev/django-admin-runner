## ADDED Requirements

### Requirement: Zensical as build tool
The project SHALL use Zensical CLI (`zensical`) instead of `mkdocs` for building and serving documentation. The existing `mkdocs.yml` SHALL be used as the configuration file without format changes.

#### Scenario: Building docs with Zensical
- **WHEN** a developer runs the docs build command
- **THEN** `zensical build` is executed and produces the static site in the configured `site_dir`

#### Scenario: Serving docs locally
- **WHEN** a developer runs the local docs server command
- **THEN** `zensical serve` starts a local preview server

### Requirement: Updated dependency configuration
The `pyproject.toml` docs dependency group SHALL replace `mkdocs` and `mkdocs-material` with `zensical`. Other docs plugins (mkdocstrings, literate-nav, etc.) SHALL be kept if compatible with Zensical.

#### Scenario: Docs dependencies install correctly
- **WHEN** a developer installs the docs dependency group
- **THEN** `zensical` and compatible plugins are installed without conflicts

### Requirement: Updated task runner commands
The Justfile docs task SHALL use `zensical build` and `zensical serve` instead of `mkdocs build` and `mkdocs serve`.

#### Scenario: Just docs command works
- **WHEN** a developer runs `just docs`
- **THEN** Zensical serves the docs locally with live reload

### Requirement: Zensical compatibility verified
The documentation site SHALL build successfully with Zensical and produce output visually equivalent to the current mkdocs-material build. All plugins and extensions in use SHALL be verified compatible.

#### Scenario: Full build succeeds
- **WHEN** `zensical build` is run
- **THEN** the build completes without errors and the generated site has the same content, navigation, and features as before

#### Scenario: Plugin compatibility confirmed
- **WHEN** the docs are built with Zensical
- **THEN** mkdocstrings API docs, literate-nav navigation, and all markdown extensions render correctly
