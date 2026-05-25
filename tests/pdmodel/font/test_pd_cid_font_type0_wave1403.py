"""Wave 1403 branch-closure tests for :class:`PDCIDFontType0`.

* ``458->462`` — ``generate_bounding_box`` when the embedded CFF program
  is present but its Top DICT carries no ``/FontBBox``
  (``program.get_property("FontBBox") is None``): the ``if cff_bbox is
  not None`` guard is false, so we fall through to ``super().
  get_bounding_box()``.
* ``614->616`` — ``get_glyph_path`` when the font is embedded and has a
  ``/CIDToGIDMap`` stream, but the decoded map does not cover the CID
  (``0 <= cid < len(cid_to_gid)`` is false), so the CID is left
  unremapped.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

# ---------- 458->462 : CFF program with no /FontBBox ----------


def test_generate_bounding_box_falls_through_when_cff_has_no_fontbbox() -> None:
    """Program present (descriptor branch skipped) but
    ``get_property("FontBBox")`` returns None — 458 false → 462."""

    class _NoBBoxProgram:
        def get_property(self, name: str) -> Any | None:
            return None  # No /FontBBox in the Top DICT.

    font = PDCIDFontType0(COSDictionary())
    # No descriptor with a non-zero /FontBBox, so we reach the program
    # branch; stub a program that yields no bbox.
    font.get_cff_font = lambda: _NoBBoxProgram()  # type: ignore[assignment,method-assign,return-value]
    result = font.generate_bounding_box()
    # Falls through to super().get_bounding_box() — with no descriptor
    # FontBBox the upstream fallback is None.
    assert result is None


# ---------- 614->616 : CIDToGIDMap stream too short for the CID ----------


def test_get_path_skips_remap_when_cid_out_of_map_range() -> None:
    """``get_path`` on an embedded font with a ``/CIDToGIDMap`` stream
    whose decoded length does not cover the requested CID:
    ``0 <= cid < len(cid_to_gid)`` is false (614 → 616), so the CID is
    used unremapped. With no CFF program the method then returns ``[]``.
    """
    font_dict = COSDictionary()
    # A 1-entry CIDToGIDMap stream (covers CID 0 only).
    cid_to_gid = COSStream()
    cid_to_gid.set_data(b"\x00\x05")  # CID 0 -> GID 5
    font_dict.set_item(COSName.get_pdf_name("CIDToGIDMap"), cid_to_gid)

    parent = PDType0Font()
    font = PDCIDFontType0(font_dict, parent)
    # Force the embedded + stream gate True, and a CID beyond the map.
    font.is_embedded = lambda: True  # type: ignore[assignment,method-assign,return-value]
    font.code_to_cid = lambda _code: 7  # type: ignore[assignment,method-assign,return-value]
    font.get_cff_font = lambda: None  # type: ignore[assignment,method-assign,return-value]
    # CID 7 is out of the 1-entry map -> 614 false -> 616; no program -> [].
    assert font.get_path(7) == []
