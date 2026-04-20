"""Tests for the minimal ANSI-to-HTML converter in django_admin_runner._ansi."""

from django_admin_runner._ansi import _256_to_rgb, ansi_to_html, linkify_urls

# ---------------------------------------------------------------------------
# Plain text / HTML escaping
# ---------------------------------------------------------------------------


def test_plain_text_passthrough():
    assert ansi_to_html("hello world") == "hello world"


def test_empty_string():
    assert ansi_to_html("") == ""


def test_html_escape_lt_gt():
    assert ansi_to_html("<b>hi</b>") == "&lt;b&gt;hi&lt;/b&gt;"


def test_html_escape_ampersand():
    assert ansi_to_html("a & b") == "a &amp; b"


def test_no_span_for_plain_text():
    assert "<span" not in ansi_to_html("plain")


# ---------------------------------------------------------------------------
# Text attributes
# ---------------------------------------------------------------------------


def test_bold():
    assert ansi_to_html("\x1b[1mBold\x1b[0m") == '<span class="ansi-bold">Bold</span>'


def test_dim():
    assert ansi_to_html("\x1b[2mDim\x1b[0m") == '<span class="ansi-dim">Dim</span>'


def test_italic():
    assert ansi_to_html("\x1b[3mItalic\x1b[0m") == '<span class="ansi-italic">Italic</span>'


def test_underline():
    assert ansi_to_html("\x1b[4mUnder\x1b[0m") == '<span class="ansi-underline">Under</span>'


# ---------------------------------------------------------------------------
# 4-bit foreground colours
# ---------------------------------------------------------------------------


def test_fg_standard_color():
    # 32 = green → ansi-fg-2
    assert ansi_to_html("\x1b[32mGreen\x1b[0m") == '<span class="ansi-fg-2">Green</span>'


def test_fg_bright_color():
    # 92 = bright green → ansi-fg-10
    assert ansi_to_html("\x1b[92mBright\x1b[0m") == '<span class="ansi-fg-10">Bright</span>'


def test_fg_all_standard_range():
    for code in range(30, 38):
        idx = code - 30
        result = ansi_to_html(f"\x1b[{code}mX\x1b[0m")
        assert f"ansi-fg-{idx}" in result


def test_fg_all_bright_range():
    for code in range(90, 98):
        idx = code - 90 + 8
        result = ansi_to_html(f"\x1b[{code}mX\x1b[0m")
        assert f"ansi-fg-{idx}" in result


# ---------------------------------------------------------------------------
# 4-bit background colours
# ---------------------------------------------------------------------------


def test_bg_standard_color():
    # 41 = red bg → ansi-bg-1
    assert ansi_to_html("\x1b[41mBg\x1b[0m") == '<span class="ansi-bg-1">Bg</span>'


def test_bg_bright_color():
    # 101 = bright red bg → ansi-bg-9
    assert ansi_to_html("\x1b[101mBg\x1b[0m") == '<span class="ansi-bg-9">Bg</span>'


# ---------------------------------------------------------------------------
# Combined attributes
# ---------------------------------------------------------------------------


def test_combined_bold_and_fg():
    result = ansi_to_html("\x1b[1;32mBoldGreen\x1b[0m")
    assert "ansi-bold" in result
    assert "ansi-fg-2" in result
    assert "BoldGreen" in result


def test_combined_fg_and_bg():
    result = ansi_to_html("\x1b[32;41mGreenOnRed\x1b[0m")
    assert "ansi-fg-2" in result
    assert "ansi-bg-1" in result


# ---------------------------------------------------------------------------
# 256-colour codes
# ---------------------------------------------------------------------------


def test_256_color_low_index_uses_class():
    # 38;5;3 → index < 16 → CSS class
    result = ansi_to_html("\x1b[38;5;3mYellow\x1b[0m")
    assert result == '<span class="ansi-fg-3">Yellow</span>'


def test_256_color_high_index_uses_inline_style():
    # 38;5;196 → index ≥ 16 → inline rgb()
    result = ansi_to_html("\x1b[38;5;196mRed\x1b[0m")
    assert 'style="color:rgb(' in result
    assert "Red" in result
    assert "ansi-fg" not in result


def test_256_bg_low_index_uses_class():
    result = ansi_to_html("\x1b[48;5;2mBg\x1b[0m")
    assert result == '<span class="ansi-bg-2">Bg</span>'


def test_256_bg_high_index_uses_inline_style():
    result = ansi_to_html("\x1b[48;5;200mBg\x1b[0m")
    assert 'style="background:rgb(' in result


# ---------------------------------------------------------------------------
# Truecolor codes
# ---------------------------------------------------------------------------


def test_truecolor_fg():
    result = ansi_to_html("\x1b[38;2;200;100;50mCustom\x1b[0m")
    assert 'style="color:rgb(200,100,50)"' in result
    assert "Custom" in result


def test_truecolor_bg():
    result = ansi_to_html("\x1b[48;2;10;20;30mBg\x1b[0m")
    assert 'style="background:rgb(10,20,30)"' in result


def test_truecolor_combined_fg_and_bg():
    result = ansi_to_html("\x1b[38;2;255;0;0m\x1b[48;2;0;0;255mText\x1b[0m")
    assert "color:rgb(255,0,0)" in result
    assert "background:rgb(0,0,255)" in result


# ---------------------------------------------------------------------------
# Reset / state management
# ---------------------------------------------------------------------------


def test_reset_closes_span():
    result = ansi_to_html("\x1b[32mGreen\x1b[0m normal")
    assert result == '<span class="ansi-fg-2">Green</span> normal'


def test_empty_escape_acts_as_reset():
    # \x1b[m (no params) = reset
    result = ansi_to_html("\x1b[32mGreen\x1b[m normal")
    assert result == '<span class="ansi-fg-2">Green</span> normal'


def test_no_unclosed_span():
    # Span opened but never explicitly reset — flush_span closes it
    result = ansi_to_html("\x1b[32mGreen")
    assert result.count("<span") == result.count("</span>")


def test_partial_reset_bold():
    # 22 resets bold/dim but keeps colour
    result = ansi_to_html("\x1b[1;32mBoldGreen\x1b[22mJustGreen\x1b[0m")
    assert "ansi-bold" not in result.split("JustGreen")[1]
    assert "ansi-fg-2" in result.split("JustGreen")[1] or "ansi-fg-2" in result


def test_fg_reset_code_39():
    result = ansi_to_html("\x1b[32mGreen\x1b[39m after")
    # After 39, fg is cleared; "after" should not be in a coloured span
    assert "after" in result
    # The "after" portion should be plain (outside any fg-class span)
    after_part = result.split("after")
    assert "ansi-fg" not in after_part[-1]


# ---------------------------------------------------------------------------
# _256_to_rgb helper
# ---------------------------------------------------------------------------


def test_256_to_rgb_color_cube_black():
    assert _256_to_rgb(16) == (0, 0, 0)


def test_256_to_rgb_color_cube_white():
    assert _256_to_rgb(231) == (255, 255, 255)


def test_256_to_rgb_grayscale_start():
    assert _256_to_rgb(232) == (8, 8, 8)


def test_256_to_rgb_grayscale_end():
    assert _256_to_rgb(255) == (238, 238, 238)


def test_256_to_rgb_red():
    # index 196 = 6x6x6 cube entry for pure red (r=5, g=0, b=0)
    assert _256_to_rgb(196) == (255, 0, 0)


# ---------------------------------------------------------------------------
# URL auto-linking (linkify_urls)
# ---------------------------------------------------------------------------


def test_url_in_plain_text():
    html = linkify_urls("See https://example.com/export.csv for details")
    assert (
        '<a href="https://example.com/export.csv" target="_blank">https://example.com/export.csv</a>'
        in html
    )
    assert "See " in html
    assert " for details" in html


def test_url_with_ansi_spans():
    """URL linking works alongside ANSI color spans."""
    colored = ansi_to_html("\x1b[32mDone: https://example.com/report\x1b[0m")
    linked = linkify_urls(colored)
    assert 'href="https://example.com/report"' in linked
    assert 'target="_blank"' in linked
    assert "ansi-fg-2" in linked


def test_multiple_urls():
    html = linkify_urls("https://a.com and https://b.com")
    assert 'href="https://a.com"' in html
    assert 'href="https://b.com"' in html


def test_no_protocol_no_link():
    html = linkify_urls("visit example.com/file.csv today")
    assert "<a " not in html


def test_url_trailing_punctuation_stripped():
    html = linkify_urls("Saved to https://example.com/export.csv.")
    assert 'href="https://example.com/export.csv"' in html
    assert html.endswith(".")


def test_linkify_empty_string():
    assert linkify_urls("") == ""


def test_linkify_no_urls():
    assert linkify_urls("just plain text") == "just plain text"
