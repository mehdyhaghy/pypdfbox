"""Wave 1403 branch-closure tests for :class:`PDType1FontEmbedder`.

* ``242->248`` — ``build_font_descriptor_from_metrics`` when
  ``metrics.get_family_name()`` returns a *falsy* value: the
  ``if family:`` guard is false, so no ``/FontFamily`` is written and we
  fall through to the symbolic-flag assignment.
* ``126->129`` — the constructor's ``if base_font:`` guard is false when
  ``_get_type1_name`` returns a falsy name (the parsed Type 1 dict has no
  ``/FontName``), so no ``/BaseFont`` is set.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_type1_font_embedder import PDType1FontEmbedder
from pypdfbox.pdmodel.pd_document import PDDocument


@pytest.fixture(scope="module", autouse=True)
def _install_missing_cos_name_constants() -> None:
    for attr, raw in (
        ("BASE_FONT", "BaseFont"),
        ("FONT_DESC", "FontDescriptor"),
        ("ENCODING", "Encoding"),
    ):
        if not hasattr(COSName, attr):
            setattr(COSName, attr, COSName.get_pdf_name(raw))


# ---------- 242->248 : falsy family name skips /FontFamily ----------


def test_build_font_descriptor_from_metrics_skips_family_when_empty() -> None:
    class _Metrics:
        def get_encoding_scheme(self) -> str:
            return "AdobeStandardEncoding"

        def get_font_name(self) -> str:
            return "NoFamilyFont"

        def get_family_name(self) -> str:
            # Falsy -> 242 false -> 248 (no /FontFamily emitted).
            return ""

    fd = PDType1FontEmbedder.build_font_descriptor_from_metrics(_Metrics())
    assert fd.get_font_name() == "NoFamilyFont"
    assert fd.get_cos_object().get_item(COSName.get_pdf_name("FontFamily")) is None
    # The fall-through path still set the non-symbolic flag.
    assert fd.is_non_symbolic() is True


# ---------- 126->129 : falsy base font name skips /BaseFont ----------


class _FakeGlyph:
    def __init__(self, width: float = 0.0) -> None:
        self.width = width


class _FakeGlyphSet:
    def __getitem__(self, name: str) -> _FakeGlyph:
        raise KeyError(name)


def _synthetic_pfb() -> bytes:
    seg1 = b"%!PS-AdobeFont"
    seg2 = b"binary-segment"
    seg3 = b"end"
    return (
        b"\x80\x01" + len(seg1).to_bytes(4, "little") + seg1
        + b"\x80\x02" + len(seg2).to_bytes(4, "little") + seg2
        + b"\x80\x01" + len(seg3).to_bytes(4, "little") + seg3
        + b"\x80\x03"
    )


def test_constructor_skips_base_font_when_type1_name_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parsed Type 1 font whose dict carries no ``/FontName`` makes
    ``_get_type1_name`` return ``None`` — the ``if base_font:`` guard is
    false (126 -> 129): no ``/BaseFont`` is written, but the descriptor
    and widths are still populated."""

    class _Stub:
        def __init__(self, _stream: Any) -> None:
            # No "FontName" key -> _get_type1_name returns None (falsy).
            self.font = {"FontBBox": [0, 0, 1, 1]}

        def getGlyphSet(self) -> _FakeGlyphSet:  # noqa: N802 - upstream API
            return _FakeGlyphSet()

    import fontTools.t1Lib as t1mod

    monkeypatch.setattr(t1mod, "T1Font", _Stub)

    doc = PDDocument()
    try:
        dict_ = COSDictionary()
        PDType1FontEmbedder(doc, dict_, _synthetic_pfb(), None)
        # /BaseFont must be absent because base_font was falsy.
        assert dict_.get_item(COSName.BASE_FONT) is None
        # Sanity: the descriptor still got attached.
        assert dict_.get_item(COSName.FONT_DESC) is not None
    finally:
        doc.close()
