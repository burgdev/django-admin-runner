## Why

Visiting the docs site root returns a 404 because there is no `docs/index.md` file. Additionally, the `literate-nav` plugin is configured to read `docs/SUMMARY.md` but that file doesn't exist either, which means the plugin silently overrides the `nav` section in `mkdocs.yml` and breaks navigation entirely. Users landing on the docs site see nothing useful.

## What Changes

- Create `docs/index.md` as the site landing page that redirects or links to "Getting Started"
- Create `docs/SUMMARY.md` to provide the literate-nav plugin with proper navigation structure
- Ensure the root page renders the Getting Started content (hero + feature cards) instead of a 404

## Capabilities

### New Capabilities

- `docs-index`: Landing page for the documentation site root, providing a clear entry point and navigation to Getting Started

### Modified Capabilities

(none - this is a docs-only fix, no spec-level behavior changes)

## Impact

- `docs/index.md` (new file)
- `docs/SUMMARY.md` (new file)
- `mkdocs.yml` may need minor adjustments to the `nav` section if `literate-nav` conflict persists
