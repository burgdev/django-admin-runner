## Context

The docs site (built with MkDocs Material) currently returns a 404 at the root URL because:

1. **No `docs/index.md`** — MkDocs requires an `index.md` to serve the site root. Currently the landing page content lives in `docs/getting-started/index.md` which is a nested section page, not the site root.

2. **`literate-nav` plugin reads `docs/SUMMARY.md`** — The plugin is configured with `nav_file: SUMMARY.md` but that file doesn't exist. When `literate-nav` is active, it overrides the `nav` section in `mkdocs.yml`. Without `SUMMARY.md`, the navigation is empty/broken.

3. The `mkdocs.yml` has both a `nav` section AND the `literate-nav` plugin, which creates a conflict — `literate-nav` takes precedence.

## Goals / Non-Goals

**Goals:**
- Site root (`/`) renders a proper landing page instead of 404
- Navigation tabs (Getting Started, Guides, API Reference, etc.) work correctly
- Minimal changes — reuse existing content and structure

**Non-Goals:**
- Redesigning the docs structure or content
- Changing the theme or styling
- Removing the `literate-nav` plugin (it's useful for maintainability)

## Decisions

### Decision 1: Create `docs/SUMMARY.md` to fix navigation

Create `docs/SUMMARY.md` with the same navigation structure currently in `mkdocs.yml`'s `nav` section. This gives `literate-nav` what it needs and removes the conflict.

**Why:** The `literate-nav` plugin is already configured and provides a markdown-based way to manage navigation. Keeping it and providing the file it needs is simpler than removing the plugin and relying solely on `mkdocs.yml`'s `nav` section.

**Alternative considered:** Remove `literate-nav` plugin and rely on the `nav` section in `mkdocs.yml`. Rejected because the plugin is already installed and working with SUMMARY.md is a common MkDocs pattern.

### Decision 2: Create `docs/index.md` that redirects to Getting Started

Create a minimal `docs/index.md` that either contains the landing page content directly or uses MkDocs Material's `navigation.indexes` feature to serve the getting-started index as the home page.

**Why:** The `navigation.indexes` feature is already enabled in the theme config, and the `getting-started/index.md` already has rich landing page content. The simplest fix is to create a root `index.md` that uses the existing content.

**Approach:** Since `docs/getting-started/index.md` already has a well-designed hero section with feature cards and quick navigation, create `docs/index.md` with similar but more concise content that serves as the true site root, pointing to Getting Started as the main entry.

## Risks / Trade-offs

- **Duplicate content risk**: If `docs/index.md` mirrors `getting-started/index.md` too closely, updates need to be made in two places. → Mitigation: Make `docs/index.md` a concise redirect-style page that points to getting-started, rather than duplicating the full hero content.
- **literate-nav precedence**: The `nav` section in `mkdocs.yml` becomes dead config when `SUMMARY.md` exists. → Mitigation: Document this in `SUMMARY.md` header comment so future editors know where to update navigation.
