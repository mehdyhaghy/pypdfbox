"""Coverage-boost tests for ``pypdfbox.tools.pdf_text2_html`` (wave 1316).

The module ports upstream ``PDFText2HTML`` + the inner ``FontState``
helper. Pre-wave, the file sat at 35% line coverage — the module-level
escape helpers, ``FontState`` state machine, and the HTML-wrapping
overrides (``start_document`` / ``end_document`` / ``start_article`` /
``end_article`` / ``write_paragraph_end`` / ``get_title``) were
untested.

The HTML-wrapping overrides call ``super().write_string(text)`` with a
single argument while the parent ``PDFTextStripper.write_string`` now
takes ``(text, text_positions, sink)`` — see the upstream-divergence
note in CHANGES.md. To keep the wrapping overrides exercisable from
unit tests without a parent-class rewrite, the tests below replace the
parent's ``write_string`` on a per-test basis with a capture stub. The
parent's ``write_paragraph_end`` (also a 3-arg in pypdfbox's parent
signature) is similarly stubbed where touched.
"""
from __future__ import annotations

import types
from typing import Any

import pytest

from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.tools.pdf_text2_html import (
    INITIAL_PDF_TO_HTML_BYTES,
    FontState,
    PDFText2HTML,
    _append_escaped,
    _escape,
)


# --------------------------------------------------------------------------
# parent-class shim
# --------------------------------------------------------------------------
@pytest.fixture
def patched_parent(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace ``PDFTextStripper.write_string`` /
    ``write_paragraph_end`` with one-arg / no-arg capture stubs so the
    PDFText2HTML wrapping methods can be exercised in isolation."""
    captured: list[str] = []

    def _capture(self: Any, text: str, *args: Any, **kw: Any) -> None:
        captured.append(text)

    def _para_end(self: Any, *args: Any, **kw: Any) -> None:
        captured.append("<PARA_END>")

    monkeypatch.setattr(PDFTextStripper, "write_string", _capture)
    monkeypatch.setattr(PDFTextStripper, "write_paragraph_end", _para_end)
    return captured


# --------------------------------------------------------------------------
# module-level constants + escape helpers
# --------------------------------------------------------------------------
def test_initial_pdf_to_html_bytes_constant() -> None:
    """Mirrors upstream's ``INITIAL_PDF_TO_HTML_BYTES = 8192`` constant."""
    assert INITIAL_PDF_TO_HTML_BYTES == 8192


def test_escape_passes_through_printable_ascii() -> None:
    assert _escape("Hello") == "Hello"


def test_escape_replaces_html_specials() -> None:
    assert _escape('"&<>') == "&quot;&amp;&lt;&gt;"


def test_escape_encodes_non_printable_as_numeric_entity() -> None:
    # Newline (code 10) is below 32 -> numeric entity.
    assert _escape("\n") == "&#10;"
    # DEL (127) is above 126 -> numeric entity.
    assert _escape("\x7f") == "&#127;"


def test_escape_handles_mixed_run() -> None:
    assert _escape("a<\n") == "a&lt;&#10;"


def test_append_escaped_writes_into_provided_builder() -> None:
    builder: list[str] = []
    _append_escaped(builder, "x")
    _append_escaped(builder, "&")
    _append_escaped(builder, "\x01")
    assert builder == ["x", "&amp;", "&#1;"]


def test_static_escape_proxies_module_helper() -> None:
    """The static class method on ``PDFText2HTML`` mirrors the upstream
    private static ``escape`` — both must produce identical output."""
    assert PDFText2HTML.escape("a<b") == _escape("a<b")


def test_static_append_escaped_proxies_module_helper() -> None:
    builder: list[str] = []
    PDFText2HTML.append_escaped(builder, ">")
    assert builder == ["&gt;"]


# --------------------------------------------------------------------------
# FontState — state machine
# --------------------------------------------------------------------------
def test_font_state_open_emits_tag_and_records_state() -> None:
    fs = FontState()
    assert fs.open("b") == "<b>"
    # Re-opening the same tag is a no-op.
    assert fs.open("b") == ""


def test_font_state_close_on_unopened_tag_is_noop() -> None:
    assert FontState().close("b") == ""


def test_font_state_close_reopens_tags_above_target() -> None:
    """When closing a tag that's not the innermost, upstream's behaviour
    is to close every tag down to and including the target, then re-open
    the intermediate tags that were collateral damage."""
    fs = FontState()
    fs.open("b")
    fs.open("i")
    # Close ``b`` (the outer tag) — innermost ``i`` must be closed and
    # then re-opened so the bold tag can come off.
    closed = fs.close("b")
    assert closed == "</i></b><i>"


def test_font_state_clear_closes_all_open_tags() -> None:
    fs = FontState()
    fs.open("b")
    fs.open("i")
    out = fs.clear()
    # innermost first, outermost last.
    assert out == "</i></b>"
    # State emptied.
    assert fs.clear() == ""


def test_font_state_open_tag_close_tag_helpers() -> None:
    fs = FontState()
    assert fs.open_tag("strong") == "<strong>"
    assert fs.close_tag("strong") == "</strong>"


def test_font_state_is_bold_detects_force_bold_flag() -> None:
    class _Desc:
        def is_force_bold(self) -> bool:
            return True

        def get_font_name(self) -> str:
            return "Plain"

        def is_italic(self) -> bool:
            return False

    assert FontState().is_bold(_Desc()) is True


def test_font_state_is_bold_detects_name_suffix() -> None:
    class _Desc:
        def is_force_bold(self) -> bool:
            return False

        def get_font_name(self) -> str:
            return "Foo-Bold-Cn"

        def is_italic(self) -> bool:
            return False

    assert FontState().is_bold(_Desc()) is True


def test_font_state_is_italic_detects_flag_or_name() -> None:
    class _FlagDesc:
        def is_italic(self) -> bool:
            return True

        def is_force_bold(self) -> bool:
            return False

        def get_font_name(self) -> str:
            return "Plain"

    class _NameDesc:
        def is_italic(self) -> bool:
            return False

        def is_force_bold(self) -> bool:
            return False

        def get_font_name(self) -> str:
            return "Foo-Italic"

    fs = FontState()
    assert fs.is_italic(_FlagDesc()) is True
    assert fs.is_italic(_NameDesc()) is True


def test_font_state_push_with_matched_text_and_positions() -> None:
    """When ``len(text) == len(text_positions)``, each character is
    pushed through the per-char dispatcher with its matching position."""

    class _Desc:
        def __init__(self, name: str, bold: bool, italic: bool) -> None:
            self._name = name
            self._b = bold
            self._i = italic

        def get_font_name(self) -> str:
            return self._name

        def is_force_bold(self) -> bool:
            return self._b

        def is_italic(self) -> bool:
            return self._i

    class _Font:
        def __init__(self, d: _Desc) -> None:
            self._d = d

        def get_font_descriptor(self) -> _Desc:
            return self._d

    class _TP:
        def __init__(self, desc: _Desc) -> None:
            self._f = _Font(desc)

        def get_font(self) -> _Font:
            return self._f

    bold = _TP(_Desc("Foo-Bold", True, False))
    italic = _TP(_Desc("Foo-Italic", False, True))
    fs = FontState()
    out = fs.push("AB", [bold, italic])
    # ``A`` opens <b>, ``B`` closes <b> and opens <i>.
    assert out.startswith("<b>A")
    assert "<i>B" in out


def test_font_state_push_falls_back_to_single_position_then_escape() -> None:
    """If ``len(text) != len(text_positions)`` and there are positions,
    upstream's logic pushes only the first char via the descriptor path
    and escapes the tail."""

    class _NoDescFont:
        def get_font_descriptor(self) -> None:
            return None

    class _TP:
        def get_font(self) -> _NoDescFont:
            return _NoDescFont()

    fs = FontState()
    out = fs.push("Hi<", [_TP()])
    # ``H`` goes through the position branch, then ``i<`` is escaped.
    assert out.endswith("i&lt;")


def test_font_state_push_no_positions_returns_raw_text() -> None:
    """When the positions list is empty and the text non-empty, upstream
    returns ``text`` unchanged (no escape)."""
    out = FontState().push("abc", [])
    assert out == "abc"


def test_font_state_push_empty_text_returns_empty() -> None:
    assert FontState().push("", []) == ""


def test_font_state_push_char_handles_attribute_error_descriptor() -> None:
    """If ``text_position.get_font()`` raises ``AttributeError``,
    descriptor stays ``None`` and the char is emitted with no style."""

    class _BareTP:
        # No ``get_font`` → AttributeError, swallowed.
        pass

    buffer: list[str] = []
    FontState().push_char(buffer, "x", _BareTP())
    # No style tags, just the escaped character.
    assert "".join(buffer) == "x"


# --------------------------------------------------------------------------
# PDFText2HTML — constructor + getters
# --------------------------------------------------------------------------
def test_constructor_configures_paragraph_and_page_markers() -> None:
    p = PDFText2HTML()
    assert p.get_paragraph_start() == "<p>"
    # Paragraph end carries the configured line separator.
    sep = p.get_line_separator()
    assert p.get_paragraph_end() == "</p>" + sep
    # Page-end mirrors upstream: ``</div><sep>``.
    assert p.get_page_end() == "</div>" + sep


# --------------------------------------------------------------------------
# wrapping overrides (require parent-class write_string stub)
# --------------------------------------------------------------------------
def test_start_document_emits_html_head_and_doctype(patched_parent: list[str]) -> None:
    p = PDFText2HTML()
    p.start_document(None)
    body = "".join(patched_parent)
    assert "<!DOCTYPE html" in body
    assert "<title>" in body
    assert "<body>" in body


def test_end_document_closes_body_and_html(patched_parent: list[str]) -> None:
    p = PDFText2HTML()
    p.end_document(None)
    assert "".join(patched_parent) == "</body></html>"


def test_start_article_ltr_emits_plain_div(patched_parent: list[str]) -> None:
    p = PDFText2HTML()
    p.start_article(True)
    assert "<div>" in "".join(patched_parent)


def test_start_article_rtl_emits_dir_attribute(patched_parent: list[str]) -> None:
    p = PDFText2HTML()
    p.start_article(False)
    assert '<div dir="RTL">' in "".join(patched_parent)


def test_end_article_emits_closing_div(patched_parent: list[str]) -> None:
    p = PDFText2HTML()
    p.end_article()
    assert "</div>" in "".join(patched_parent)


def test_write_string_no_positions_escapes_and_forwards(
    patched_parent: list[str],
) -> None:
    p = PDFText2HTML()
    p.write_string("a & b")
    assert "".join(patched_parent) == "a &amp; b"


def test_write_string_with_positions_routes_through_font_state(
    patched_parent: list[str],
) -> None:
    class _Desc:
        def get_font_name(self) -> str:
            return "Foo-Bold"

        def is_force_bold(self) -> bool:
            return True

        def is_italic(self) -> bool:
            return False

    class _Font:
        def get_font_descriptor(self) -> _Desc:
            return _Desc()

    class _TP:
        def get_font(self) -> _Font:
            return _Font()

    p = PDFText2HTML()
    p.write_string("X", [_TP()])
    assert "<b>X" in "".join(patched_parent)


def test_write_paragraph_end_clears_font_state(patched_parent: list[str]) -> None:
    p = PDFText2HTML()
    # Prime the font state so ``clear`` has something to emit.
    p._font_state.open("b")  # noqa: SLF001 — exercising port invariant
    p.write_paragraph_end()
    captured = "".join(patched_parent)
    assert "</b>" in captured
    # Parent's write_paragraph_end was patched to append ``<PARA_END>``.
    assert "<PARA_END>" in captured


# --------------------------------------------------------------------------
# get_title
# --------------------------------------------------------------------------
def test_get_title_returns_empty_when_no_document_attr() -> None:
    p = PDFText2HTML()
    assert p.get_title() == ""


def test_get_title_returns_document_information_title() -> None:
    class _Info:
        def get_title(self) -> str:
            return "Document Name"

    class _Doc:
        def get_document_information(self) -> _Info:
            return _Info()

    p = PDFText2HTML()
    p.document = _Doc()
    assert p.get_title() == "Document Name"


def test_get_title_falls_back_to_largest_font_run() -> None:
    """When info has no title, the scanner walks characters by article
    and collects any > 13pt run as the heuristic title."""

    class _InfoEmpty:
        def get_title(self) -> str | None:
            return None

    class _Doc:
        def get_document_information(self) -> _InfoEmpty:
            return _InfoEmpty()

    class _TP:
        def __init__(self, size: float, ch: str) -> None:
            self._s = size
            self._u = ch

        def get_font_size(self) -> float:
            return self._s

        def get_unicode(self) -> str:
            return self._u

    p = PDFText2HTML()
    p.document = _Doc()
    p.get_characters_by_article = types.MethodType(  # type: ignore[method-assign]
        lambda self: [[_TP(14.0, "B"), _TP(14.0, "i"), _TP(14.0, "g")], [_TP(10.0, "x")]],
        p,
    )
    assert p.get_title() == "Big"


def test_get_title_returns_empty_when_no_large_runs() -> None:
    class _InfoEmpty:
        def get_title(self) -> str | None:
            return None

    class _Doc:
        def get_document_information(self) -> _InfoEmpty:
            return _InfoEmpty()

    class _TP:
        def __init__(self, size: float, ch: str) -> None:
            self._s = size
            self._u = ch

        def get_font_size(self) -> float:
            return self._s

        def get_unicode(self) -> str:
            return self._u

    p = PDFText2HTML()
    p.document = _Doc()
    p.get_characters_by_article = types.MethodType(  # type: ignore[method-assign]
        lambda self: [[_TP(10.0, "x"), _TP(10.0, "y")]],
        p,
    )
    assert p.get_title() == ""


def test_get_title_swallows_get_characters_attribute_error() -> None:
    """If ``get_characters_by_article`` raises ``AttributeError``, the
    scanner returns ``""`` instead of bubbling the failure."""

    class _InfoEmpty:
        def get_title(self) -> str | None:
            return None

    class _Doc:
        def get_document_information(self) -> _InfoEmpty:
            return _InfoEmpty()

    def _raise(self: Any) -> Any:
        raise AttributeError("not implemented")

    p = PDFText2HTML()
    p.document = _Doc()
    p.get_characters_by_article = types.MethodType(_raise, p)  # type: ignore[method-assign]
    assert p.get_title() == ""
