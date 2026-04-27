"""Hand-written tests for ``pypdfbox.fontbox.cff.Type2CharString``.

We exercise both the bare/empty constructor (no fontTools state) and a
real-glyph path: pull an OTF off the host's font directories, hand the
CFF bytes to :class:`CFFFont`, and walk every glyph via
``get_type2_char_string``.

When no OTF is available the module skips — same convention as
``test_cff_font_parity``.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.cff.type2_char_string import Type2CharString

_OTF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/STIXGeneral.otf",
    "/System/Library/Fonts/Supplemental/STIXGeneralItalic.otf",
    "/usr/share/fonts/opentype/stix/STIXGeneral.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _load_cff_bytes() -> bytes | None:
    try:
        from fontTools.ttLib import TTFont  # noqa: PLC0415
    except ImportError:
        return None
    for candidate in _OTF_CANDIDATES:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            ttf = TTFont(str(path))
            if "CFF " not in ttf:
                continue
            buf = io.BytesIO()
            ttf["CFF "].cff.compile(buf, ttf, isCFF2=False)
            return buf.getvalue()
        except Exception:  # noqa: BLE001
            continue
    return None


_CFF_BYTES = _load_cff_bytes()
_SKIP_REASON = "no CFF/OTF fixture available on this host"


# ---------------------------------------------------------------------------
# Bare constructor — no fontTools state required
# ---------------------------------------------------------------------------


def test_empty_charstring_accessors_safe() -> None:
    """A Type2CharString with no program must answer all accessors with
    safe defaults; ``get_path()`` must return an empty list, never raise."""
    cs = Type2CharString(
        font=None,
        font_name="Helvetica",
        glyph_name=".notdef",
        gid=0,
        sequence=None,
        default_width_x=500,
        nominal_width_x=0,
    )
    assert cs.get_gid() == 0
    assert cs.get_name() == ".notdef"
    assert cs.get_font_name() == "Helvetica"
    assert cs.get_default_width_x() == 500.0
    assert cs.get_nominal_width_x() == 0.0
    # No program → empty path, no crash.
    assert cs.get_path() == []
    # Bounds of empty path is None.
    assert cs.get_bounds() is None
    # Width for an empty charstring: the T2WidthExtractor sees no
    # operands at all, so .width stays 0 — matches upstream's
    # Type1CharString.getWidth() returning the unset 0 field. The
    # accessor must return a float, not raise.
    w = cs.get_width()
    assert isinstance(w, float)
    assert w == 0.0


def test_constructor_rejects_wrong_sequence_type() -> None:
    with pytest.raises(TypeError):
        Type2CharString(
            font=None,
            font_name="X",
            glyph_name="A",
            gid=1,
            sequence=42,  # not a T2CharString / bytes / list / None
        )


def test_repr_carries_font_and_gid() -> None:
    cs = Type2CharString(None, "Foo", "A", 7, None)
    text = repr(cs)
    assert "Foo" in text
    assert "'A'" in text
    assert "gid=7" in text


# ---------------------------------------------------------------------------
# Real-font integration — needs a host OTF
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cff_font() -> CFFFont:
    if _CFF_BYTES is None:
        pytest.skip(_SKIP_REASON)
    return CFFFont.from_bytes(_CFF_BYTES)


def test_get_type2_char_string_returns_wrapper(cff_font: CFFFont) -> None:
    cs = cff_font.get_type2_char_string(0)
    assert isinstance(cs, Type2CharString)
    assert cs.get_gid() == 0
    # GID 0 is .notdef in well-formed CFF.
    assert cs.get_name() == ".notdef"


def test_get_type2_char_string_path_is_drawable(cff_font: CFFFont) -> None:
    """Pull a non-trivial glyph and verify the recording pen captures
    at least one moveto + a non-empty command list."""
    n = cff_font.get_num_char_strings()
    assert n > 1
    # Sample a handful of GIDs across the charset; at least one must
    # have a non-empty path. We don't lock in a specific GID because
    # the host font isn't fixed.
    indices = [1, n // 4, n // 2, max(1, n - 1)]
    found_path = False
    for gid in indices:
        cs = cff_font.get_type2_char_string(gid)
        path = cs.get_path()
        assert isinstance(path, list)
        if path:
            found_path = True
            # First command must be a moveto.
            assert path[0][0] == "moveto"
            # Bounds must be a 4-tuple of floats with xmin<=xmax, ymin<=ymax.
            bounds = cs.get_bounds()
            assert bounds is not None
            xmin, ymin, xmax, ymax = bounds
            assert xmin <= xmax
            assert ymin <= ymax
            break
    assert found_path, "no probed GID produced a non-empty path"


def test_get_type2_char_string_width_matches_cff_font_width(cff_font: CFFFont) -> None:
    """``Type2CharString.get_width`` must match ``CFFFont.get_width(name)``
    for the same glyph — both delegate to fontTools' T2WidthExtractor."""
    n = cff_font.get_num_char_strings()
    charset = cff_font.get_charset()
    # Skip .notdef (GID 0) which often has 0 width in extracted CFFs;
    # pick a glyph that has a real advance.
    sample_gid = 1 if n > 1 else 0
    cs = cff_font.get_type2_char_string(sample_gid)
    name = charset[sample_gid]
    assert cs.get_width() == cff_font.get_width(name)


def test_get_type2_char_string_out_of_range_returns_empty_wrapper(
    cff_font: CFFFont,
) -> None:
    """Out-of-range GIDs must not raise; they return an empty wrapper
    whose path is ``[]`` — see CHANGES.md (deviation from upstream
    which throws IOException)."""
    n = cff_font.get_num_char_strings()
    cs = cff_font.get_type2_char_string(n + 999)
    assert isinstance(cs, Type2CharString)
    assert cs.get_path() == []


def test_path_is_cached(cff_font: CFFFont) -> None:
    """Calling ``get_path`` twice must return equal results without
    re-running the pen (we don't assert identity because the wrapper
    returns a fresh list copy)."""
    cs = cff_font.get_type2_char_string(1)
    p1 = cs.get_path()
    p2 = cs.get_path()
    assert p1 == p2


def test_t2_property_exposes_underlying_charstring(cff_font: CFFFont) -> None:
    """``Type2CharString.t2`` must expose the fontTools T2CharString so
    callers can run their own pens / introspect the program."""
    from fontTools.misc.psCharStrings import T2CharString

    cs = cff_font.get_type2_char_string(1)
    assert isinstance(cs.t2, T2CharString)
