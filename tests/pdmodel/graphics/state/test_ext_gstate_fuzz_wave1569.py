"""Fuzz / edge parity for ``PDExtendedGraphicsState`` getters and
``copy_into_graphics_state``.

Hammers each ExtGState entry accessor (/CA /ca /LW /LC /LJ /ML /D /BM
/SMask /AIS /Font) and the ``copyIntoGraphicsState`` apply path, asserting
pypdfbox lands the same result Apache PDFBox 3.0.7 documents:

* Alpha constants (/CA /ca) are returned **raw** — upstream's
  ``getStrokingAlphaConstant`` / ``getNonStrokingAlphaConstant`` return the
  boxed ``Float`` with no [0, 1] clamp; the clamp happens (if at all) in the
  renderer, not the accessor. So a /CA of 1.5 stays 1.5 and -0.3 stays -0.3.
* /BM resolves through ``BlendMode.getInstance`` — absent → Normal, unknown
  name → Normal, COSArray of names → first recognised, /Compatible → Normal.
* /SMask "None" → no soft mask (``get_soft_mask_typed`` returns ``None``);
  a soft-mask dictionary wraps to ``PDSoftMask``.
* ``copy_into_graphics_state`` applies **only present keys** — absent keys
  must not overwrite a seeded graphics-state value with a spec default.
* A present-but-malformed /LW / /ML / /CA / /ca still forwards the spec
  default (upstream ``defaultIfNull``); a present-but-malformed /D clears
  the seeded dash (null-overwrite parity).

These run without the live Java oracle (no ``@requires_oracle``) — the
expected values are the documented upstream semantics. The oracle-gated
companion lives in ``test_ext_gstate_copy_edge_oracle.py``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.graphics.state.pd_graphics_state import PDGraphicsState
from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask


def _ext(**entries: object) -> PDExtendedGraphicsState:
    """Build an ExtGState whose /<key> entries are the given COS values."""
    d = COSDictionary()
    d.set_item(COSName.TYPE, COSName.get_pdf_name("ExtGState"))
    for key, value in entries.items():
        d.set_item(COSName.get_pdf_name(key), value)  # type: ignore[arg-type]
    return PDExtendedGraphicsState(d)


# ---------------------------------------------------------------------------
# /CA and /ca (alpha constants) — raw, no clamp
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [0.0, 0.25, 0.5, 1.0, 1.5, 2.0, -0.3, 100.0],
    ids=["0", "quarter", "half", "1", "over1", "2", "neg", "huge"],
)
def test_stroking_alpha_returned_raw(value: float) -> None:
    # Upstream getStrokingAlphaConstant returns the boxed Float untouched —
    # no [0, 1] clamp at the accessor.
    ext = _ext(CA=COSFloat(value))
    assert ext.get_stroking_alpha_constant() == pytest.approx(value)


@pytest.mark.parametrize(
    "value",
    [0.0, 0.4, 1.0, 1.9, -1.0],
    ids=["0", "mid", "1", "over1", "neg"],
)
def test_non_stroking_alpha_returned_raw(value: float) -> None:
    ext = _ext(ca=COSFloat(value))
    assert ext.get_non_stroking_alpha_constant() == pytest.approx(value)


def test_alpha_absent_returns_none() -> None:
    ext = _ext()
    assert ext.get_stroking_alpha_constant() is None
    assert ext.get_non_stroking_alpha_constant() is None


def test_alpha_malformed_returns_none() -> None:
    # /CA present but not a number → accessor yields None (the spec default
    # is supplied by copy_into_graphics_state, not here).
    ext = _ext(CA=COSName.get_pdf_name("oops"))
    assert ext.get_stroking_alpha_constant() is None


# ---------------------------------------------------------------------------
# /LW /LC /LJ /ML — line params
# ---------------------------------------------------------------------------


def test_line_width_present_and_absent() -> None:
    assert _ext(LW=COSFloat(3.5)).get_line_width() == pytest.approx(3.5)
    assert _ext().get_line_width() is None
    # Present-but-malformed → None at accessor.
    assert _ext(LW=COSName.get_pdf_name("x")).get_line_width() is None


def test_line_cap_sentinel_minus_one_when_absent() -> None:
    # Upstream getLineCapStyle → getInt(LC, -1); absent/malformed is -1.
    assert _ext().get_line_cap_style() == -1
    assert _ext(LC=COSInteger.get(2)).get_line_cap_style() == 2
    assert _ext(LC=COSName.get_pdf_name("bad")).get_line_cap_style() == -1


def test_line_join_sentinel_minus_one_when_absent() -> None:
    assert _ext().get_line_join_style() == -1
    assert _ext(LJ=COSInteger.get(1)).get_line_join_style() == 1
    assert _ext(LJ=COSName.get_pdf_name("bad")).get_line_join_style() == -1


def test_miter_limit_present_and_absent() -> None:
    assert _ext(ML=COSFloat(8.0)).get_miter_limit() == pytest.approx(8.0)
    assert _ext().get_miter_limit() is None


# ---------------------------------------------------------------------------
# /D — dash array + phase
# ---------------------------------------------------------------------------


def _dash_cos(dash: list[float], phase: float) -> COSArray:
    inner = COSArray()
    for v in dash:
        inner.add(COSFloat(v))
    outer = COSArray()
    outer.add(inner)
    outer.add(COSFloat(phase))
    return outer


def test_dash_well_formed() -> None:
    ext = _ext(D=_dash_cos([3.0, 2.0], 1.0))
    pat = ext.get_line_dash_pattern()
    assert pat is not None
    assert pat.get_dash_array() == [3.0, 2.0]
    assert pat.get_phase() == 1


def test_dash_phase_not_ignored() -> None:
    ext = _ext(D=_dash_cos([5.0], 4.0))
    pat = ext.get_line_dash_pattern()
    assert pat is not None
    assert pat.get_phase() == 4


@pytest.mark.parametrize(
    "bad",
    [
        COSArray(),  # size 0
        COSName.get_pdf_name("notarray"),
        COSFloat(2.0),
    ],
    ids=["empty", "name", "float"],
)
def test_dash_malformed_returns_none(bad: object) -> None:
    ext = _ext(D=bad)  # type: ignore[arg-type]
    assert ext.get_line_dash_pattern() is None


def test_dash_size_one_malformed() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(1))
    ext = _ext(D=arr)
    assert ext.get_line_dash_pattern() is None


# ---------------------------------------------------------------------------
# /BM — blend mode
# ---------------------------------------------------------------------------


def test_blend_mode_absent_is_normal() -> None:
    # Upstream getBlendMode never returns null; absent → Normal.
    assert _ext().get_blend_mode() is BlendMode.NORMAL


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Multiply", BlendMode.MULTIPLY),
        ("Screen", BlendMode.SCREEN),
        ("Darken", BlendMode.DARKEN),
        ("HardLight", BlendMode.HARD_LIGHT),
        ("Luminosity", BlendMode.LUMINOSITY),
    ],
    ids=["multiply", "screen", "darken", "hardlight", "luminosity"],
)
def test_blend_mode_named(name: str, expected: BlendMode) -> None:
    assert _ext(BM=COSName.get_pdf_name(name)).get_blend_mode() == expected


def test_blend_mode_unknown_name_is_normal() -> None:
    assert _ext(BM=COSName.get_pdf_name("Bogus")).get_blend_mode() is BlendMode.NORMAL


def test_blend_mode_compatible_is_normal() -> None:
    assert (
        _ext(BM=COSName.get_pdf_name("Compatible")).get_blend_mode()
        is BlendMode.NORMAL
    )


def test_blend_mode_array_first_supported() -> None:
    # COSArray of names → first recognised mode wins.
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Bogus"))
    arr.add(COSName.get_pdf_name("Multiply"))
    arr.add(COSName.get_pdf_name("Screen"))
    assert _ext(BM=arr).get_blend_mode() == BlendMode.MULTIPLY


def test_blend_mode_array_none_recognised_is_normal() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Bogus1"))
    arr.add(COSName.get_pdf_name("Bogus2"))
    assert _ext(BM=arr).get_blend_mode() is BlendMode.NORMAL


# ---------------------------------------------------------------------------
# /SMask — None vs dict
# ---------------------------------------------------------------------------


def test_smask_none_name_is_no_soft_mask() -> None:
    ext = _ext(SMask=COSName.get_pdf_name("None"))
    # Raw accessor returns the name; the typed accessor converts /None to None.
    assert ext.get_soft_mask_typed() is None


def test_smask_absent_is_none() -> None:
    assert _ext().get_soft_mask_typed() is None


def test_smask_dict_wraps_to_soft_mask() -> None:
    sm = COSDictionary()
    sm.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Alpha"))
    ext = _ext(SMask=sm)
    typed = ext.get_soft_mask_typed()
    assert isinstance(typed, PDSoftMask)
    assert typed.is_alpha()


# ---------------------------------------------------------------------------
# /AIS — alpha-is-shape flag
# ---------------------------------------------------------------------------


def test_alpha_source_flag_default_false() -> None:
    assert _ext().get_alpha_source_flag() is False


@pytest.mark.parametrize("flag", [True, False], ids=["true", "false"])
def test_alpha_source_flag_roundtrip(flag: bool) -> None:
    from pypdfbox.cos import COSBoolean

    ext = _ext(AIS=COSBoolean.get(flag))
    assert ext.get_alpha_source_flag() is flag


# ---------------------------------------------------------------------------
# /Font
# ---------------------------------------------------------------------------


def test_font_absent_helpers_return_none() -> None:
    ext = _ext()
    assert ext.get_font() is None
    assert ext.get_font_size() is None


def test_font_size_roundtrip() -> None:
    ext = _ext()
    ext.set_font(COSName.get_pdf_name("F1"))
    ext.set_font_size(12.0)
    assert ext.get_font_size() == pytest.approx(12.0)
    assert ext.get_font() == COSName.get_pdf_name("F1")


# ---------------------------------------------------------------------------
# copy_into_graphics_state — only present keys applied
# ---------------------------------------------------------------------------


def test_copy_absent_keys_do_not_overwrite_seeded_state() -> None:
    gs = PDGraphicsState()
    gs.set_line_width(42.0)
    gs.set_line_cap(2)
    gs.set_line_join(2)
    gs.set_alpha_constant(0.3)
    gs.set_non_stroke_alpha_constant(0.4)
    gs.set_blend_mode(BlendMode.MULTIPLY)
    # Empty ExtGState — applying it must change nothing.
    _ext().copy_into_graphics_state(gs)
    assert gs.get_line_width() == pytest.approx(42.0)
    assert gs.get_line_cap() == 2
    assert gs.get_line_join() == 2
    assert gs.get_alpha_constant() == pytest.approx(0.3)
    assert gs.get_non_stroke_alpha_constant() == pytest.approx(0.4)
    assert gs.get_blend_mode() == BlendMode.MULTIPLY


def test_copy_present_ca_applied_raw() -> None:
    gs = PDGraphicsState()
    gs.set_alpha_constant(0.1)
    # Out-of-range /CA is forwarded raw (no clamp) — parity with upstream.
    _ext(CA=COSFloat(1.5)).copy_into_graphics_state(gs)
    assert gs.get_alpha_constant() == pytest.approx(1.5)


def test_copy_present_ca_ns_applied_raw() -> None:
    gs = PDGraphicsState()
    gs.set_non_stroke_alpha_constant(0.1)
    _ext(ca=COSFloat(-0.2)).copy_into_graphics_state(gs)
    assert gs.get_non_stroke_alpha_constant() == pytest.approx(-0.2)


def test_copy_malformed_lw_pushes_spec_default() -> None:
    gs = PDGraphicsState()
    gs.set_line_width(42.0)
    _ext(LW=COSName.get_pdf_name("notanumber")).copy_into_graphics_state(gs)
    # defaultIfNull(getLineWidth(), 1) → 1.0 overwrites the seed.
    assert gs.get_line_width() == pytest.approx(1.0)


def test_copy_malformed_ml_pushes_spec_default() -> None:
    gs = PDGraphicsState()
    gs.set_miter_limit(99.0)
    _ext(ML=COSName.get_pdf_name("x")).copy_into_graphics_state(gs)
    assert gs.get_miter_limit() == pytest.approx(10.0)


def test_copy_malformed_ca_pushes_spec_default() -> None:
    gs = PDGraphicsState()
    gs.set_alpha_constant(0.3)
    _ext(CA=COSName.get_pdf_name("x")).copy_into_graphics_state(gs)
    assert gs.get_alpha_constant() == pytest.approx(1.0)


def test_copy_malformed_dash_clears_seeded_dash() -> None:
    gs = PDGraphicsState()
    seed = COSArray()
    seed.add(COSFloat(7.0))
    seed.add(COSFloat(7.0))
    gs.set_line_dash_pattern(PDLineDashPattern(seed, 9))
    # A size-1 /D yields None from the getter and that None overwrites.
    mal = COSArray()
    mal.add(COSInteger.get(1))
    _ext(D=mal).copy_into_graphics_state(gs)
    assert gs.get_line_dash_pattern() is None


def test_copy_blend_mode_applied() -> None:
    gs = PDGraphicsState()
    _ext(BM=COSName.get_pdf_name("Screen")).copy_into_graphics_state(gs)
    assert gs.get_blend_mode() == BlendMode.SCREEN


def test_copy_blend_mode_array_applies_first_supported() -> None:
    gs = PDGraphicsState()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Bogus"))
    arr.add(COSName.get_pdf_name("Darken"))
    _ext(BM=arr).copy_into_graphics_state(gs)
    assert gs.get_blend_mode() == BlendMode.DARKEN


def test_copy_present_dash_applied() -> None:
    gs = PDGraphicsState()
    _ext(D=_dash_cos([2.0, 1.0], 3.0)).copy_into_graphics_state(gs)
    pat = gs.get_line_dash_pattern()
    assert pat is not None
    assert pat.get_dash_array() == [2.0, 1.0]
    assert pat.get_phase() == 3


def test_copy_smask_none_sets_no_soft_mask() -> None:
    gs = PDGraphicsState()
    _ext(SMask=COSName.get_pdf_name("None")).copy_into_graphics_state(gs)
    assert gs.get_soft_mask() is None


def test_copy_smask_dict_sets_soft_mask() -> None:
    gs = PDGraphicsState()
    sm = COSDictionary()
    sm.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Luminosity"))
    _ext(SMask=sm).copy_into_graphics_state(gs)
    mask = gs.get_soft_mask()
    assert isinstance(mask, PDSoftMask)
    assert mask.is_luminosity()


def test_copy_ais_applied() -> None:
    from pypdfbox.cos import COSBoolean

    gs = PDGraphicsState()
    assert gs.is_alpha_source() is False
    _ext(AIS=COSBoolean.get(True)).copy_into_graphics_state(gs)
    assert gs.is_alpha_source() is True


def test_copy_line_cap_join_applied() -> None:
    gs = PDGraphicsState()
    _ext(
        LC=COSInteger.get(1),
        LJ=COSInteger.get(2),
    ).copy_into_graphics_state(gs)
    assert gs.get_line_cap() == 1
    assert gs.get_line_join() == 2
