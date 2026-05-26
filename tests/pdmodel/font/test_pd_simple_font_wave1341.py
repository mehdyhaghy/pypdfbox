"""Wave 1341 coverage-boost tests for ``pypdfbox.pdmodel.font.pd_simple_font``.

Targets the still-uncovered branches in the wave-1332 snapshot:

* :meth:`PDSimpleFont.read_encoding` ``Unknown encoding`` warning path
  (lines 317-318) and the symbolic-with-no-valid-base ``/Differences``
  branch that calls ``read_encoding_from_font`` (line 332).
* The abstract-method ``NotImplementedError`` raises for
  :meth:`read_encoding_from_font`, :meth:`get_path`, :meth:`has_glyph`
  and :meth:`get_font_box_font` (lines 356/369/382/396).
* :meth:`get_standard14_width` ``nbspace`` -> ``space`` and ``sfthyphen``
  -> ``hyphen`` substitutions (lines 423/425).
* :meth:`will_be_subset` returning ``False`` (line 608) plus the
  ``NotImplementedError`` raised by :meth:`add_to_subset` /
  :meth:`subset` on non-TrueType simple fonts (lines 617/628).
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.font.encoding import (
    DictionaryEncoding,
    WinAnsiEncoding,
)
from pypdfbox.pdmodel.font.pd_font_descriptor import (
    FLAG_SYMBOLIC,
    PDFontDescriptor,
)
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont

# ---------- read_encoding: Unknown encoding warning path ------------------


def test_read_encoding_unknown_named_encoding_warns_and_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unrecognised name -> warning + read_encoding_from_font fallback."""
    font = PDType1Font()
    # Standard 14 helvetica so the read_encoding_from_font fallback resolves
    # to WinAnsiEncoding rather than None.
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("BogusEncodingName"),
    )
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.font.pd_simple_font"):
        font.read_encoding()
    # Fell back to whatever read_encoding_from_font returns (Standard14
    # Helvetica -> WinAnsiEncoding, the Acrobat default for the unembedded
    # Latin core fonts; verified against the live PDFBox oracle).
    assert isinstance(font.get_encoding_typed(), WinAnsiEncoding)
    assert any("Unknown encoding" in rec.getMessage() for rec in caplog.records)


# ---------- read_encoding: symbolic + dictionary encoding without valid base


def test_read_encoding_dict_symbolic_no_valid_base_invokes_built_in() -> None:
    """A ``/Differences`` dict whose ``/BaseEncoding`` is missing/unknown +
    symbolic descriptor flag -> ``read_encoding_from_font`` is consulted
    to supply the ``built_in`` argument to the ``DictionaryEncoding``.
    """
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    # Mark the font as symbolic via /FontDescriptor /Flags.
    descriptor_dict = COSDictionary()
    descriptor = PDFontDescriptor(descriptor_dict)
    descriptor.set_flags(FLAG_SYMBOLIC)
    font.get_cos_object().set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor_dict
    )
    # /Encoding is a dict with NO /BaseEncoding -> read_encoding_from_font
    # is called for the built-in.
    enc = COSDictionary()
    font.get_cos_object().set_item(COSName.get_pdf_name("Encoding"), enc)
    font.read_encoding()
    assert isinstance(font.get_encoding_typed(), DictionaryEncoding)


# ---------- abstract NotImplementedError raises ---------------------------


class _ConcreteForAbstractTests(PDSimpleFont):
    """Subclass that does not override any abstract method, so the
    base-class ``NotImplementedError`` raises stay reachable.
    """

    def get_name(self) -> str:
        return "ConcreteForAbstractTests"


def test_read_encoding_from_font_raises_not_implemented_on_base() -> None:
    font = _ConcreteForAbstractTests()
    with pytest.raises(NotImplementedError, match="read_encoding_from_font"):
        font.read_encoding_from_font()


def test_get_path_raises_not_implemented_on_base() -> None:
    font = _ConcreteForAbstractTests()
    with pytest.raises(NotImplementedError, match="get_path"):
        font.get_path("A")


def test_has_glyph_raises_not_implemented_on_base() -> None:
    font = _ConcreteForAbstractTests()
    with pytest.raises(NotImplementedError, match="has_glyph"):
        font.has_glyph("A")


def test_get_font_box_font_raises_not_implemented_on_base() -> None:
    font = _ConcreteForAbstractTests()
    with pytest.raises(NotImplementedError, match="get_font_box_font"):
        font.get_font_box_font()


# ---------- get_standard14_width: nbspace / sfthyphen substitutions -------


class _StubAFM:
    """Minimal stand-in for ``FontMetrics`` exposing ``get_character_width``."""

    def __init__(self) -> None:
        self.requested: list[str] = []

    def get_character_width(self, name: str) -> float:
        self.requested.append(name)
        return {"space": 250.0, "hyphen": 333.0}.get(name, 0.0)


class _StubEncoding:
    """Returns whatever name was wired in -- bypasses the real Encoding
    machinery so we can drive the nbspace / sfthyphen rewrites
    deterministically.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    def get_name(self, code: int) -> str:  # noqa: ARG002
        return self._name


def test_get_standard14_width_nbspace_substitutes_to_space() -> None:
    """``nbspace`` is missing from the Adobe AFMs but typographically maps
    to ``space`` (PDFBOX-4944) -- ``get_standard14_width`` must rewrite.
    """
    afm = _StubAFM()
    font = PDType1Font()
    font.get_standard14_afm = lambda: afm  # type: ignore[method-assign]
    font.get_encoding_typed = lambda: _StubEncoding("nbspace")  # type: ignore[method-assign]
    assert font.get_standard14_width(0o240) == 250.0
    assert "space" in afm.requested
    assert "nbspace" not in afm.requested


def test_get_standard14_width_sfthyphen_substitutes_to_hyphen() -> None:
    """``sfthyphen`` is missing from the Adobe AFMs but typographically
    maps to ``hyphen`` (PDFBOX-5115).
    """
    afm = _StubAFM()
    font = PDType1Font()
    font.get_standard14_afm = lambda: afm  # type: ignore[method-assign]
    font.get_encoding_typed = lambda: _StubEncoding("sfthyphen")  # type: ignore[method-assign]
    assert font.get_standard14_width(0o255) == 333.0
    assert "hyphen" in afm.requested
    assert "sfthyphen" not in afm.requested


# ---------- subsetting NotImplementedError raises -------------------------


def test_will_be_subset_returns_false_on_base() -> None:
    """Mirrors upstream ``PDSimpleFont.willBeSubset``: only the
    ``PDTrueTypeFont`` override flips this -- the base class always
    returns ``False``. ``PDType1Font`` / ``PDType3Font`` override too so
    we drive the base implementation directly.
    """
    assert PDSimpleFont.will_be_subset(_ConcreteForAbstractTests()) is False


def test_add_to_subset_raises_not_implemented_on_base() -> None:
    """The base ``add_to_subset`` raises; concrete subclasses override."""
    font = _ConcreteForAbstractTests()
    with pytest.raises(NotImplementedError, match="subsetting is not supported"):
        PDSimpleFont.add_to_subset(font, 65)


def test_subset_raises_not_implemented_on_base() -> None:
    """The base ``subset`` raises; concrete subclasses override."""
    font = _ConcreteForAbstractTests()
    with pytest.raises(NotImplementedError, match="subsetting is not supported"):
        PDSimpleFont.subset(font)
