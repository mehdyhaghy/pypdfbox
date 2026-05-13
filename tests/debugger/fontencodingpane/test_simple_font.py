"""Tests for the :class:`SimpleFont` encoding pane."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.debugger.fontencodingpane.simple_font import SimpleFont
from pypdfbox.pdmodel.font import PDType1Font


def _helvetica() -> PDType1Font:
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "Type1")
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font_dict.set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    return PDType1Font(font_dict)


def test_simple_font_builds_256_row_table(tk_root):
    pane = SimpleFont(_helvetica(), tk_root)
    # WinAnsi is a complete encoding for the printable range — every
    # row from 0..255 should be present.
    assert pane.total_available_glyphs == 256
    assert len(pane.view.tree.get_children()) == 256


def test_simple_font_header_attributes(tk_root):
    # Construct the pane to exercise the constructor path, then exercise
    # the static helper directly.
    SimpleFont(_helvetica(), tk_root)
    # Encoding name format mirrors upstream: "<font class> / <encoding name>".
    assert "WinAnsiEncoding" in SimpleFont.get_encoding_name(_helvetica())


def test_simple_font_get_panel_is_view(tk_root):
    pane = SimpleFont(_helvetica(), tk_root)
    assert pane.get_panel() is pane.view


def test_simple_font_first_row_is_code_zero(tk_root):
    pane = SimpleFont(_helvetica(), tk_root)
    children = pane.view.tree.get_children()
    first = pane.view.tree.item(children[0])
    assert first["text"] == "0"


def test_simple_font_handles_font_without_encoding(tk_root):
    """A font dict without an /Encoding entry should still construct.

    Upstream's ``getEncodingName`` returns ``"(null)"`` when the
    encoding is missing.
    """
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("Type"), "Font")
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "Type1")
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font = PDType1Font(font_dict)
    # ``PDSimpleFont`` synthesises a default StandardEncoding for
    # Standard-14 / non-symbolic fonts even when /Encoding is absent,
    # so the encoding-name string still shows up — we just verify it
    # constructs and produces some glyph rows.
    pane = SimpleFont(font, tk_root)
    assert pane.total_available_glyphs > 0


def test_simple_font_swallows_to_unicode_oserror(tk_root, monkeypatch):
    """When ``font.to_unicode`` raises ``OSError`` for a code, the row
    falls back to Latin-1 character mapping and still gets emitted.
    """
    font = _helvetica()
    original_to_unicode = font.to_unicode
    seen: list[int] = []

    def _patched(code: int) -> str | None:
        seen.append(code)
        if code == 65:
            raise OSError("simulated to_unicode failure")
        return original_to_unicode(code)

    monkeypatch.setattr(font, "to_unicode", _patched)
    pane = SimpleFont(font, tk_root)
    # Row still produced — ``unicode_char`` falls back to ``chr(65)`` = "A".
    assert pane.total_available_glyphs > 0
    assert 65 in seen


def test_simple_font_swallows_get_path_oserror(tk_root, monkeypatch):
    """When ``font.get_path`` raises ``OSError``, the glyph cell is set
    to an empty list and a row is still appended (line 113-121)."""
    font = _helvetica()

    def _patched(name: str) -> list:
        if name == "A":
            raise OSError("forced get_path failure")
        return []

    monkeypatch.setattr(font, "get_path", _patched)
    pane = SimpleFont(font, tk_root)
    # Row for code 65 ("A") still emitted.
    children = pane.view.tree.get_children()
    assert len(children) == 256


def test_simple_font_notdef_branch_with_stub(tk_root):
    """Exercise the ``.notdef`` fallback branch in ``_get_glyphs`` (line
    126-130) where the row drops to ``NO_GLYPH`` because the code is
    outside the encoding AND ``unicode_char`` is None.

    Reaching that else requires both ``encoding.contains(code) == False``
    AND ``unicode_char is None`` after the ``chr(code)`` fallback. The
    chr-fallback always produces a string in normal Python, so we shim
    ``chr`` in the ``simple_font`` module namespace to return ``None``
    and provide a narrow encoding that excludes most codes — driving
    the loop into the else branch.
    """
    from pypdfbox.debugger.fontencodingpane import simple_font as sf_mod

    class _NarrowEncoding:
        """Encoding that only contains codes 65..67 — most codes fall
        through to the ``.notdef`` branch."""

        def contains(self, code: int) -> bool:
            return 65 <= code <= 67

        def get_name(self, code: int) -> str:
            return chr(code) if self.contains(code) else ".notdef"

        def get_encoding_name(self) -> str:
            return "NarrowEncoding"

    class _StubFont:
        def get_name(self) -> str:
            return "Stub"

        def is_standard14(self) -> bool:
            return False

        def is_embedded(self) -> bool:
            return False

        def get_encoding_typed(self):
            return _NarrowEncoding()

        def to_unicode(self, code: int) -> str | None:  # noqa: ARG002
            return None

        def get_path(self, name: str) -> list:
            if name == ".notdef":
                raise OSError("forced .notdef fail")
            return [("moveTo", 0.0, 0.0)]

    # Inject ``chr`` into the simple_font module globals so the
    # in-source ``chr(code)`` fallback yields None and the row drops
    # through to the .notdef else branch.
    sf_globals = vars(sf_mod)

    def _none_chr(_code):
        return None  # type: ignore[return-value]

    sf_globals["chr"] = _none_chr
    try:
        pane = SimpleFont(_StubFont(), tk_root)  # type: ignore[arg-type]
        # 256 rows always produced — codes 65..67 take the encoded path,
        # all others land in the ``.notdef`` else (with OSError handled).
        assert len(pane.view.tree.get_children()) == 256
    finally:
        del sf_globals["chr"]
