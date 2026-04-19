## 1. Doc Audit & Fixes

- [x] 1.1 Audit installation.md: verify Python ≥3.12 and Django ≥6.0 requirements match pyproject.toml
- [x] 1.2 Audit all doc pages for API accuracy (set_result_html, hooks, rich output, context)
- [x] 1.3 Fix any outdated code examples, broken links, or inconsistencies found during audit

## 2. Project Icon (SVG)

- [x] 2.1 Create SVG icon at docs/assets/icon.svg — minimal design combining terminal prompt + admin motif, works at 16–128px
- [x] 2.2 Generate PNG fallback at docs/assets/icon.png from the SVG
- [x] 2.3 Update mkdocs.yml: set `theme.icon` / `theme.logo` / `site_favicon` to use the new icon

## 3. Custom Doc Styling

- [x] 3.1 Create docs/stylesheets/extra.css with CSS custom properties for project-specific colors (primary, accent)
- [x] 3.2 Add card-based feature grid styles (responsive: 3-col desktop, 2-col tablet, 1-col mobile)
- [x] 3.3 Add hero section styles (centered layout, tagline, CTA buttons)
- [x] 3.4 Reference extra.css in mkdocs.yml under `extra_css`
- [x] 3.5 Create social card image (docs/assets/social.png) — 1200x630px with icon, name, tagline
- [x] 3.6 Add Open Graph meta config to mkdocs.yml (`extra.social`)

## 4. Landing Page Overhaul

- [x] 4.1 Rewrite docs/index.md: add hero section with project name, tagline, and CTA buttons (Get Started, Examples)
- [x] 4.2 Convert the feature bullet list into a card grid using the CSS from step 3
- [x] 4.3 Add "Examples" link to the quick navigation section
- [x] 4.4 Update mkdocs.yml nav to include the examples page

## 5. Examples Page

- [x] 5.1 Create docs/examples.md with three content tabs (Classic, Unfold + Celery, Unfold + RQ)
- [x] 5.2 Write Classic tab content: overview, mermaid architecture diagram, setup steps, key code snippets
- [x] 5.3 Write Unfold + Celery tab content: overview, architecture diagram, setup (Docker + Celery worker), FileOrPathField demo
- [x] 5.4 Write Unfold + RQ tab content: overview, architecture diagram, custom runner implementation walkthrough

## 6. Zensical Migration

- [x] 6.1 Install zensical and verify it builds the current docs without errors (`zensical build`)
- [x] 6.2 Verify all plugins work with zensical: mkdocstrings, literate-nav, section-index, open-in-new-tab
- [x] 6.3 Update pyproject.toml: replace mkdocs + mkdocs-material deps with zensical in docs group
- [x] 6.4 Update Justfile: change `just docs` task to use `zensical serve` and `zensical build`
- [x] 6.5 Verify the full build produces visually equivalent output
- [x] 6.6 Run `just check` to ensure linting passes on all changed files
