"""Wave 1615 forward-ports from the unreleased PDFBox 3.0.9.

* PDFBOX-6319: lenient ``/W`` and ``/W2`` parsing in ``PDCIDFont``
  (malformed entries never raise; a bad ``/W2`` triple stops the read).
* PDFBOX-6288 / PDFBOX-5384: a non-embedded ``CIDFontType2`` whose
  substitute is the same font (``hasEqualName``) and whose encoding CMap has
  an ``Identity`` ordering treats the code as the GID.
* PDFBOX-6323: ``FileSystemFontProvider`` never derives a ROS from the
  ``gcid`` table, so the upstream supplement bug cannot occur here.
"""

import logging
from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

_FONT = (
    Path(__file__).resolve().parents[3]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "DejaVuSans.ttf"
)


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


# ---------------------------------------------------------------- PDFBOX-6319


def _cid_font(
    w: list | None = None, w2: list | None = None
) -> PDCIDFontType2:
    font = PDCIDFontType2()
    if w is not None:
        font.set_w(COSArray(w))
    if w2 is not None:
        font.set_w2(COSArray(w2))
    return font


def test_w_range_with_non_number_second_consumes_three_slots() -> None:
    # Upstream readWidths treats a non-array second entry as ``c1 c2 w`` and
    # skips all three slots; the following ``10 [500]`` must still parse.
    font = _cid_font(
        w=[_i(1), COSName.get_pdf_name("x"), _i(700), _i(10), COSArray([_i(500)])]
    )
    assert font.get_widths() == {10: 500.0}


def test_w_range_with_non_number_width_is_skipped() -> None:
    font = _cid_font(
        w=[_i(1), _i(3), COSString("bad"), _i(5), _i(6), _i(250)]
    )
    assert font.get_widths() == {5: 250.0, 6: 250.0}


def test_w_premature_end_does_not_raise() -> None:
    font = _cid_font(w=[_i(1), _i(3)])
    assert font.get_widths() == {}
    assert font.get_glyph_width(1) == 1000.0


def test_w2_non_number_first_entry_is_skipped() -> None:
    font = _cid_font(
        w2=[
            COSString("bad"),
            _i(4),
            COSArray([_i(-900), _i(250), _i(880)]),
        ]
    )
    assert font.get_widths2() == {4: (-900.0, 250.0, 880.0)}


def test_w2_array_form_stops_at_first_bad_triple() -> None:
    font = _cid_font(
        w2=[
            _i(1),
            COSArray(
                [
                    _i(-900), _i(250), _i(880),
                    COSName.get_pdf_name("bad"), _i(1), _i(2),
                    _i(-901), _i(251), _i(881),
                ]
            ),
            _i(20),
            COSArray([_i(-1000), _i(300), _i(900)]),
        ]
    )
    # CID 3 is dropped (upstream breaks the inner loop), CID 20 still read.
    assert font.get_widths2() == {
        1: (-900.0, 250.0, 880.0),
        20: (-1000.0, 300.0, 900.0),
    }


def test_w2_array_form_ignores_trailing_partial_triple() -> None:
    # ``j < size - 2`` upstream: a trailing pair is never read.
    font = _cid_font(
        w2=[_i(1), COSArray([_i(-900), _i(250), _i(880), _i(-1), _i(2)])]
    )
    assert font.get_widths2() == {1: (-900.0, 250.0, 880.0)}


def test_w2_range_form_bad_triple_aborts_whole_read() -> None:
    font = _cid_font(
        w2=[
            _i(1), _i(2), COSString("x"), _i(1), _i(2),
            _i(10), COSArray([_i(-900), _i(250), _i(880)]),
        ]
    )
    assert font.get_widths2() == {}


def test_w2_range_form_truncated_aborts(caplog: pytest.LogCaptureFixture) -> None:
    font = _cid_font(
        w2=[
            _i(5), COSArray([_i(-900), _i(250), _i(880)]),
            _i(1), _i(2), COSFloat(-1.0), _i(3),
        ]
    )
    with caplog.at_level(logging.WARNING):
        assert font.get_widths2() == {5: (-900.0, 250.0, 880.0)}
    assert "Aborting read of 3 elements of /W2" in caplog.text


def test_w2_next_neither_array_nor_number_is_skipped() -> None:
    font = _cid_font(
        w2=[
            _i(1), COSString("x"),
            _i(7), COSArray([_i(-900), _i(250), _i(880)]),
        ]
    )
    assert font.get_widths2() == {7: (-900.0, 250.0, 880.0)}


def test_malformed_w2_metrics_fall_back_to_defaults() -> None:
    font = _cid_font(
        w=[_i(0), COSArray([_i(600)])],
        w2=[_i(0), COSArray([COSString("x"), _i(1), _i(2)])],
    )
    assert font.get_vertical_displacement_vector_y(0) == -1000.0
    assert font.get_position_vector(0) == (300.0, 880.0)


# ---------------------------------------------------- PDFBOX-6288 / PDFBOX-5384


def _non_embedded(
    base_font: str | None = None, cid_to_gid: COSStream | None = None
) -> tuple[PDDocument, PDCIDFontType2, TrueTypeFont]:
    doc = PDDocument()
    loaded = PDType0Font.load(doc, str(_FONT), embed_subset=False)
    loaded.get_descendant_font().get_font_descriptor().set_font_file2(None)
    descendant_dict = loaded.get_descendant_font().get_cos_object()
    if base_font is not None:
        descendant_dict.set_name(COSName.get_pdf_name("BaseFont"), base_font)
    if cid_to_gid is None:
        descendant_dict.remove_item(COSName.get_pdf_name("CIDToGIDMap"))
    else:
        descendant_dict.set_item(COSName.get_pdf_name("CIDToGIDMap"), cid_to_gid)
    parent = PDType0Font(loaded.get_cos_object())
    descendant = parent.get_descendant_font()
    assert isinstance(descendant, PDCIDFontType2)
    assert not descendant.is_embedded()
    ttf = TrueTypeFont.from_bytes(_FONT.read_bytes())
    descendant._substitute_ttf = ttf
    return doc, descendant, ttf


@pytest.mark.parametrize(
    ("base_font", "equal"),
    [
        ("DejaVuSans", True),
        ("DejaVu", True),  # prefix of the program name
        ("DejaVuSans-Bold", True),  # program name is a prefix
        ("DejaVu-Sans", True),  # "-" removed before comparing
        ("DejaVu,Sans", True),  # "," removed before comparing
        ("ArialMT", False),
    ],
    ids=["equal", "prefix", "longer", "dash", "comma", "other"],
)
def test_name_equality(base_font: str, equal: bool) -> None:
    doc, descendant, ttf = _non_embedded(base_font)
    try:
        assert descendant._is_equal_name(ttf) is equal
    finally:
        doc.close()


def test_equal_name_identity_uses_code_as_gid() -> None:
    doc, descendant, ttf = _non_embedded()
    try:
        assert descendant.code_to_gid(36) == 36
        # a code beyond the glyph count resolves to GID 0
        assert descendant.code_to_gid(ttf.get_number_of_glyphs()) == 0
        assert descendant.code_to_gid(60000) == 0
    finally:
        doc.close()


def test_other_name_keeps_unicode_fallback() -> None:
    doc, descendant, _ttf = _non_embedded("SomethingElse")
    try:
        # no /ToUnicode mapping for 60000 -> the CID is used as the GID
        assert descendant.code_to_gid(60000) == 60000
    finally:
        doc.close()


def test_identity_warning_is_logged_once(caplog: pytest.LogCaptureFixture) -> None:
    doc, descendant, _ttf = _non_embedded()
    try:
        with caplog.at_level(logging.WARNING):
            for code in (36, 37, 38):
                descendant.code_to_gid(code)
        assert caplog.text.count("Using non-embedded CID2GID identity") == 1
    finally:
        doc.close()


def test_equal_name_cid_to_gid_stream_is_used_and_warns_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stream = COSStream()
    stream.set_data(bytes([0, 0, 0, 40, 0, 41]))
    doc, descendant, _ttf = _non_embedded("DejaVuSans-Bold", stream)
    try:
        with caplog.at_level(logging.WARNING):
            assert descendant.code_to_gid(1) == 40
            assert descendant.code_to_gid(2) == 41
            assert descendant.code_to_gid(5) == 0
        assert caplog.text.count("Using non-embedded GIDs") == 1
    finally:
        doc.close()


# ---------------------------------------------------------------- PDFBOX-6323


def test_file_system_font_provider_has_no_gcid_ros(tmp_path: Path) -> None:
    """Upstream derived the ROS supplement from the ``gcid`` table with a
    broken bit expression. pypdfbox indexes TrueType fonts through fontTools
    and never reads ``gcid``: a font carrying one is indexed with no
    ``CIDSystemInfo``."""
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables.DefaultTable import DefaultTable

    from pypdfbox.pdmodel.font.file_system_font_provider import (
        FileSystemFontProvider,
    )

    tt = TTFont(str(_FONT))
    gcid = DefaultTable("gcid")
    data = bytearray(144)
    data[12:18] = b"Adobe\0"
    data[76:82] = b"Japan1"
    data[140:142] = b"\x01\x02"  # supplement 258 upstream after the fix
    gcid.data = bytes(data)
    tt["gcid"] = gcid
    path = tmp_path / "gcid.ttf"
    tt.save(str(path))
    tt.close()

    provider = FileSystemFontProvider.__new__(FileSystemFontProvider)
    provider._font_info_list = []
    with TTFont(str(path)) as font:
        provider._add_ttf_metadata(path, font)
    infos = provider._font_info_list
    assert len(infos) == 1
    assert infos[0].get_cid_system_info() is None



# ---------------------------------------------------------------- PDFBOX-6321


def test_type0_encode_bytes_join_to_gid() -> None:
    """Upstream fixed a sign-extending byte join in TestFontEmbedding.
    Python ``bytes`` are unsigned; the encoded big-endian pair must join to
    the glyph id from the font's cmap."""
    doc = PDDocument()
    try:
        font = PDType0Font.load(doc, str(_FONT), embed_subset=False)
        ttf = TrueTypeFont.from_bytes(_FONT.read_bytes())
        lookup = ttf.get_unicode_cmap_lookup(False)
        encoded = font.encode("Aé")
        assert len(encoded) == 4
        val1 = (encoded[0] & 0xFF) << 8 | (encoded[1] & 0xFF)
        val2 = (encoded[2] & 0xFF) << 8 | (encoded[3] & 0xFF)
        assert val1 == lookup.get_glyph_id(ord("A"))
        assert val2 == lookup.get_glyph_id(0xE9)
    finally:
        doc.close()
