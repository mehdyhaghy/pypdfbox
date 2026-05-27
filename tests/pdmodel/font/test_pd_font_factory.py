"""Round-out hand-written tests for ``PDFontFactory.create_font``.

Companion to the longer-standing ``test_font_factory_dispatch.py`` and
``test_pd_font_factory_parity.py`` suites — focuses on the wave-37
additions:

* A top-level ``/CIDFontType2`` (or ``/CIDFontType0``) raises ``OSError``
  — a CIDFont is only legal as a ``/Type0`` descendant (upstream raises
  IOException "Type N descendant font not allowed").
* Missing OR unknown ``/Subtype`` falls back to :class:`PDType1Font` with
  a logged warning, mirroring upstream ``PDFontFactory.createFont``.

These behaviours match the live PDFBox 3.0.7 oracle (see
``oracle/test_font_factory_oracle.py``); this file covers the
pypdfbox-specific contract surface (logging strings, the
``resource_cache`` parity kwarg interaction).
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_mm_type1_font import PDMMType1Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont

_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_FONT_FILE2: COSName = COSName.get_pdf_name("FontFile2")
_FONT_FILE3: COSName = COSName.get_pdf_name("FontFile3")


def _make_font_dict(subtype: str | None) -> COSDictionary:
    raw = COSDictionary()
    if subtype is not None:
        raw.set_name(_SUBTYPE, subtype)
    return raw


def _attach_font_file2(font_dict: COSDictionary) -> COSStream:
    """Attach a /FontDescriptor with an empty /FontFile2 stream — that's
    enough to mark the font as carrying an embedded TrueType program for
    the purpose of factory dispatch."""
    descriptor = COSDictionary()
    stream = COSStream()
    descriptor.set_item(_FONT_FILE2, stream)
    font_dict.set_item(_FONT_DESCRIPTOR, descriptor)
    return stream


# ---------- top-level CIDFont subtypes raise (not allowed) ----------


def test_top_level_cid_font_type2_with_font_file2_raises() -> None:
    # A CIDFont is only legal as a /Type0 descendant. Even with an
    # embedded /FontFile2, a *top-level* /CIDFontType2 dict raises.
    raw = _make_font_dict("CIDFontType2")
    _attach_font_file2(raw)
    with pytest.raises(OSError, match="Type 2 descendant font not allowed"):
        PDFontFactory.create_font(raw)


def test_top_level_cid_font_type2_via_create_cid_font_raises() -> None:
    raw = _make_font_dict("CIDFontType2")
    _attach_font_file2(raw)
    with pytest.raises(OSError, match="Type 2 descendant font not allowed"):
        PDFontFactory.create_cid_font(raw)


def test_top_level_cid_font_type2_bare_raises() -> None:
    raw = _make_font_dict("CIDFontType2")
    with pytest.raises(OSError, match="Type 2 descendant font not allowed"):
        PDFontFactory.create_font(raw)


def test_top_level_cid_font_type0_bare_raises() -> None:
    raw = _make_font_dict("CIDFontType0")
    with pytest.raises(OSError, match="Type 0 descendant font not allowed"):
        PDFontFactory.create_font(raw)


def test_top_level_cid_font_type2_raise_honours_resource_cache_kwarg() -> None:
    # Signature parity: the resource_cache kwarg is accepted; the raise
    # behaviour is unaffected by it.
    raw = _make_font_dict("CIDFontType2")
    _attach_font_file2(raw)
    with pytest.raises(OSError, match="Type 2 descendant font not allowed"):
        PDFontFactory.create_font(raw, resource_cache=object())


# ---------- missing /Subtype fallback to PDType1Font ----------


def test_missing_subtype_falls_back_to_pd_type1_font() -> None:
    # Mirrors PDFBox: missing /Subtype on a font dictionary is treated as
    # /Type1 with a logged warning, rather than failing outright.
    raw = _make_font_dict(None)
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1Font)
    assert out.get_cos_object() is raw


def test_missing_subtype_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    raw = _make_font_dict(None)
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.font.pd_font_factory"):
        PDFontFactory.create_font(raw)
    # Mirrors upstream PDFontFactory: "Invalid font subtype 'null'" for a
    # missing /Subtype (the warning lets log scrapers spot malformed input;
    # the actual fallback to PDType1Font is asserted separately above).
    joined = "\n".join(rec.message for rec in caplog.records)
    assert "subtype" in joined.lower()
    assert "null" in joined.lower()


def test_missing_subtype_via_create_simple_font_returns_pd_type1_font() -> None:
    # Type1 fallback is a PDSimpleFont, so create_simple_font must accept it.
    raw = _make_font_dict(None)
    out = PDFontFactory.create_simple_font(raw)
    assert isinstance(out, PDType1Font)


def test_missing_subtype_via_create_cid_font_returns_none() -> None:
    # Type1 fallback is NOT a PDCIDFont, so create_cid_font filters it out.
    raw = _make_font_dict(None)
    assert PDFontFactory.create_cid_font(raw) is None


# ---------- unknown /Subtype: warn-and-fall-back-to-Type1 ----------


def test_unknown_subtype_falls_back_to_type1_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Upstream PDFontFactory logs a warning and falls back to PDType1Font
    # for any unrecognised /Subtype (so text extraction can still proceed
    # with Standard 14 metrics).
    raw = _make_font_dict("Bogus")
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.font.pd_font_factory"):
        out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1Font)
    joined = "\n".join(rec.message for rec in caplog.records)
    assert "Bogus" in joined


def test_empty_subtype_string_falls_back_to_type1() -> None:
    # Empty /Subtype name is an unknown subtype — upstream still falls
    # back to PDType1Font (the unknown-subtype arm).
    raw = _make_font_dict("")
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1Font)


# ---------- regression: known-subtype paths don't log spurious warnings ----------


@pytest.mark.parametrize(
    "subtype",
    ["Type0", "Type1", "TrueType", "Type3", "MMType1"],
)
def test_known_subtype_does_not_warn(
    caplog: pytest.LogCaptureFixture, subtype: str
) -> None:
    raw = _make_font_dict(subtype)
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.font.pd_font_factory"):
        PDFontFactory.create_font(raw)
    assert caplog.records == []


def test_bare_cid_font_type0_raises_without_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # A top-level /CIDFontType0 is not allowed: upstream raises rather
    # than logging the "invalid subtype" warning (that warning is only
    # for truly unknown subtypes).
    raw = _make_font_dict("CIDFontType0")
    with (
        caplog.at_level(
            logging.WARNING, logger="pypdfbox.pdmodel.font.pd_font_factory"
        ),
        pytest.raises(OSError, match="Type 0 descendant font not allowed"),
    ):
        PDFontFactory.create_font(raw)
    assert caplog.records == []


def test_bare_cid_font_type2_raises_without_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw = _make_font_dict("CIDFontType2")
    with (
        caplog.at_level(
            logging.WARNING, logger="pypdfbox.pdmodel.font.pd_font_factory"
        ),
        pytest.raises(OSError, match="Type 2 descendant font not allowed"),
    ):
        PDFontFactory.create_font(raw)
    assert caplog.records == []


# ---------- MMType1 + /FontFile3 (Type1C-marked CFF program) ----------


def _attach_font_file3_with_subtype(font_dict: COSDictionary, subtype: str) -> COSStream:
    """Attach a /FontDescriptor with an empty /FontFile3 stream of the
    requested /Subtype. Mirrors the upstream test fixture for routing
    /MMType1 with a CFF-marked FontFile3 to PDType1CFont.
    """
    descriptor = COSDictionary()
    stream = COSStream()
    stream.set_name(_SUBTYPE, subtype)
    descriptor.set_item(_FONT_FILE3, stream)
    font_dict.set_item(_FONT_DESCRIPTOR, descriptor)
    return stream


def test_mm_type1_with_type1c_font_file3_routes_to_pd_type1c_font() -> None:
    # Mirrors upstream PDFontFactory.createFont: /MMType1 with a
    # /FontDescriptor /FontFile3 of /Subtype /Type1C is a CFF-backed
    # multiple-master Type 1 font and must dispatch to PDType1CFont.
    raw = _make_font_dict("MMType1")
    _attach_font_file3_with_subtype(raw, "Type1C")
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1CFont)


def test_mm_type1_without_font_file3_still_returns_pd_mm_type1_font() -> None:
    # Bare /MMType1 (no embedded program at all) keeps the existing
    # PDMMType1Font dispatch path.
    raw = _make_font_dict("MMType1")
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDMMType1Font)
    assert not isinstance(out, PDType1CFont)


def test_mm_type1_with_non_type1c_font_file3_routes_to_pd_type1c_font() -> None:
    # Upstream checks only containsKey(FONT_FILE3) for the /MMType1 arm —
    # a /FontFile3 of any (or no) /Subtype routes to PDType1CFont.
    raw = _make_font_dict("MMType1")
    _attach_font_file3_with_subtype(raw, "OpenType")
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1CFont)
