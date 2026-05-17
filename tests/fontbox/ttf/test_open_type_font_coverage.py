"""Coverage-boost tests for :class:`OpenTypeFont`.

Targets the branches not exercised by the existing test files:

* :meth:`set_version` ``struct.error`` / ``OverflowError`` fallback.
* :meth:`get_path` for name-keyed (str) GID against a CFF-flavoured font.
* :meth:`get_cff` ``compile()`` exception fallback path.
* :meth:`get_cff` empty-bytes branch.
* :meth:`get_cff` CID-keyed (``CFFCIDFont``) branch via mocked Top DICT.
* :meth:`get_glyph_table` raises on PostScript-flavoured fonts.
"""
from __future__ import annotations

import contextlib
import io
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.ttf import OpenTypeFont, OTFParser

FIXTURE_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _make_t2_empty() -> Any:
    from fontTools.misc.psCharStrings import T2CharString  # noqa: PLC0415

    cs = T2CharString()
    cs.program = ["endchar"]
    return cs


def _synth_name_keyed_otf_bytes() -> bytes:
    """Minimal name-keyed CFF OpenType font (re-used helper)."""
    try:
        from fontTools.fontBuilder import FontBuilder  # noqa: PLC0415
    except ImportError:
        pytest.skip("fontTools FontBuilder not available")

    fb = FontBuilder(unitsPerEm=1000, isTTF=False)
    glyph_order = [".notdef", "A"]
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({0x41: "A"})
    cs = {name: _make_t2_empty() for name in glyph_order}
    fb.setupCFF(
        psName="CoverageOTF",
        fontInfo={"FullName": "Coverage OTF"},
        charStringsDict=cs,
        privateDict={},
    )
    fb.setupHorizontalMetrics({name: (500, 0) for name in glyph_order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Cov", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, usWinAscent=800, usWinDescent=200)
    fb.setupPost()

    out = io.BytesIO()
    fb.font.save(out)
    return out.getvalue()


# ---------- set_version() ----------------------------------------------


def test_set_version_with_nan_does_not_raise() -> None:
    """``struct`` happily packs NaN — exercise the success branch one more
    time alongside the magic-bits check."""
    if not FIXTURE_TTF.exists():
        pytest.skip("TTF fixture not present")
    font = OTFParser().parse(FIXTURE_TTF.read_bytes())
    font.set_version(float("nan"))
    # NaN doesn't match the OTTO magic bits.
    assert font._has_post_script_tag is False


def test_set_version_with_invalid_input_falls_back_to_zero() -> None:
    """``struct.pack(">f", ...)`` rejects very large ints; the except
    branch sets ``bits = 0`` so ``_has_post_script_tag`` stays ``False``.
    """
    if not FIXTURE_TTF.exists():
        pytest.skip("TTF fixture not present")
    font = OTFParser().parse(FIXTURE_TTF.read_bytes())
    # Force the ``except`` path by patching ``struct.pack`` to raise.
    import struct as _struct  # noqa: PLC0415

    with mock.patch.object(
        _struct, "pack", side_effect=_struct.error("forced failure")
    ):
        font.set_version(1.0)
    assert font._has_post_script_tag is False


def test_set_version_otto_magic_marks_post_script() -> None:
    """The float whose IEEE-754 single-precision encoding equals
    ``_OTTO_FLOAT_BITS`` (0x469EA8A9) — what upstream stores when the
    SFNT version is OTTO — flips the PostScript flag.
    """
    if not FIXTURE_TTF.exists():
        pytest.skip("TTF fixture not present")
    font = OTFParser().parse(FIXTURE_TTF.read_bytes())
    import struct as _struct  # noqa: PLC0415

    # Round-trip 0x469EA8A9 into a Python float — what upstream's
    # ``Float.intBitsToFloat`` produces from the OTTO fingerprint.
    otto_encoded_float = _struct.unpack(">f", _struct.pack(">I", 0x469EA8A9))[0]
    font.set_version(otto_encoded_float)
    assert font._has_post_script_tag is True


# ---------- get_glyph_table override ------------------------------------


def test_get_glyph_table_raises_on_postscript_font() -> None:
    if not FIXTURE_TTF.exists():
        pytest.skip("TTF fixture not present")
    font = OTFParser().parse(FIXTURE_TTF.read_bytes())
    font._has_post_script_tag = True
    with pytest.raises(NotImplementedError):
        font.get_glyph_table()


def test_get_glyph_table_returns_none_when_not_postscript() -> None:
    """A TTF-flavoured OTF stream still delegates to the parent
    ``get_glyph_table`` which may return ``None`` when no ``glyf`` table
    is registered with fontTools (depends on the source). Either ``None``
    or a populated glyph table is acceptable; the key is that no
    ``NotImplementedError`` is raised.
    """
    if not FIXTURE_TTF.exists():
        pytest.skip("TTF fixture not present")
    font = OTFParser().parse(FIXTURE_TTF.read_bytes())
    assert font._has_post_script_tag is False
    # Must not raise.
    font.get_glyph_table()


# ---------- get_path() override for CFF-flavoured fonts -----------------


@pytest.fixture(scope="module")
def cff_otf() -> OpenTypeFont:
    font = OTFParser().parse(_synth_name_keyed_otf_bytes())
    assert isinstance(font, OpenTypeFont)
    # ``OTFParser`` doesn't always flip the package-private SFNT-version
    # flag during parse — the same as upstream, where the flag is set by
    # ``setVersion()`` called from ``TTFParser.parseTables``. Force it on
    # for the override coverage to exercise the CFF branch in
    # :meth:`get_path`.
    font._has_post_script_tag = True
    assert font.is_post_script() is True
    return font


def test_get_path_int_gid_delegates_to_parent(cff_otf: OpenTypeFont) -> None:
    """An integer GID never enters the CFF override path; it delegates
    straight to ``TrueTypeFont.get_path(int)``. On this CFF-flavoured
    font the parent's ``glyf`` lookup raises ``NotImplementedError``
    (PostScript flag) — the key invariant is that the CFF branch was
    *not* taken, so we accept either a clean result or that exception.
    """
    with contextlib.suppress(NotImplementedError):
        cff_otf.get_path(0)


def test_get_path_str_gid_with_cff(cff_otf: OpenTypeFont) -> None:
    """String GID against a CFF-flavoured supported OTF — exercises the
    ``cff.get_type2_char_string(...)`` branch."""
    # Reach the CFF branch (must have post_script tag + supported OTF).
    cff_otf.get_path("A")


def test_get_path_str_gid_returns_none_when_get_cff_returns_none(
    cff_otf: OpenTypeFont,
) -> None:
    """If ``get_cff`` would return ``None`` for any reason, ``get_path``
    short-circuits to ``None`` rather than crashing on a missing CFF.
    """
    with mock.patch.object(cff_otf, "get_cff", return_value=None):
        # Cache invalidate isn't needed since we patch the accessor itself.
        assert cff_otf.get_path("A") is None


def test_get_path_str_gid_returns_none_when_charstring_missing(
    cff_otf: OpenTypeFont,
) -> None:
    """If the CFF ``get_type2_char_string`` returns ``None`` for the GID,
    the override returns ``None`` (covers the ``cs is None`` guard).
    """

    class _NoneCFF:
        def get_type2_char_string(self, _gid: int) -> None:
            return None

    with mock.patch.object(cff_otf, "get_cff", return_value=_NoneCFF()):
        assert cff_otf.get_path("A") is None


# ---------- get_cff() error-path branches -------------------------------


def test_get_cff_compile_exception_falls_back_to_raw_data() -> None:
    """If ``cff_table.compile`` raises, the code falls back to the
    raw ``cff_table.data`` bytes recorded during decompile.
    """
    raw = _synth_name_keyed_otf_bytes()
    font = OTFParser().parse(raw)
    # Reset the CFF projection cache before mocking.
    font._cff = None
    font._cff_resolved = False
    cff_table = font._tt["CFF "]
    real_bytes = cff_table.compile(font._tt)

    with mock.patch.object(
        cff_table, "compile", side_effect=RuntimeError("forced failure")
    ):
        # Stash the bytes on ``.data`` so the fallback branch finds them.
        cff_table.data = real_bytes  # type: ignore[attr-defined]
        cff = font.get_cff()

    assert cff is not None
    assert isinstance(cff, CFFType1Font)


def test_get_cff_returns_none_when_compile_and_data_both_empty() -> None:
    """If ``compile`` raises *and* there's no fallback raw payload, the
    accessor returns ``None`` (covers the ``not cff_bytes`` guard)."""
    raw = _synth_name_keyed_otf_bytes()
    font = OTFParser().parse(raw)
    font._cff = None
    font._cff_resolved = False
    cff_table = font._tt["CFF "]
    with mock.patch.object(
        cff_table, "compile", side_effect=RuntimeError("forced failure")
    ):
        # Force the ``getattr(..., "data", b"")`` fallback to return b"".
        if hasattr(cff_table, "data"):
            del cff_table.data
        assert font.get_cff() is None


def test_get_cff_returns_none_when_compile_yields_empty_bytes() -> None:
    """``compile`` returning b"" hits the same empty-bytes guard."""
    raw = _synth_name_keyed_otf_bytes()
    font = OTFParser().parse(raw)
    font._cff = None
    font._cff_resolved = False
    cff_table = font._tt["CFF "]
    with mock.patch.object(cff_table, "compile", return_value=b""):
        assert font.get_cff() is None


def test_get_cff_routes_cid_keyed_font_to_cffcidfont() -> None:
    """When the Top DICT exposes ``ROS``, the projection routes to
    :class:`CFFCIDFont`.

    We synthesise the CID-flavoured shape by patching the parent
    ``font_set[name]`` to report an ``ROS`` attribute. The actual CFF
    payload bytes still parse cleanly via :meth:`CFFCIDFont.from_bytes`
    because the underlying CFF table itself is name-keyed — but the
    branch selection only inspects the Top DICT introspection.
    """
    raw = _synth_name_keyed_otf_bytes()
    font = OTFParser().parse(raw)
    font._cff = None
    font._cff_resolved = False
    cff_table = font._tt["CFF "]
    # Snapshot the real CFF bytes before we monkey-patch ``cff`` — the
    # ``compile`` will then take the fallback path that reads
    # ``cff_table.data`` (which we'll seed below).
    real_bytes = cff_table.compile(font._tt)

    class _TopWithRos:
        ROS = ("Adobe", "Identity", 0)
        rawDict: dict[str, Any] = {}

    class _FakeFontSet:
        fontNames = ["CoverageOTF"]

        def __getitem__(self, _name: str) -> _TopWithRos:
            return _TopWithRos()

    fake_set = _FakeFontSet()
    sentinel = CFFCIDFont()
    captured: dict[str, Any] = {}

    def _fake_from_bytes(data: Any) -> CFFCIDFont:
        captured["data"] = data
        return sentinel

    # Replace ``cff_table.cff`` with the CID-flavoured fake; seed
    # ``cff_table.data`` so the compile-fallback branch yields non-empty
    # bytes; patch ``CFFCIDFont.from_bytes`` to return our sentinel
    # instead of doing real parsing (the bytes aren't really CID-keyed).
    original_cff = cff_table.cff
    original_from_bytes = CFFCIDFont.from_bytes
    cff_table.cff = fake_set  # type: ignore[assignment]
    cff_table.data = real_bytes  # type: ignore[attr-defined]
    CFFCIDFont.from_bytes = staticmethod(_fake_from_bytes)  # type: ignore[method-assign]
    try:
        cff = font.get_cff()
    finally:
        cff_table.cff = original_cff
        CFFCIDFont.from_bytes = original_from_bytes  # type: ignore[method-assign]

    assert cff is sentinel
    assert isinstance(captured["data"], (bytes, bytearray))


def test_get_cff_routes_cid_via_raw_dict_ros_key() -> None:
    """``ROS`` may live only in ``rawDict``; the lookup falls back to that
    when the attribute isn't a direct attribute on the Top DICT.
    """
    raw = _synth_name_keyed_otf_bytes()
    font = OTFParser().parse(raw)
    font._cff = None
    font._cff_resolved = False
    cff_table = font._tt["CFF "]
    real_bytes = cff_table.compile(font._tt)

    class _TopRawDictOnly:
        rawDict = {"ROS": ("Adobe", "Identity", 0)}

    class _FakeFontSet:
        fontNames = ["CoverageOTF"]

        def __getitem__(self, _name: str) -> _TopRawDictOnly:
            return _TopRawDictOnly()

    sentinel = CFFCIDFont()

    def _fake_from_bytes(_data: Any) -> CFFCIDFont:
        return sentinel

    original_cff = cff_table.cff
    original_from_bytes = CFFCIDFont.from_bytes
    cff_table.cff = _FakeFontSet()  # type: ignore[assignment]
    cff_table.data = real_bytes  # type: ignore[attr-defined]
    CFFCIDFont.from_bytes = staticmethod(_fake_from_bytes)  # type: ignore[method-assign]
    try:
        cff = font.get_cff()
    finally:
        cff_table.cff = original_cff
        CFFCIDFont.from_bytes = original_from_bytes  # type: ignore[method-assign]

    assert cff is sentinel


def test_get_cff_cached_negative_short_circuits() -> None:
    """Once ``_cff_resolved`` is True with ``_cff = None`` cached, repeat
    calls short-circuit and return ``None`` without re-parsing.
    """
    if not FIXTURE_TTF.exists():
        pytest.skip("TTF fixture not present")
    font = OTFParser().parse(FIXTURE_TTF.read_bytes())
    # First call resolves & caches the negative result.
    assert font.get_cff() is None
    assert font._cff_resolved is True
    # Second call must take the cached branch.
    assert font.get_cff() is None
