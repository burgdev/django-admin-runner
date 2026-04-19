## Why

The documentation is functional but lacks polish, personality, and real-world examples. The landing page is bare, there's no project icon/branding, no dedicated examples section, and the docs site could benefit from the modern Zensical toolchain (the Material for MkDocs successor by the same creators). This change brings the docs up to a polished, publication-ready state.

## What Changes

- **Doc audit & fixes**: Verify all docs reflect current API (Python ≥3.12, Django ≥6.0, `set_result_html()`, hooks, rich output), fix any outdated references
- **Examples section**: Add a dedicated docs page showcasing all three example projects (classic, unfold_celery, unfold_rq) with screenshots descriptions, setup steps, and what each demonstrates
- **Project icon (SVG)**: Create a clean, memorable SVG icon that works at small sizes (favicon, nav, social card) — conveying "admin + command runner"
- **Custom docu touch**: Add a hero section on the landing page, custom CSS (accent colors, card-based feature grid), social card image, and a "why django-admin-runner?" pitch
- **Zensical port**: Evaluate and port the docs build from mkdocs-material to Zensical (compatible successor by Material's creators, uses same mkdocs.yml). This is a build-tool swap — content stays Markdown

## Capabilities

### New Capabilities
- `docs-examples-page`: Dedicated examples page documenting all three example projects with setup, architecture, and key takeaways
- `project-icon`: SVG project icon/logo suitable for favicon, docs nav, and social cards
- `docs-polish`: Landing page hero, custom CSS styling, social cards, and overall personality/branding for the docs site
- `zensical-migration`: Port the docs build from mkdocs + mkdocs-material to Zensical CLI

### Modified Capabilities
<!-- No existing spec-level behavior changes — this is purely documentation and build tooling -->

## Impact

- **docs/**: New pages, updated landing page, new assets (SVG, CSS, social images)
- **mkdocs.yml**: Potential rename to zensical config or config adjustments for Zensical compatibility
- **pyproject.toml**: Docs dependency group may change (mkdocs-material → zensical)
- **README.md**: May add icon reference, update docs badge URL
- **Justfile**: `just docs` command may need updating for `zensical build`/`zensical serve`
