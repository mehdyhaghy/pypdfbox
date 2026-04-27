"""Round-out hand-written tests for ``PDFontFactory.create_font``.

Companion to the longer-standing ``test_font_factory_dispatch.py`` and
``test_pd_font_factory_parity.py`` suites — focuses on the wave-37
additions:

* ``/CIDFontType2`` top-level dispatch (only when the descriptor carries
  an embedded TrueType ``/FontFile2`` stream).
* Missing ``/Subtype`` falls back to :class:`PDType1Font` with a logged
  warning, mirroring upstream ``PDFontFactory.createFont``.
* Unknown ``/Subtype`` values stay non-fatal: a warning is logged and
  the factory returns ``None`` (callers decide whether to skip).

These behaviours are also exercised in
``upstream/test_pd_font_factory.py`` against the JUnit cases ported from
``PDFontFactoryTest.java``; this file covers the pypdfbox-specific
contract surface (logging strings, ``PDCIDFontType2`` round-trip, the
``resource_cache`` parity kwarg interaction with the new arms).
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font.pd_cid_font import PDCIDFont
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

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


# ---------- CIDFontType2 dispatch (FontFile2 present) ----------


def test_cid_font_type2_with_font_file2_dispatches_to_pd_cid_font_type2() -> None:
    raw = _make_font_dict("CIDFontType2")
    _attach_font_file2(raw)
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDCIDFontType2)
    assert isinstance(out, PDCIDFont)
    # Identity preservation: the wrapper holds the same dict the caller
    # passed in (no defensive copy).
    assert out.get_cos_object() is raw


def test_cid_font_type2_with_font_file2_via_create_cid_font() -> None:
    raw = _make_font_dict("CIDFontType2")
    _attach_font_file2(raw)
    out = PDFontFactory.create_cid_font(raw)
    assert isinstance(out, PDCIDFontType2)


def test_cid_font_type2_without_descriptor_returns_none() -> None:
    # Bare /CIDFontType2 without any FontDescriptor is reached via the
    # /Type0 descendant path; the top-level factory must return None so
    # callers don't double-wrap.
    raw = _make_font_dict("CIDFontType2")
    assert PDFontFactory.create_font(raw) is None


def test_cid_font_type2_with_descriptor_but_no_font_file2_returns_none() -> None:
    raw = _make_font_dict("CIDFontType2")
    raw.set_item(_FONT_DESCRIPTOR, COSDictionary())
    assert PDFontFactory.create_font(raw) is None


def test_cid_font_type2_with_font_file3_only_returns_none() -> None:
    # /FontFile3 (CFF / OpenType) doesn't satisfy the /FontFile2 marker
    # we use to disambiguate top-level CIDFontType2 — must still defer
    # to the descendant path.
    raw = _make_font_dict("CIDFontType2")
    descriptor = COSDictionary()
    ff3 = COSStream()
    ff3.set_name(_SUBTYPE, "OpenType")
    descriptor.set_item(_FONT_FILE3, ff3)
    raw.set_item(_FONT_DESCRIPTOR, descriptor)
    assert PDFontFactory.create_font(raw) is None


def test_cid_font_type2_with_font_file2_accepts_resource_cache_kwarg() -> None:
    # Signature parity: the resource_cache kwarg is accepted but ignored
    # — make sure the new dispatch arm honours that.
    raw = _make_font_dict("CIDFontType2")
    _attach_font_file2(raw)
    out = PDFontFactory.create_font(raw, resource_cache=object())
    assert isinstance(out, PDCIDFontType2)


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
    # Message must mention the subtype is missing/None and that we're
    # falling back to Type1, so log scrapers can spot malformed inputs.
    joined = "\n".join(rec.message for rec in caplog.records)
    assert "subtype" in joined.lower()
    assert "type1" in joined.lower()


def test_missing_subtype_via_create_simple_font_returns_pd_type1_font() -> None:
    # Type1 fallback is a PDSimpleFont, so create_simple_font must accept it.
    raw = _make_font_dict(None)
    out = PDFontFactory.create_simple_font(raw)
    assert isinstance(out, PDType1Font)


def test_missing_subtype_via_create_cid_font_returns_none() -> None:
    # Type1 fallback is NOT a PDCIDFont, so create_cid_font filters it out.
    raw = _make_font_dict(None)
    assert PDFontFactory.create_cid_font(raw) is None


# ---------- unknown /Subtype: warn-and-skip ----------


def test_unknown_subtype_returns_none_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    raw = _make_font_dict("Bogus")
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.font.pd_font_factory"):
        out = PDFontFactory.create_font(raw)
    assert out is None
    joined = "\n".join(rec.message for rec in caplog.records)
    assert "Bogus" in joined


def test_empty_subtype_string_returns_none() -> None:
    # Empty /Subtype name is structurally an unknown subtype, not a
    # missing one — we don't fall back to Type1 for it.
    raw = _make_font_dict("")
    assert PDFontFactory.create_font(raw) is None


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


def test_bare_cid_font_type0_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    # Bare /CIDFontType0 is a *known* subtype that's just dispatched via
    # the descendant path — must not emit the "invalid subtype" warning.
    raw = _make_font_dict("CIDFontType0")
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.font.pd_font_factory"):
        out = PDFontFactory.create_font(raw)
    assert out is None
    assert caplog.records == []


def test_bare_cid_font_type2_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    raw = _make_font_dict("CIDFontType2")
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.font.pd_font_factory"):
        out = PDFontFactory.create_font(raw)
    assert out is None
    assert caplog.records == []
