## ADDED Requirements

### Requirement: SVG project icon
The project SHALL have an SVG icon file at `docs/assets/icon.svg` that represents the concept of "running Django admin commands". The icon SHALL be clean, minimal, and work at sizes from 16x16 to 128x128 pixels.

#### Scenario: Icon renders at favicon size
- **WHEN** the SVG icon is rendered at 16x16 pixels
- **THEN** the icon is recognizable and not visually cluttered

#### Scenario: Icon renders at docs nav size
- **WHEN** the SVG icon is rendered at 48x48 pixels in the docs navigation
- **THEN** the icon clearly represents a terminal/command concept with admin context

### Requirement: Icon integrated into docs site
The mkdocs.yml configuration SHALL reference the icon as the site favicon and logo.

#### Scenario: Docs site shows the icon as favicon
- **WHEN** a user opens the docs site in a browser
- **THEN** the browser tab shows the project icon as the favicon

#### Scenario: Docs site shows the icon in navigation
- **WHEN** a user views the docs site
- **THEN** the icon appears in the top-left navigation area as the site logo

### Requirement: PNG fallback for favicon
The project SHALL include a PNG version of the icon at `docs/assets/icon.png` for browsers that don't support SVG favicons.

#### Scenario: Browser requests PNG favicon
- **WHEN** a browser that doesn't support SVG favicons loads the docs
- **THEN** a PNG favicon is served as fallback
