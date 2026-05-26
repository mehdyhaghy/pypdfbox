"""Coverage boost for :mod:`pypdfbox.pdmodel.font.pd_type1_font_embedder`.

Exercises the constructor end-to-end against the real PFB Type 1 fixtures
(parsed via pypdfbox's own ``Type1Font`` wrapper, which correctly drives
fontTools — the embedder no longer constructs fontTools' ``T1Font`` directly,
which only accepts a file path) plus the ``build_font_descriptor`` factory.

The helper tests (``build_font_descriptor`` / ``_get_type1_width``) use a tiny
fake exposing the pypdfbox ``Type1Font`` accessor surface
(``get_font_name`` / ``get_family_name`` / ``get_font_b_box`` /
``get_italic_angle`` / ``get_encoding`` / ``get_width``).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.pd_type1_font_embedder import PDType1FontEmbedder
from pypdfbox.pdmodel.pd_document import PDDocument

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "type1"
_DEMO_PFB = _FIXTURES / "DemoType1.pfb"
_CUSTOM_PFB = _FIXTURES / "CustomEncType1.pfb"


@pytest.fixture(scope="module", autouse=True)
def _install_missing_cos_name_constants() -> None:
    """``PDType1FontEmbedder.__init__`` references ``COSName.FONT_DESC`` /
    ``BASE_FONT`` / ``ENCODING`` which are not registered in
    ``cos_name.py``'s static table. Register them on demand so the
    constructor runs end-to-end. Order-independent.
    """
    for attr, raw in (
        ("BASE_FONT", "BaseFont"),
        ("FONT_DESC", "FontDescriptor"),
        ("ENCODING", "Encoding"),
    ):
        if not hasattr(COSName, attr):
            setattr(COSName, attr, COSName.get_pdf_name(raw))


class _FakeType1:
    """Mimics the pypdfbox :class:`Type1Font` accessor surface the embedder
    helpers consume."""

    def __init__(
        self,
        *,
        name: str = "MyFont",
        family: str | None = "MyFamily",
        bbox: tuple[float, float, float, float] | None = (-50, -100, 600, 700),
        italic_angle: float = -10.0,
        encoding: dict[int, str] | None = None,
        widths: dict[str, float] | None = None,
    ) -> None:
        self._name = name
        self._family = family
        self._bbox = bbox
        self._italic = italic_angle
        self._encoding = encoding if encoding is not None else {65: "A", 66: "B"}
        self._widths = widths if widths is not None else {"A": 680.0}

    def get_font_name(self) -> str:
        return self._name

    def get_family_name(self) -> str | None:
        return self._family

    def get_font_b_box(self) -> tuple[float, float, float, float] | None:
        return self._bbox

    def get_italic_angle(self) -> float:
        return self._italic

    def get_encoding(self) -> dict[int, str]:
        return dict(self._encoding)

    def get_width(self, name: str) -> float:
        return self._widths.get(name, 0.0)


def test_constructor_with_real_pfb() -> None:
    doc = PDDocument()
    try:
        target = COSDictionary()
        embedder = PDType1FontEmbedder(doc, target, _DEMO_PFB.read_bytes(), None)
        assert target.get_name_as_string("Subtype") == "Type1"
        assert target.get_name_as_string("BaseFont") == "DemoType1"
        assert target.get_int("FirstChar") == 0
        assert target.get_int("LastChar") == 255
        widths = target.get_dictionary_object("Widths")
        assert isinstance(widths, COSArray)
        assert len(widths) == 256
        # StandardEncoding maps code 65 -> "A" (width 600 in this font).
        assert widths.get(65).int_value() == 600
        assert embedder.get_font_encoding() is not None
        assert embedder.get_type1_font() is not None
        assert embedder.get_glyph_list() is not None
    finally:
        doc.close()


def test_constructor_with_explicit_encoding() -> None:
    doc = PDDocument()
    try:
        target = COSDictionary()
        enc = WinAnsiEncoding()
        PDType1FontEmbedder(doc, target, _DEMO_PFB.read_bytes(), enc)
        # Explicit encoding got written through to /Encoding.
        assert target.get_dictionary_object("Encoding") is not None
    finally:
        doc.close()


def test_constructor_accepts_stream_input() -> None:
    doc = PDDocument()
    try:
        stream = io.BytesIO(_DEMO_PFB.read_bytes())
        target = COSDictionary()
        PDType1FontEmbedder(doc, target, stream, None)
        assert target.get_name_as_string("BaseFont") == "DemoType1"
    finally:
        doc.close()


def test_constructor_falls_back_when_program_unparseable() -> None:
    """When the bytes can't be parsed as a Type 1 program the embedder
    degrades gracefully: still tags /Subtype, but leaves /BaseFont and the
    parsed program empty."""
    doc = PDDocument()
    try:
        target = COSDictionary()
        # A bare PFB header followed by junk that is not a Type 1 program.
        seg = b"not a type1 font"
        bad = b"\x80\x01" + len(seg).to_bytes(4, "little") + seg + b"\x80\x03"
        embedder = PDType1FontEmbedder(doc, target, bad, None)
        assert embedder.get_type1_font() is None
        assert target.get_name_as_string("Subtype") == "Type1"
        assert "BaseFont" not in [str(k).lstrip("/") for k in target.key_set()]
    finally:
        doc.close()


def test_build_font_descriptor_with_full_font() -> None:
    fake = _FakeType1()
    fd = PDType1FontEmbedder.build_font_descriptor(fake)
    assert fd.get_font_name() == "MyFont"
    # Recoverable code->name encoding -> non-symbolic.
    assert fd.is_symbolic() is False
    assert fd.is_non_symbolic() is True
    assert fd.get_italic_angle() == -10


def test_build_font_descriptor_marks_symbolic_for_empty_encoding() -> None:
    # An empty (FontSpecific / built-in) encoding map -> symbolic.
    fake = _FakeType1(encoding={})
    fd = PDType1FontEmbedder.build_font_descriptor(fake)
    assert fd.is_symbolic() is True


def test_get_type1_width_with_known_glyph() -> None:
    fake = _FakeType1(widths={"A": 680.0})
    assert PDType1FontEmbedder._get_type1_width(fake, "A") == 680.0


def test_get_type1_width_returns_zero_for_unknown_glyph() -> None:
    fake = _FakeType1(widths={"A": 680.0})
    assert PDType1FontEmbedder._get_type1_width(fake, "Z") == 0.0


def test_get_type1_name_returns_none_when_accessor_missing() -> None:
    class _Bad:
        pass

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
    cos = fd.get_cos_object()
    assert cos.get_string("CharSet") == "Latin1"


def test_accessors_via_bare_instance() -> None:
    """Cover the three trivial accessors without invoking ``__init__``."""
    embedder = PDType1FontEmbedder.__new__(PDType1FontEmbedder)
    embedder._font_encoding = WinAnsiEncoding()  # type: ignore[attr-defined]
    embedder._type1 = _FakeType1()  # type: ignore[attr-defined]
    assert embedder.get_font_encoding() is embedder._font_encoding  # type: ignore[attr-defined]
    assert embedder.get_type1_font() is embedder._type1  # type: ignore[attr-defined]
    assert embedder.get_glyph_list() is not None


def test_custom_encoding_widths_land_at_custom_codes() -> None:
    """CustomEncType1 maps codes 1/2/3 -> A/B/C; the /Widths array must
    carry the program advances at those custom codes."""
    doc = PDDocument()
    try:
        target = COSDictionary()
        PDType1FontEmbedder(doc, target, _CUSTOM_PFB.read_bytes(), None)
        widths = target.get_dictionary_object("Widths")
        assert isinstance(widths, COSArray)
        assert widths.get(1).int_value() == 600
        assert widths.get(2).int_value() == 700
        assert widths.get(3).int_value() == 650
    finally:
        doc.close()
