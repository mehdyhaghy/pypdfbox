"""Tests ported from upstream PDFBox 3.0 (3.0.9-SNAPSHOT)
``fontbox/src/test/java/org/apache/fontbox/ttf/HintingTablesTest.java``.

Tests parsing of the TrueType hinting tables (``cvt ``, ``fpgm``,
``prep``, ``gasp``). LiberationSans-Regular is a hand-hinted font and
carries all four tables; the expected values come from its on-disk table
directory.
"""

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import GaspTable, TrueTypeFont, TTFParser
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer

_TTF_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "ttf"


def _parse(resource: str) -> TrueTypeFont:
    path = _TTF_DIR / resource
    assert path.exists(), f"missing test resource {resource}"
    return TTFParser().parse(RandomAccessReadBuffer(path.read_bytes()))


def test_control_value_table() -> None:
    font = _parse("LiberationSans-Regular.ttf")
    cvt = font.get_control_values()
    assert cvt is not None
    # 648-byte table / 2 bytes per FWord
    assert cvt.get_value_count() == 324
    assert len(cvt.get_values()) == 324
    # CVT entries are signed FWords (raw font units, not yet scaled to ppem)
    assert cvt.get_values()[0] == 1484


def test_font_program_table() -> None:
    font = _parse("LiberationSans-Regular.ttf")
    fpgm = font.get_font_program()
    assert fpgm is not None
    assert len(fpgm.get_program()) == 1972


def test_control_value_program_table() -> None:
    font = _parse("LiberationSans-Regular.ttf")
    prep = font.get_control_value_program()
    assert prep is not None
    assert len(prep.get_program()) == 835


def test_gasp_table() -> None:
    font = _parse("LiberationSans-Regular.ttf")
    gasp = font.get_gasp()
    assert gasp is not None
    assert gasp.get_version() == 0

    # three ranges: (<=8: DOGRAY), (<=17: GRIDFIT), (<=65535: GRIDFIT|DOGRAY)
    assert gasp.get_range_max_ppem() == [8, 17, 65535]
    assert gasp.get_range_flags() == [
        GaspTable.GASP_DOGRAY,
        GaspTable.GASP_GRIDFIT,
        GaspTable.GASP_GRIDFIT | GaspTable.GASP_DOGRAY,
    ]

    # ppem -> flags lookup, including range boundaries
    assert gasp.get_flags(8) == GaspTable.GASP_DOGRAY
    assert gasp.get_flags(9) == GaspTable.GASP_GRIDFIT
    assert gasp.get_flags(17) == GaspTable.GASP_GRIDFIT
    assert gasp.get_flags(18) == GaspTable.GASP_GRIDFIT | GaspTable.GASP_DOGRAY
    assert gasp.get_flags(2000) == GaspTable.GASP_GRIDFIT | GaspTable.GASP_DOGRAY

    # grid-fitting is off at 8 ppem and below, on above it
    assert not gasp.is_grid_fit(8)
    assert gasp.is_grid_fit(9)
    assert gasp.is_grid_fit(16)


@pytest.mark.skipif(
    not (_TTF_DIR / "JosefinSans-Italic.ttf").exists()
    or not (_TTF_DIR / "Lohit-Tamil.ttf").exists(),
    reason=(
        "JosefinSans-Italic.ttf / Lohit-Tamil.ttf (SIL OFL 1.1) are not bundled per the "
        "wave 1360 fixture policy; absent-table behaviour is covered synthetically in "
        "tests/fontbox/ttf/test_hinting_tables.py"
    ),
)
def test_absent_tables_return_null() -> None:
    # JosefinSans-Italic has no 'cvt '/'fpgm' (but does have 'prep'/'gasp')...
    josefin = _parse("JosefinSans-Italic.ttf")
    assert josefin.get_control_values() is None
    assert josefin.get_font_program() is None
    assert josefin.get_control_value_program() is not None
    assert josefin.get_gasp() is not None

    # ...and Lohit-Tamil has no 'gasp'. Absent accessors must return None, not raise.
    lohit = _parse("Lohit-Tamil.ttf")
    assert lohit.get_gasp() is None
    assert lohit.get_control_values() is not None
    assert lohit.get_font_program() is not None
    assert lohit.get_control_value_program() is not None


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
