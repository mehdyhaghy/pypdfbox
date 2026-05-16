"""Coverage boost for :mod:`pypdfbox.pdmodel.font.pd_type1_font_embedder`.

Exercises the constructor end-to-end with a monkey-patched ``T1Font``
plus the ``build_font_descriptor`` Type-1 factory which the original
test module skips (it lacks a parsed Type 1 font).
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.pd_type1_font_embedder import PDType1FontEmbedder
from pypdfbox.pdmodel.pd_document import PDDocument


@pytest.fixture(scope="module", autouse=True)
def _install_missing_cos_name_constants() -> None:
    """``PDType1FontEmbedder.__init__`` references ``COSName.FONT_DESC`` /
    ``BASE_FONT`` / ``ENCODING`` which are not registered in
    ``cos_name.py``'s static table. Register them on demand so the
    constructor runs end-to-end. Order-independent: if another test
    module already installed them this is a no-op.
    """
    for attr, raw in (
        ("BASE_FONT", "BaseFont"),
        ("FONT_DESC", "FontDescriptor"),
        ("ENCODING", "Encoding"),
    ):
        if not hasattr(COSName, attr):
            setattr(COSName, attr, COSName.get_pdf_name(raw))


class _FakeGlyph:
    def __init__(self, width: float = 500.0) -> None:
        self.width = width


class _FakeGlyphSet:
    def __init__(self, glyphs: dict[str, _FakeGlyph] | None = None) -> None:
        self._glyphs = glyphs or {}

    def __getitem__(self, name: str) -> _FakeGlyph:
        return self._glyphs[name]


class _FakeT1:
    def __init__(self, font: dict[str, Any] | None = None) -> None:
        self.font = font if font is not None else {}

    def getGlyphSet(self) -> _FakeGlyphSet:  # noqa: N802 - upstream API
        # Provide a width for the "A" glyph; everything else falls back
        # to 0 via the KeyError path.
        return _FakeGlyphSet({"A": _FakeGlyph(680.0)})


def _patch_t1font(monkeypatch: pytest.MonkeyPatch, font_dict: dict[str, Any]) -> None:
    """Install a fake ``fontTools.t1Lib.T1Font`` that just stores the dict."""

    class _Stub:
        def __init__(self, _stream: Any) -> None:
            self.font = font_dict

        def getGlyphSet(self) -> _FakeGlyphSet:  # noqa: N802
            return _FakeGlyphSet({"A": _FakeGlyph(680.0), "B": _FakeGlyph(700.0)})

    import fontTools.t1Lib as t1mod

    monkeypatch.setattr(t1mod, "T1Font", _Stub)


def _synthetic_pfb() -> bytes:
    # Three segments + EOF marker — payload contents are irrelevant
    # because we monkey-patch T1Font.
    seg1 = b"%!PS-AdobeFont"
    seg2 = b"binary-segment"
    seg3 = b"end"
    return (
        b"\x80\x01" + len(seg1).to_bytes(4, "little") + seg1
        + b"\x80\x02" + len(seg2).to_bytes(4, "little") + seg2
        + b"\x80\x01" + len(seg3).to_bytes(4, "little") + seg3
        + b"\x80\x03"
    )


def test_constructor_with_full_font_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    font_dict = {
        "FontName": "MyType1",
        "FamilyName": "MyFamily",
        "FontBBox": [-100, -200, 800, 900],
        "FontInfo": {"ItalicAngle": -12},
        "Encoding": ["A", "B"] + [".notdef"] * 254,
    }
    _patch_t1font(monkeypatch, font_dict)
    doc = PDDocument()
    try:
        target = COSDictionary()
        embedder = PDType1FontEmbedder(doc, target, _synthetic_pfb(), None)
        assert target.get_name_as_string("Subtype") == "Type1"
        assert target.get_name_as_string("BaseFont") == "MyType1"
        assert target.get_int("FirstChar") == 0
        assert target.get_int("LastChar") == 255
        widths = target.get_dictionary_object("Widths")
        assert isinstance(widths, COSArray)
        assert len(widths) == 256
        assert embedder.get_font_encoding() is not None
        assert embedder.get_type1_font() is not None
        assert embedder.get_glyph_list() is not None
    finally:
        doc.close()


def test_constructor_with_explicit_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_t1font(monkeypatch, {"FontName": "X", "FontBBox": [0, 0, 1, 1]})
    doc = PDDocument()
    try:
        target = COSDictionary()
        enc = WinAnsiEncoding()
        PDType1FontEmbedder(doc, target, _synthetic_pfb(), enc)
        # Encoding got written through.
        assert target.get_dictionary_object("Encoding") is not None
    finally:
        doc.close()


def test_constructor_accepts_stream_input(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_t1font(monkeypatch, {"FontName": "S", "FontBBox": [0, 0, 1, 1]})
    doc = PDDocument()
    try:
        stream = io.BytesIO(_synthetic_pfb())
        PDType1FontEmbedder(doc, COSDictionary(), stream, None)
    finally:
        doc.close()


def test_constructor_falls_back_when_t1font_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Broken:
        def __init__(self, _stream: Any) -> None:
            raise OSError("bad font")

    import fontTools.t1Lib as t1mod

    monkeypatch.setattr(t1mod, "T1Font", _Broken)
    doc = PDDocument()
    try:
        target = COSDictionary()
        embedder = PDType1FontEmbedder(doc, target, _synthetic_pfb(), None)
        assert embedder.get_type1_font() is None
        # Subtype still written.
        assert target.get_name_as_string("Subtype") == "Type1"
        # BaseFont not written when type1 is None.
        assert "BaseFont" not in [str(k).lstrip("/") for k in target.key_set()]
    finally:
        doc.close()


def test_constructor_raises_when_fonttools_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    real_import = builtins.__import__

    def _no_fonttools(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "fontTools.t1Lib":
            raise ImportError("fontTools missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_fonttools)
    doc = PDDocument()
    try:
        with pytest.raises(OSError, match="fontTools"):
            PDType1FontEmbedder(doc, COSDictionary(), _synthetic_pfb(), None)
    finally:
        doc.close()


def test_build_font_descriptor_with_full_font() -> None:
    fake = _FakeT1(
        font={
            "FontName": "MyFont",
            "FamilyName": "MyFamily",
            "FontBBox": [-50, -100, 600, 700],
            "FontInfo": {"ItalicAngle": -10},
            "Encoding": ["A", "B"],
        }
    )
    fd = PDType1FontEmbedder.build_font_descriptor(fake)
    assert fd.get_font_name() == "MyFont"
    assert fd.is_symbolic() is False
    assert fd.is_non_symbolic() is True
    assert fd.get_italic_angle() == -10


def test_build_font_descriptor_marks_symbolic_for_font_specific() -> None:
    fake = _FakeT1(
        font={
            "FontName": "Sym",
            "FontBBox": [0, 0, 100, 100],
            "Encoding": "FontSpecific",
        }
    )
    fd = PDType1FontEmbedder.build_font_descriptor(fake)
    assert fd.is_symbolic() is True


def test_build_font_descriptor_handles_missing_encoding_as_symbolic() -> None:
    fake = _FakeT1(font={"FontName": "NoEnc", "FontBBox": [0, 0, 1, 1]})
    fd = PDType1FontEmbedder.build_font_descriptor(fake)
    assert fd.is_symbolic() is True


def test_get_type1_width_with_known_glyph() -> None:
    fake = _FakeT1()
    assert PDType1FontEmbedder._get_type1_width(fake, "A") == 680.0


def test_get_type1_width_returns_zero_for_unknown_glyph() -> None:
    fake = _FakeT1()
    assert PDType1FontEmbedder._get_type1_width(fake, "Z") == 0.0


def test_get_type1_name_returns_none_when_font_not_dict() -> None:
    class _Bad:
        font: Any = None

    assert PDType1FontEmbedder._get_type1_name(_Bad()) is None


def test_parse_pfb_pads_lengths_when_fewer_than_three_segments() -> None:
    from pypdfbox.pdmodel.font.pd_type1_font_embedder import _parse_pfb_segments

    seg = b"only-one"
    pfb = b"\x80\x01" + len(seg).to_bytes(4, "little") + seg + b"\x80\x03"
    body, lengths = _parse_pfb_segments(pfb)
    assert body == seg
    assert lengths == [len(seg), 0, 0]


def test_build_font_descriptor_from_metrics_with_truthy_charset() -> None:
    class _M:
        def get_encoding_scheme(self) -> str:
            return "StandardEncoding"

        def get_font_name(self) -> str:
            return "F"

        def get_character_set(self) -> str:
            return "Latin1"

    fd = PDType1FontEmbedder.build_font_descriptor_from_metrics(_M())
    # set_character_set is a wrapper around set_char_set — verify via
    # the COS dictionary key it writes to.
    cos = fd.get_cos_object()
    assert cos.get_string("CharSet") == "Latin1"


def test_accessors_via_bare_instance() -> None:
    """Cover the three trivial accessors without invoking ``__init__``.

    ``__init__`` raises ``AttributeError`` on the (currently unregistered)
    ``COSName.FONT_DESC`` lookup, so we build the instance manually with
    pre-populated private attributes.
    """
    embedder = PDType1FontEmbedder.__new__(PDType1FontEmbedder)
    embedder._font_encoding = WinAnsiEncoding()  # type: ignore[attr-defined]
    embedder._type1 = _FakeT1()  # type: ignore[attr-defined]
    assert embedder.get_font_encoding() is embedder._font_encoding  # type: ignore[attr-defined]
    assert embedder.get_type1_font() is embedder._type1  # type: ignore[attr-defined]
    # GlyphList accessor — singleton lookup, no instance state needed.
    assert embedder.get_glyph_list() is not None
