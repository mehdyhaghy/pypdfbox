"""Hand-written pins for the NON-EMBEDDED CIDFontType2 model-layer contract
(``/FontFile2``-less substitute path). Wave 1488.

These mirror the API exercised by the live oracle in
``oracle/test_cid_substitute_gid_oracle.py`` but need no Java — they lock the
machine-independent behaviour of a CIDFontType2 whose descriptor carries no
embedded font program:

* ``is_embedded()`` is ``False`` once the program is absent,
* ``get_true_type_font()`` / ``get_open_type_font()`` return ``None``,
* ``is_damaged()`` is ``False`` (nothing to parse, nothing damaged),
* width / metric lookups fall back to the ``/W`` + ``/DW`` parent path,
* ``cid_to_gid`` falls through to the identity ``cid`` (the substitute GID is
  the renderer's responsibility — documented divergence from upstream).
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_resources import PDResources

_FONT = (
    Path(__file__).resolve().parents[3]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "DejaVuSans.ttf"
)

_CONTENT_CIDS = (3, 5, 7, 9)


def _build_non_embedded(out: Path) -> Path:
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, 200.0, 60.0))
        doc.add_page(page)
        font = PDType0Font.load(doc, str(_FONT), embed_subset=False)
        descendant = font.get_descendant_font()
        assert isinstance(descendant, PDCIDFontType2)
        descendant.get_font_descriptor().set_font_file2(None)
        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)
        codes = b"".join(struct.pack(">H", c) for c in _CONTENT_CIDS)
        cs = COSStream()
        cs.set_data(
            b"BT\n/F1 24 Tf\n10 20 Td\n<%s> Tj\nET\n"
            % codes.hex().encode("ascii")
        )
        page.set_contents(cs)
        doc.save(str(out))
    finally:
        doc.close()
    return out


def _reload(pdf_path: Path) -> tuple[PDDocument, PDType0Font, PDCIDFontType2]:
    doc = PDDocument.load(pdf_path)
    for page in doc.get_pages():
        res = page.get_resources()
        if res is None:
            continue
        for name in res.get_font_names():
            font = res.get_font(name)
            if not isinstance(font, PDType0Font):
                continue
            descendant = font.get_descendant_font()
            if isinstance(descendant, PDCIDFontType2):
                return doc, font, descendant
    doc.close()
    raise AssertionError("no CIDFontType2 descendant in fixture")


def test_strip_fontfile2_makes_non_embedded(tmp_path: Path) -> None:
    fixture = _build_non_embedded(tmp_path / "sub.pdf")
    assert b"FontFile2" not in fixture.read_bytes()
    doc, font, descendant = _reload(fixture)
    try:
        assert not font.is_embedded()
        assert not descendant.is_embedded()
    finally:
        doc.close()


def test_no_embedded_program_accessors_return_none(tmp_path: Path) -> None:
    fixture = _build_non_embedded(tmp_path / "sub.pdf")
    doc, _font, descendant = _reload(fixture)
    try:
        assert descendant.get_true_type_font() is None
        assert descendant.get_open_type_font() is None
        assert descendant.get_cmap_lookup() is None
        # Not embedded => not damaged (nothing to parse).
        assert descendant.is_damaged() is False
        assert descendant.is_open_type_post_script() is False
    finally:
        doc.close()


def test_cid_to_gid_falls_through_to_identity(tmp_path: Path) -> None:
    """Documented divergence: with no embedded program the model-layer GID is
    the identity ``cid`` (the substitute-font GID resolution lives in the
    renderer). Negative CIDs are still clamped to 0."""
    fixture = _build_non_embedded(tmp_path / "sub.pdf")
    doc, _font, descendant = _reload(fixture)
    try:
        for cid in (0, 3, 5, 7, 9, 60000, 65535):
            assert descendant.cid_to_gid(cid) == cid
            assert descendant.code_to_gid(cid) == cid
        assert descendant.cid_to_gid(-1) == 0
    finally:
        doc.close()


def test_width_lookup_uses_w_and_dw(tmp_path: Path) -> None:
    """Advances come from the ``/W`` array (and ``/DW`` for uncovered CIDs),
    not from a (missing) embedded ``hmtx``."""
    fixture = _build_non_embedded(tmp_path / "sub.pdf")
    doc, font, descendant = _reload(fixture)
    try:
        # Covered CIDs have positive, finite /W advances.
        for cid in _CONTENT_CIDS:
            w = font.get_width(cid)
            assert w > 0.0
        # An uncovered high CID falls back to /DW (default 1000).
        assert font.get_width(65535) == pytest.approx(
            descendant.get_default_width()
        )
        # get_width_from_font has no embedded program to read -> 0.0.
        assert descendant.get_width_from_font(3) == 0.0
    finally:
        doc.close()


def test_average_and_matrix_fall_back_without_program(tmp_path: Path) -> None:
    fixture = _build_non_embedded(tmp_path / "sub.pdf")
    doc, _font, descendant = _reload(fixture)
    try:
        # No embedded program => font matrix defaults to the 1000-unit em.
        assert descendant.get_font_matrix() == [
            0.001,
            0.0,
            0.0,
            0.001,
            0.0,
            0.0,
        ]
        # Average width falls back to the parent /W average (a positive value).
        assert descendant.get_average_font_width() > 0.0
    finally:
        doc.close()
