## Context

The `RegisteredCommandAdmin.name_link` method renders the command description as an inline-styled `<span>` with a hard-coded `max-width:300px`. This fixed width truncates descriptions regardless of the actual column width available in the admin changelist table. On wider screens, the column has more space than 300px, yet descriptions still cut off prematurely.

Additionally, the `list.html` templates (both base and Unfold variants) render descriptions without any truncation, which can cause layout overflow with very long help text.

## Goals / Non-Goals

**Goals:**
- Make description truncation responsive to the actual available container width, not a fixed pixel value.
- Apply consistent truncation behavior across the admin changelist and both list template variants.
- Use pure CSS (no JavaScript) for the truncation.

**Non-Goals:**
- Adding a tooltip/popover on hover to show the full description (could be a future enhancement).
- Changing the visual appearance beyond the truncation behavior.
- Adding any JavaScript or dynamic resizing logic.

## Decisions

### Use CSS `max-width:100%` with `overflow:hidden; text-overflow:ellipsis` on a block-level element

**Decision**: Replace `max-width:300px` with `max-width:100%` (or remove max-width entirely and rely on the parent's natural constraints), keep `overflow:hidden; text-overflow:ellipsis; white-space:nowrap; display:block`, and ensure the parent `<td>` constrains width properly.

**Rationale**: The admin changelist table cell already has a natural width. Using `max-width:100%` lets the description span the full available column width. `text-overflow:ellipsis` only activates when content actually overflows — short descriptions render in full, long ones get the ellipsis. This is pure CSS, zero JavaScript, and works across all browsers.

**Alternative considered**: Using JavaScript to detect overflow and add a title attribute. Rejected because it adds complexity and a JS dependency for a purely presentational concern.

**Alternative considered**: Using `-webkit-line-clamp` for multi-line truncation. Rejected because the current design is single-line and line-clamp has inconsistent browser support for the ellipsis indicator in all contexts.

### Apply the same truncation CSS in list.html templates

**Decision**: Add `overflow:hidden; text-overflow:ellipsis; white-space:nowrap;` to the description elements in both `unfold/list.html` and `base/list.html`.

**Rationale**: Very long management command help text can break layouts. Applying consistent truncation prevents overflow while still showing as much as fits.

## Risks / Trade-offs

- **[Risk] Column width may vary by browser/screen size** → Acceptable trade-off; the behavior is "truncate only when needed" which is the desired outcome. The column will naturally size based on Django admin's table layout.
- **[Risk] Very narrow viewports may still truncate aggressively** → This is inherent to CSS truncation and matches user expectations. The alternative (wrapping) would make the changelist harder to scan.
