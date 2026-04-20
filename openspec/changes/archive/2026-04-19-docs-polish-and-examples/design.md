## Context

The django-admin-runner package has solid documentation built with MkDocs + Material theme, covering core features like the decorator, runners, widgets, and admin themes. However, it lacks:

1. **Polish & personality**: The landing page is a plain feature list with no visual identity
2. **Examples page**: Three full example projects exist in `examples/` but aren't showcased in docs
3. **Branding**: No icon/logo exists — the project relies on generic Material theme defaults
4. **Modern tooling**: Zensical (by Material's creators) is a drop-in replacement that consolidates MkDocs + Material into one stack

The docs are deployed to `burgdev.github.io/django-admin-runner` via GitHub Pages.

## Goals / Non-Goals

**Goals:**
- Audit and fix any doc inaccuracies against current source code
- Create a memorable SVG icon for the project
- Add a rich examples page documenting all three example projects
- Give the docs a custom identity (hero section, feature cards, social card)
- Evaluate and implement Zensical as the docs build tool

**Non-Goals:**
- Rewriting API reference content that's already accurate
- Adding new package features (this is docs-only)
- Changing the package's Python API or behavior
- Multi-language documentation

## Decisions

### 1. SVG Icon Design

**Decision**: Create a minimal SVG icon combining a terminal prompt (`>_`) with a Django-style shield/admin motif.

**Rationale**: The icon needs to convey "commands" (terminal) + "admin" (shield/panel) at 16px–128px. A simple geometric design with 2–3 colors works best. Using inline SVG in the docs and a PNG fallback for favicon.

**Alternative considered**: Running figure / gear icon — too generic, doesn't convey the specific value proposition.

### 2. Examples Page Structure

**Decision**: Single page with tabbed sections per example project (classic / unfold-celery / unfold-rq), each showing: overview, architecture diagram (mermaid), setup steps, and key code snippets.

**Rationale**: MkDocs Material's content tabs (`pymdownx.tabbed`) already handle this perfectly. A single page is easier to maintain than three separate pages, and tabs let users compare approaches.

### 3. Landing Page Customization

**Decision**: Use Material's `custom_dir` template overrides + custom CSS to add a hero section with the icon, a tagline, and a card-based feature grid. Add `overrides/main.html` extending the base.

**Rationale**: Template overrides are the standard Material/Zensical customization path. Keeps changes maintainable and upgrade-safe.

### 4. Zensical Migration

**Decision**: Port to Zensical as the build tool, keeping `mkdocs.yml` as config (Zensical is compatible). Replace `mkdocs-material` dep with `zensical` in pyproject.toml. Update `just docs` to use `zensical serve` / `zensical build`.

**Rationale**: Zensical is built by the Material for MkDocs creators, guarantees compatibility with existing `mkdocs.yml`, and consolidates MkDocs + Material into one tool. Since it's still in alpha (v0.0.32), we'll add a fallback note but proceed — the compatibility guarantee means this is low-risk.

**Alternative considered**: Stay on mkdocs-material — valid but misses the opportunity to adopt the successor toolchain early.

### 5. Custom CSS Approach

**Decision**: Add `docs/stylesheets/extra.css` with CSS custom properties overriding Material/Zensical variables. Use CSS Grid for the feature cards on the landing page.

**Rationale**: CSS custom properties are the supported theming mechanism. Grid gives responsive cards without JavaScript.

## Risks / Trade-offs

- **[Zensical alpha stability]** → Mitigation: Zensical guarantees Material compat; if it breaks, reverting is just swapping the dep back to mkdocs-material
- **[Icon design subjectivity]** → Mitigation: Keep it minimal and functional; it can be iterated on
- **[Custom template overrides may break on theme upgrades]** → Mitigation: Use minimal overrides, rely on CSS custom properties first
