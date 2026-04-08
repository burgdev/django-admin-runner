"""Minimal ANSI escape sequence to HTML converter.

Converts SGR (Select Graphic Rendition) escape sequences to HTML ``<span>``
elements with CSS classes and/or inline ``style`` attributes.

Supported codes:
- ``0``  — reset
- ``1``  bold, ``2`` dim, ``3`` italic, ``4`` underline
- ``22`` reset bold/dim, ``23`` reset italic, ``24`` reset underline
- ``30–37`` / ``90–97``  — 4-bit foreground (standard + bright) → CSS class
- ``40–47`` / ``100–107`` — 4-bit background → CSS class
- ``38;5;N`` / ``48;5;N`` — 256-colour: N<16 → CSS class, N≥16 → inline rgb()
- ``38;2;r;g;b`` / ``48;2;r;g;b`` — truecolor → inline rgb()
- ``39`` / ``49`` — reset foreground / background

4-bit colours map to ``ansi-fg-N`` / ``ansi-bg-N`` CSS classes (N = 0–15).
Style attributes are provided by ``ansi-output.css`` via CSS custom properties,
making the palette theme-aware (dark / light mode).
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field

_ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")


@dataclass
class _State:
    fg: int | None = None  # 0-15 → CSS class
    bg: int | None = None
    fg_rgb: tuple[int, int, int] | None = None  # truecolor / 256-colour ≥16
    bg_rgb: tuple[int, int, int] | None = None
    attrs: set[str] = field(default_factory=set)  # bold, dim, italic, underline

    def reset(self) -> None:
        self.fg = None
        self.bg = None
        self.fg_rgb = None
        self.bg_rgb = None
        self.attrs.clear()

    def is_default(self) -> bool:
        return (
            self.fg is None
            and self.bg is None
            and self.fg_rgb is None
            and self.bg_rgb is None
            and not self.attrs
        )

    def css_classes(self) -> list[str]:
        classes = [f"ansi-{a}" for a in sorted(self.attrs)]
        if self.fg is not None:
            classes.append(f"ansi-fg-{self.fg}")
        if self.bg is not None:
            classes.append(f"ansi-bg-{self.bg}")
        return classes

    def inline_styles(self) -> list[str]:
        styles = []
        if self.fg_rgb is not None:
            r, g, b = self.fg_rgb
            styles.append(f"color:rgb({r},{g},{b})")
        if self.bg_rgb is not None:
            r, g, b = self.bg_rgb
            styles.append(f"background:rgb({r},{g},{b})")
        return styles


def _256_to_rgb(n: int) -> tuple[int, int, int]:
    """Convert 256-colour index ≥16 to ``(r, g, b)``."""
    if n < 232:
        n -= 16
        return ((n // 36) * 51, ((n % 36) // 6) * 51, (n % 6) * 51)
    v = (n - 232) * 10 + 8
    return (v, v, v)


def _apply_sgr(state: _State, params: list[int]) -> None:
    """Apply a list of SGR parameter values to *state* in-place."""
    i = 0
    while i < len(params):
        p = params[i]

        if p == 0:
            state.reset()
        elif p == 1:
            state.attrs.add("bold")
        elif p == 2:
            state.attrs.add("dim")
        elif p == 3:
            state.attrs.add("italic")
        elif p == 4:
            state.attrs.add("underline")
        elif p == 22:
            state.attrs.discard("bold")
            state.attrs.discard("dim")
        elif p == 23:
            state.attrs.discard("italic")
        elif p == 24:
            state.attrs.discard("underline")
        elif 30 <= p <= 37:
            state.fg = p - 30
            state.fg_rgb = None
        elif p == 38:
            if i + 1 < len(params) and params[i + 1] == 5 and i + 2 < len(params):
                n = params[i + 2]
                if n < 16:
                    state.fg = n
                    state.fg_rgb = None
                else:
                    state.fg = None
                    state.fg_rgb = _256_to_rgb(n)
                i += 2
            elif i + 1 < len(params) and params[i + 1] == 2 and i + 4 < len(params):
                state.fg = None
                state.fg_rgb = (params[i + 2], params[i + 3], params[i + 4])
                i += 4
        elif p == 39:
            state.fg = None
            state.fg_rgb = None
        elif 40 <= p <= 47:
            state.bg = p - 40
            state.bg_rgb = None
        elif p == 48:
            if i + 1 < len(params) and params[i + 1] == 5 and i + 2 < len(params):
                n = params[i + 2]
                if n < 16:
                    state.bg = n
                    state.bg_rgb = None
                else:
                    state.bg = None
                    state.bg_rgb = _256_to_rgb(n)
                i += 2
            elif i + 1 < len(params) and params[i + 1] == 2 and i + 4 < len(params):
                state.bg = None
                state.bg_rgb = (params[i + 2], params[i + 3], params[i + 4])
                i += 4
        elif p == 49:
            state.bg = None
            state.bg_rgb = None
        elif 90 <= p <= 97:
            state.fg = p - 90 + 8  # bright colours → indices 8–15
            state.fg_rgb = None
        elif 100 <= p <= 107:
            state.bg = p - 100 + 8
            state.bg_rgb = None

        i += 1


def ansi_to_html(text: str) -> str:
    """Convert ANSI escape sequences in *text* to HTML ``<span>`` elements.

    Text content is HTML-escaped.  Spans use CSS classes for 4-bit colours
    (``ansi-fg-N`` / ``ansi-bg-N``) and inline ``style`` attributes for
    256-colour (indices ≥16) and truecolor values.
    """
    result: list[str] = []
    state = _State()
    span_open = False

    def flush_span() -> None:
        nonlocal span_open
        if span_open:
            result.append("</span>")
            span_open = False

    def emit_text(chunk: str) -> None:
        nonlocal span_open
        if not chunk:
            return
        if not span_open and not state.is_default():
            classes = state.css_classes()
            styles = state.inline_styles()
            attrs = ""
            if classes:
                attrs += f' class="{" ".join(classes)}"'
            if styles:
                attrs += f' style="{";".join(styles)}"'
            result.append(f"<span{attrs}>")
            span_open = True
        result.append(_html.escape(chunk))

    pos = 0
    for match in _ANSI_RE.finditer(text):
        start, end = match.span()
        emit_text(text[pos:start])
        flush_span()
        raw = match.group(1)
        params = [int(x) for x in raw.split(";") if x] if raw else [0]
        _apply_sgr(state, params)
        pos = end

    emit_text(text[pos:])
    flush_span()

    return "".join(result)
