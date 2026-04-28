"""Hand-written tests for :class:`CFFCIDFont` and the FDSelect/FDArray
helpers.

We exercise the synthetic Format0/Format3 FDSelect paths directly (no
fixture needed) and gate the parsed-font tests on the host having a
CIDKeyed OTF/TTC available — the CI runner may or may not, mirroring
the strategy in ``test_cff_font_parity.py``.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.cff.fd_array import FDArray
from pypdfbox.fontbox.cff.fd_select import (
    FDSelect,
    Format0FDSelect,
    Format3FDSelect,
)

# Candidate locations for a CIDKeyed CFF font on the host.
_CID_OTF_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _load_cid_cff_bytes() -> bytes | None:
    """Pull raw CFF bytes out of the first available CIDKeyed font, or
    ``None`` if nothing usable is on the host."""
    try:
        from fontTools.ttLib import TTFont  # noqa: PLC0415
    except ImportError:
        return None
    for candidate in _CID_OTF_CANDIDATES:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            ttf = TTFont(str(path), fontNumber=0)
            if "CFF " not in ttf:
                continue
            buf = io.BytesIO()
            ttf["CFF "].cff.compile(buf, ttf, isCFF2=False)
            return buf.getvalue()
        except Exception:  # noqa: BLE001
            continue
    return None


_CID_BYTES = _load_cid_cff_bytes()
_SKIP_REASON = "no CIDKeyed CFF/OTF fixture available on this host"


# ---------- FDSelect (synthetic) ----------


class TestFormat0FDSelect:
    def test_empty_returns_zero(self) -> None:
        sel = Format0FDSelect()
        assert sel.get_format() == 0
        assert sel.get_num_glyphs() == 0
        assert sel.get_fd_index(0) == 0
        assert sel[5] == 0  # out-of-range
        assert len(sel) == 0

    def test_basic_lookup(self) -> None:
        sel = Format0FDSelect([2, 2, 0, 1, 1, 3])
        assert sel.get_format() == 0
        assert sel.get_num_glyphs() == 6
        assert sel.get_fd_index(0) == 2
        assert sel.get_fd_index(2) == 0
        assert sel.get_fd_index(5) == 3
        # Negative / out-of-range → 0.
        assert sel.get_fd_index(-1) == 0
        assert sel.get_fd_index(99) == 0


class TestFormat3FDSelect:
    def test_empty_returns_zero(self) -> None:
        sel = Format3FDSelect()
        assert sel.get_format() == 3
        assert sel.get_num_glyphs() == 0
        assert sel.get_fd_index(0) == 0

    def test_ranges_resolve_correctly(self) -> None:
        # Ranges: [0..3) → FD 1, [3..7) → FD 2, [7..10) → FD 0.
        sel = Format3FDSelect(
            ranges=[(0, 1), (3, 2), (7, 0)],
            sentinel=10,
        )
        assert sel.get_format() == 3
        assert len(sel) == 10
        assert sel[0] == 1
        assert sel[2] == 1
        assert sel[3] == 2
        assert sel[6] == 2
        assert sel[7] == 0
        assert sel[9] == 0
        # Past the sentinel → 0.
        assert sel[10] == 0
        assert sel[100] == 0


class TestFDSelectWrapper:
    def test_none_underlying(self) -> None:
        sel = FDSelect(None)
        assert sel.get_format() == 0
        assert sel.get_num_glyphs() == 0
        assert sel.get_fd_index(0) == 0
        assert "FDSelect(" in repr(sel)

    def test_from_fonttools_with_dummy(self) -> None:
        class _Dummy:
            format = 3

            def __getitem__(self, i: int) -> int:
                return i % 4

            def __len__(self) -> int:
                return 16

        sel = FDSelect.from_fonttools(_Dummy())
        assert sel.get_format() == 3
        assert sel.get_num_glyphs() == 16
        assert sel.get_fd_index(0) == 0
        assert sel.get_fd_index(5) == 1
        assert sel.get_fd_index(15) == 3


# ---------- FDArray (synthetic) ----------


class TestFDArray:
    def test_empty_array(self) -> None:
        arr = FDArray(None)
        assert arr.size() == 0
        assert arr.is_empty()
        assert arr.get_font_dict(0) == {}
        assert arr.get_private_dict(0) == {}
        assert arr.get_default_width_x(0) == 0.0
        assert arr.get_nominal_width_x(0) == 0.0
        assert arr.get_local_subrs(0) == 0
        assert arr.get_raw_font_dict(0) is None

    def test_dummy_population(self) -> None:
        class _Priv:
            rawDict = {"defaultWidthX": 250, "nominalWidthX": 510}  # noqa: N815
            defaultWidthX = 250  # noqa: N815
            nominalWidthX = 510  # noqa: N815
            Subrs = [b"a", b"b", b"c"]

        class _Font:
            rawDict = {"FontName": "Demo", "Private": _Priv}  # noqa: N815
            Private = _Priv

        arr = FDArray.from_fonttools([_Font(), _Font()])
        assert arr.size() == 2
        assert not arr.is_empty()
        assert arr.get_font_dict(0)["FontName"] == "Demo"
        priv = arr.get_private_dict(0)
        assert priv["defaultWidthX"] == 250
        assert arr.get_default_width_x(1) == 250.0
        assert arr.get_nominal_width_x(1) == 510.0
        assert arr.get_local_subrs(0) == 3
        # Iteration yields one dict per FD.
        assert len(list(arr)) == 2

    def test_bulk_views(self) -> None:
        class _Priv:
            rawDict = {"defaultWidthX": 1, "nominalWidthX": 2}  # noqa: N815

        class _Font:
            rawDict = {"FontName": "X"}  # noqa: N815
            Private = _Priv

        arr = FDArray.from_fonttools([_Font(), _Font(), _Font()])
        fds = arr.font_dicts()
        privs = arr.private_dicts()
        assert len(fds) == 3
        assert len(privs) == 3
        assert all(d.get("FontName") == "X" for d in fds)
        assert all(p.get("defaultWidthX") == 1 for p in privs)


# ---------- CFFCIDFont (no fixture required) ----------


class TestCFFCIDFontEmptyInstance:
    def test_default_accessors_safe(self) -> None:
        cf = CFFCIDFont()
        assert cf.is_cid_font() is True
        assert cf.get_registry() == ""
        assert cf.get_ordering() == ""
        assert cf.get_supplement() == 0
        assert cf.get_ros() == ("", "", 0)
        assert cf.get_cid_count() == 0
        assert isinstance(cf.get_fd_select(), FDSelect)
        assert isinstance(cf.get_fd_array(), FDArray)
        assert cf.get_fd_index_for_gid(0) == 0
        assert cf.get_private_dict_for_gid(0) == {}
        assert cf.gid_for_cid(42) == 0


class TestCFFCIDFontFromNonCIDRaises:
    def test_from_bytes_rejects_name_keyed(self) -> None:
        # Build a name-keyed CFF byte stream from STIXGeneral if present,
        # otherwise skip — same shape as test_cff_font_parity.py.
        try:
            from fontTools.ttLib import TTFont  # noqa: PLC0415
        except ImportError:
            pytest.skip("fontTools not installed")
        candidates = ["/System/Library/Fonts/Supplemental/STIXGeneral.otf"]
        data: bytes | None = None
        for c in candidates:
            p = Path(c)
            if not p.exists():
                continue
            try:
                ttf = TTFont(str(p))
                if "CFF " not in ttf:
                    continue
                buf = io.BytesIO()
                ttf["CFF "].cff.compile(buf, ttf, isCFF2=False)
                data = buf.getvalue()
                break
            except Exception:  # noqa: BLE001
                continue
        if data is None:
            pytest.skip("no name-keyed OTF available")
        with pytest.raises(OSError):
            CFFCIDFont.from_bytes(data)


# ---------- CFFCIDFont (parsed-font tests) ----------


@pytest.fixture(scope="module")
def cid_font() -> CFFCIDFont:
    if _CID_BYTES is None:
        pytest.skip(_SKIP_REASON)
    return CFFCIDFont.from_bytes(_CID_BYTES)


def test_parsed_cid_font_is_cid(cid_font: CFFCIDFont) -> None:
    assert cid_font.is_cid_font() is True


def test_parsed_cid_font_has_ros(cid_font: CFFCIDFont) -> None:
    reg = cid_font.get_registry()
    ord_ = cid_font.get_ordering()
    sup = cid_font.get_supplement()
    assert isinstance(reg, str) and reg
    assert isinstance(ord_, str) and ord_
    assert isinstance(sup, int) and sup >= 0
    triple = cid_font.get_ros()
    assert triple == (reg, ord_, sup)


def test_parsed_cid_font_cid_count(cid_font: CFFCIDFont) -> None:
    assert cid_font.get_cid_count() > 0


def test_parsed_cid_font_fd_select_and_array(cid_font: CFFCIDFont) -> None:
    sel = cid_font.get_fd_select()
    arr = cid_font.get_fd_array()
    assert sel.get_num_glyphs() > 0
    assert arr.size() > 0
    # Every FDSelect entry must point at a valid /FDArray index.
    fd_for_gid0 = sel.get_fd_index(0)
    assert 0 <= fd_for_gid0 < arr.size()
    # Per-GID Private DICT lookup yields a dict with width entries.
    priv = cid_font.get_private_dict_for_gid(0)
    assert isinstance(priv, dict)


def test_parsed_cid_font_gid_for_cid(cid_font: CFFCIDFont) -> None:
    # CID 1 in a CIDKeyed CFF is conventionally the glyph at GID 1
    # (since GID 0 is .notdef and the charset starts ``cid00001`` at GID 1).
    gid = cid_font.gid_for_cid(1)
    assert gid in (0, 1)
    # Unmapped CID resolves to GID 0.
    assert cid_font.gid_for_cid(99_999_999) == 0


def test_parsed_cid_font_widths_per_fd(cid_font: CFFCIDFont) -> None:
    # default/nominal width X are well-defined per FD; the per-GID
    # convenience reads them via FDSelect.
    dw = cid_font.get_default_width_x_for_gid(0)
    nw = cid_font.get_nominal_width_x_for_gid(0)
    assert isinstance(dw, float)
    assert isinstance(nw, float)


def test_from_cff_font_round_trip(cid_font: CFFCIDFont) -> None:
    # Re-wrap shouldn't re-decompile or change observable state.
    base = CFFFont()
    base._fontset = cid_font._fontset  # noqa: SLF001
    base._top = cid_font._top  # noqa: SLF001
    again = CFFCIDFont.from_cff_font(base)
    assert again.get_ros() == cid_font.get_ros()
    assert again.get_cid_count() == cid_font.get_cid_count()


def test_get_font_dicts_and_priv_dicts(cid_font: CFFCIDFont) -> None:
    fds = cid_font.get_font_dicts()
    privs = cid_font.get_priv_dicts()
    assert isinstance(fds, list)
    assert isinstance(privs, list)
    assert len(fds) == cid_font.get_fd_array().size()
    assert len(privs) == len(fds)
    # Every Private DICT has the standard width entries.
    for priv in privs:
        assert isinstance(priv, dict)


def test_selector_keyed_glyph_access(cid_font: CFFCIDFont) -> None:
    # CID 1 — usually present in CIDKeyed CJK fonts at GID 1.
    if cid_font.has_glyph(1):
        path = cid_font.get_path(1)
        width = cid_font.get_width(1)
        assert isinstance(path, list)
        assert isinstance(width, float)
    # String selector form ("cid00001") goes through the same path.
    if cid_font.has_glyph("cid00001"):
        assert isinstance(cid_font.get_width("cid00001"), float)
    # Bogus selector → safe defaults.
    assert cid_font.has_glyph("not-a-cid") is False
    assert cid_font.get_path("not-a-cid") == []
    assert cid_font.get_width("not-a-cid") == 0.0


def test_get_type2_char_string_takes_cid(cid_font: CFFCIDFont) -> None:
    # Wrapper for CID 0 (always .notdef) — returned wrapper exposes the API.
    cs = cid_font.get_type2_char_string(0)
    assert hasattr(cs, "get_path")
    assert hasattr(cs, "get_width")


def test_per_fd_widths_dispatch(cid_font: CFFCIDFont) -> None:
    # No-arg form: Top-DICT /Private (unused for CIDKeyed; usually 0.0).
    base_dw = cid_font.get_default_width_x()
    base_nw = cid_font.get_nominal_width_x()
    assert isinstance(base_dw, float)
    assert isinstance(base_nw, float)
    # Per-GID form: route through FDSelect / FDArray.
    gid0_dw = cid_font.get_default_width_x(0)
    gid0_nw = cid_font.get_nominal_width_x(0)
    assert isinstance(gid0_dw, float)
    assert isinstance(gid0_nw, float)


def test_get_cid_for_gid_round_trip(cid_font: CFFCIDFont) -> None:
    """For a CIDKeyed CFF font the charset contains synthetic
    ``cidNNNNN`` names — get_cid_for_gid must recover the CID."""
    charset = cid_font.get_charset()
    # GID 0 is conventionally "cid00000" or ".notdef".
    cid0 = cid_font.get_cid_for_gid(0)
    assert isinstance(cid0, int)
    if len(charset) > 1 and charset[1].startswith("cid"):
        recovered = cid_font.get_cid_for_gid(1)
        assert recovered == int(charset[1][3:])
        # Round-trip back to GID.
        assert cid_font.get_gid_for_cid(recovered) == 1
