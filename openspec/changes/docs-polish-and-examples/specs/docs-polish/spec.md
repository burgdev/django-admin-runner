## ADDED Requirements

### Requirement: Landing page hero section
The docs landing page (index.md) SHALL include a hero section at the top with the project name, a one-line tagline, and prominent call-to-action buttons linking to "Get Started" and "Examples".

#### Scenario: User lands on docs homepage
- **WHEN** a user visits the docs root URL
- **THEN** a hero section is displayed with the project name, tagline, and two CTA buttons

### Requirement: Card-based feature grid
The landing page SHALL display features in a responsive card grid layout instead of a plain bullet list. Each card SHALL show a feature title, brief description, and an icon.

#### Scenario: Features display as cards
- **WHEN** a user views the landing page features section
- **THEN** features are displayed as individual cards in a responsive grid (3 columns on desktop, 2 on tablet, 1 on mobile)

### Requirement: Custom CSS stylesheet
The docs SHALL include a custom CSS file at `docs/stylesheets/extra.css` that overrides default theme colors and adds custom component styles (hero, cards, etc.) using CSS custom properties.

#### Scenario: Custom colors are applied
- **WHEN** the docs site loads
- **THEN** the theme uses project-specific primary and accent colors rather than default indigo

### Requirement: Social card image
The docs configuration SHALL include an Open Graph social card image so that links shared on social media display a preview card with the project name, icon, and tagline.

#### Scenario: Docs link is shared on social media
- **WHEN** a docs URL is shared on a platform that supports Open Graph
- **THEN** a preview card is displayed showing the project icon, name, and description

### Requirement: Doc audit for accuracy
All existing documentation pages SHALL be reviewed and updated to reflect the current API surface — specifically verifying Python ≥3.12, Django ≥6.0, `set_result_html()`, hooks system, and rich output features are accurately documented.

#### Scenario: Installation page shows correct Python version
- **WHEN** a user reads the installation page
- **THEN** the requirements section shows "Python 3.12+" matching pyproject.toml's `requires-python`

#### Scenario: Rich output is documented
- **WHEN** a user reads the docs
- **THEN** `set_result_html()` and the rich traceback feature are documented in an appropriate section
