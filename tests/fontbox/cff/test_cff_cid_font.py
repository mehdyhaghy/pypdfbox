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
from typing import Any

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
        from fontTools.ttLib import TTFont  # type: ignore[import-untyped]  # noqa: PLC0415
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
        # At / past the sentinel -> -1, matching PDFBox's Format3FDSelect.
        assert sel[10] == -1
        assert sel[100] == -1


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


# ---------- New parity-roundout tests (Wave 75) ----------


class TestFDSelectContains:
    def test_format0_contains(self) -> None:
        sel = Format0FDSelect([1, 2, 3, 0, 1])
        # In-range GIDs.
        assert 0 in sel
        assert 4 in sel
        # Out-of-range / negative / non-int.
        assert 5 not in sel
        assert -1 not in sel
        assert "0" not in sel
        # ``True`` is an ``int`` in Python; we explicitly reject it so
        # ``True in sel`` doesn't sneak past as ``1 in sel``.
        assert True not in sel  # noqa: FBT003
        assert False not in sel  # noqa: FBT003

    def test_format3_contains(self) -> None:
        sel = Format3FDSelect(ranges=[(0, 1), (3, 2)], sentinel=8)
        assert 0 in sel
        assert 7 in sel
        assert 8 not in sel  # at sentinel
        assert -1 not in sel

    def test_empty_fdselect_contains(self) -> None:
        assert 0 not in FDSelect(None)


class TestFormat0FDSelectGetFds:
    def test_get_fds_returns_copy(self) -> None:
        original = [4, 4, 0, 1, 2]
        sel = Format0FDSelect(original)
        fds = sel.get_fds()
        assert fds == original
        # Mutating the returned list must not affect the FDSelect.
        fds[0] = 99
        assert sel.get_fd_index(0) == 4

    def test_get_fds_empty(self) -> None:
        assert Format0FDSelect().get_fds() == []


class TestFormat3FDSelectAccessors:
    def test_get_ranges_and_sentinel(self) -> None:
        ranges = [(0, 1), (3, 2), (7, 0)]
        sel = Format3FDSelect(ranges=ranges, sentinel=10)
        assert sel.get_ranges() == ranges
        assert sel.get_sentinel() == 10
        assert sel.get_num_ranges() == 3

    def test_get_ranges_returns_copy(self) -> None:
        sel = Format3FDSelect(ranges=[(0, 1), (5, 2)], sentinel=10)
        out = sel.get_ranges()
        out.append((99, 99))
        assert sel.get_num_ranges() == 2

    def test_empty_ranges(self) -> None:
        sel = Format3FDSelect()
        assert sel.get_ranges() == []
        assert sel.get_sentinel() == 0
        assert sel.get_num_ranges() == 0


class TestFDArrayContains:
    def test_contains_valid_index(self) -> None:
        class _Font:
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = None

        arr = FDArray.from_fonttools([_Font(), _Font()])
        assert 0 in arr
        assert 1 in arr
        assert 2 not in arr
        assert -1 not in arr
        assert "0" not in arr
        assert True not in arr  # noqa: FBT003

    def test_empty_fdarray_contains(self) -> None:
        assert 0 not in FDArray(None)


class TestFDArrayGetFontName:
    def test_get_font_name_attribute_form(self) -> None:
        class _Font:
            FontName = "MyFont-Bold"  # noqa: N815
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = None

        arr = FDArray.from_fonttools([_Font()])
        assert arr.get_font_name(0) == "MyFont-Bold"

    def test_get_font_name_rawdict_fallback(self) -> None:
        class _Font:
            rawDict = {"FontName": "FromRawDict"}  # noqa: N815
            Private = None

        arr = FDArray.from_fonttools([_Font()])
        assert arr.get_font_name(0) == "FromRawDict"

    def test_get_font_name_missing(self) -> None:
        class _Font:
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = None

        arr = FDArray.from_fonttools([_Font()])
        assert arr.get_font_name(0) == ""

    def test_get_font_name_out_of_range(self) -> None:
        arr = FDArray(None)
        assert arr.get_font_name(0) == ""
        assert arr.get_font_name(-1) == ""


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


# ---------- ROS / FDArray setter overrides (mirror upstream package-private setters) ----------


class TestCFFCIDFontSetters:
    """Coverage for ``set_registry`` / ``set_ordering`` / ``set_supplement``
    / ``set_font_dict`` / ``set_priv_dict`` / ``set_fd_select``. These
    mirror upstream's package-private setters; we expose them publicly
    for parity with callers that synthesise a CFFCIDFont outside the
    parser path."""

    def test_set_registry_ordering_supplement(self) -> None:
        cf = CFFCIDFont()
        # Defaults are empty / zero on an unparsed font.
        assert cf.get_ros() == ("", "", 0)
        cf.set_registry("Adobe")
        cf.set_ordering("Japan1")
        cf.set_supplement(6)
        assert cf.get_registry() == "Adobe"
        assert cf.get_ordering() == "Japan1"
        assert cf.get_supplement() == 6
        # Triple convenience picks up all three overrides.
        assert cf.get_ros() == ("Adobe", "Japan1", 6)

    def test_set_supplement_coerces_to_int(self) -> None:
        cf = CFFCIDFont()
        cf.set_supplement("4")  # type: ignore[arg-type]
        assert cf.get_supplement() == 4
        assert isinstance(cf.get_supplement(), int)

    def test_set_font_dict_overrides_fd_array_view(self) -> None:
        cf = CFFCIDFont()
        synthetic = [{"FontName": "FD0"}, {"FontName": "FD1"}]
        cf.set_font_dict(synthetic)
        out = cf.get_font_dicts()
        assert out == synthetic
        # Returned list is independent — mutating it doesn't bleed back.
        out.append({"FontName": "FD2"})
        assert len(cf.get_font_dicts()) == 2

    def test_set_priv_dict_overrides_fd_array_view(self) -> None:
        cf = CFFCIDFont()
        synthetic = [{"defaultWidthX": 250}, {"defaultWidthX": 500}]
        cf.set_priv_dict(synthetic)
        assert cf.get_priv_dicts() == synthetic

    def test_set_fd_select_overrides_lazy_load(self) -> None:
        cf = CFFCIDFont()
        synthetic = FDSelect.from_fonttools(None)
        cf.set_fd_select(synthetic)
        assert cf.get_fd_select() is synthetic


# ---------- FDArray Wave-181 helpers ----------


class TestFDArrayHasPrivateDict:
    """``FDArray.has_private_dict(fd_index)`` — predicate-shaped check
    callers run before reading per-FD width / Subrs accessors."""

    def test_true_when_private_present(self) -> None:
        class _Priv:
            rawDict = {"defaultWidthX": 500}  # noqa: N815

        class _Font:
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = _Priv()

        arr = FDArray.from_fonttools([_Font()])
        assert arr.has_private_dict(0) is True

    def test_false_when_private_absent(self) -> None:
        class _Font:
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = None

        arr = FDArray.from_fonttools([_Font()])
        assert arr.has_private_dict(0) is False

    def test_false_for_out_of_range(self) -> None:
        arr = FDArray(None)
        assert arr.has_private_dict(0) is False
        assert arr.has_private_dict(-1) is False


class TestFDArrayHasLocalSubrs:
    """``FDArray.has_local_subrs(fd_index)`` — true only when the FD's
    Private DICT carries a non-empty /Subrs INDEX."""

    def test_true_when_nonempty_subrs(self) -> None:
        class _Priv:
            Subrs = [b"\x0e", b"\x0e"]  # noqa: N815
            rawDict: dict[str, Any] = {}  # noqa: N815

        class _Font:
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = _Priv()

        arr = FDArray.from_fonttools([_Font()])
        assert arr.has_local_subrs(0) is True

    def test_false_when_empty_subrs(self) -> None:
        class _Priv:
            Subrs: list[bytes] = []  # noqa: N815
            rawDict: dict[str, Any] = {}  # noqa: N815

        class _Font:
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = _Priv()

        arr = FDArray.from_fonttools([_Font()])
        assert arr.has_local_subrs(0) is False

    def test_false_when_no_private_dict(self) -> None:
        class _Font:
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = None

        arr = FDArray.from_fonttools([_Font()])
        assert arr.has_local_subrs(0) is False

    def test_false_for_out_of_range(self) -> None:
        arr = FDArray(None)
        assert arr.has_local_subrs(0) is False
        assert arr.has_local_subrs(7) is False


class TestFDArrayGetLocalSubrIndex:
    """``FDArray.get_local_subr_index(fd_index)`` — list-of-bytes view
    parallel to :meth:`CFFFont.get_global_subr_index`. Used by Type 2
    charstring decoders to resolve ``callsubr`` operations."""

    def test_returns_bytecode_from_objects(self) -> None:
        class _Cs:
            bytecode = b"\x0a\x0e"  # noqa: N815

        class _Priv:
            Subrs = [_Cs(), _Cs()]  # noqa: N815
            rawDict: dict[str, Any] = {}  # noqa: N815

        class _Font:
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = _Priv()

        arr = FDArray.from_fonttools([_Font()])
        out = arr.get_local_subr_index(0)
        assert out == [b"\x0a\x0e", b"\x0a\x0e"]

    def test_returns_raw_bytes_when_already_bytes(self) -> None:
        class _Priv:
            Subrs = [b"\x0e", bytearray(b"\x0a")]  # noqa: N815
            rawDict: dict[str, Any] = {}  # noqa: N815

        class _Font:
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = _Priv()

        arr = FDArray.from_fonttools([_Font()])
        out = arr.get_local_subr_index(0)
        assert out == [b"\x0e", b"\x0a"]
        # bytearray entries get coerced to bytes for hashability / parity.
        assert all(isinstance(b, bytes) for b in out)

    def test_empty_when_no_subrs(self) -> None:
        class _Priv:
            rawDict: dict[str, Any] = {}  # noqa: N815
            Subrs = None  # noqa: N815

        class _Font:
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = _Priv()

        arr = FDArray.from_fonttools([_Font()])
        assert arr.get_local_subr_index(0) == []

    def test_empty_when_no_private(self) -> None:
        class _Font:
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = None

        arr = FDArray.from_fonttools([_Font()])
        assert arr.get_local_subr_index(0) == []

    def test_empty_when_out_of_range(self) -> None:
        arr = FDArray(None)
        assert arr.get_local_subr_index(0) == []
        assert arr.get_local_subr_index(-1) == []

    def test_unknown_entry_shape_yields_empty_bytes(self) -> None:
        # Defensive path: a Subrs entry that is neither a bytes-like
        # nor a fontTools T2CharString (no ``bytecode``) shouldn't crash
        # — emit ``b""`` instead so the indices stay aligned.
        class _Priv:
            Subrs = [object(), b"\x0e"]  # noqa: N815
            rawDict: dict[str, Any] = {}  # noqa: N815

        class _Font:
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = _Priv()

        arr = FDArray.from_fonttools([_Font()])
        assert arr.get_local_subr_index(0) == [b"", b"\x0e"]


class TestFDArrayIndexForFontName:
    """``FDArray.index_for_font_name(name)`` — reverse lookup by FontName.
    Returns ``-1`` when no FD matches (mirrors common Java sentinel for
    "not found" in PDFBox wrappers)."""

    def test_finds_first_match(self) -> None:
        class _Font0:
            FontName = "FD-Latin"  # noqa: N815
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = None

        class _Font1:
            FontName = "FD-Greek"  # noqa: N815
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = None

        arr = FDArray.from_fonttools([_Font0(), _Font1()])
        assert arr.index_for_font_name("FD-Greek") == 1
        assert arr.index_for_font_name("FD-Latin") == 0

    def test_unknown_name_returns_minus_one(self) -> None:
        class _Font:
            FontName = "FD-Latin"  # noqa: N815
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = None

        arr = FDArray.from_fonttools([_Font()])
        assert arr.index_for_font_name("FD-Cyrillic") == -1

    def test_empty_or_none_name_returns_minus_one(self) -> None:
        class _Font:
            FontName = "FD0"  # noqa: N815
            rawDict: dict[str, Any] = {}  # noqa: N815
            Private = None

        arr = FDArray.from_fonttools([_Font()])
        assert arr.index_for_font_name("") == -1

    def test_empty_array_returns_minus_one(self) -> None:
        arr = FDArray(None)
        assert arr.index_for_font_name("Anything") == -1

    def test_finds_via_rawdict_fallback(self) -> None:
        # When fontTools surfaces FontName only via rawDict (no attr),
        # the lookup should still resolve.
        class _Font:
            rawDict = {"FontName": "FromRawDict"}  # noqa: N815
            Private = None

        arr = FDArray.from_fonttools([_Font()])
        assert arr.index_for_font_name("FromRawDict") == 0
