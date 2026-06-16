"""Blend-mode RESOLUTION + separable per-channel blend parity with PDFBox 3.0.7.

Targets the pure algebra the rendering probes (``BlendAlphaProbe`` /
``HighlightBlendProbe`` / ``TransparencyGroupCompositeProbe``) sit on top of
but never exercise in isolation:

* ``BlendMode.get_instance(COSBase)`` over a fuzz grid of ``/BM`` values —
  a plain ``COSName`` for each of the 16 standard modes, the ``Compatible``
  alias (→ ``Normal``), unknown names (→ ``Normal``), a ``COSArray`` of names
  where "first recognised wins" (PDF 32000-1 §11.3.5 fallback chain), arrays
  whose leading entry is unknown / a non-name, an empty array, a ``None``
  operand, and non-name / non-array operands (``COSInteger`` / ``COSString``).
  Each resolved mode is checked by NAME and by ``is_separable_blend_mode()``.

  Critically, upstream's ``getInstance`` returns the canonical singleton, so
  an unknown name resolves to the ``Normal`` instance whose ``getCOSName()``
  is ``Normal`` (not the original name). pypdfbox ``get_instance`` mirrors
  this (it is the rendering-time resolver; ``from_cos`` is the round-trip
  promoter that preserves unknown names — out of scope here).

* the per-channel separable blend function
  ``get_blend_channel_function().blend_channel(src, backdrop)`` evaluated over
  the Cartesian grid ``{0, 0.25, 0.5, 0.75, 1.0}^2`` (25 pairs per mode).
  Upstream ``BlendChannelFunction.blendChannel(float, float)`` takes
  ``(src, dest)`` — empirically confirmed against the live jar (ColorDodge /
  HardLight are asymmetric) — matching pypdfbox ``BlendMode.blend(
  source_channel, backdrop_channel)``.

* channel-function presence: separable modes expose a callable; the four
  non-separable HSL modes return ``None`` (no scalar function — they blend
  RGB triples).

Both sides are pinned exactly (RESOLVE / CHANFN are string-identical; BLEND
floats compared with a small tolerance for the float32-vs-float64 gap).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSString
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)

_SEPARABLE = (
    "Normal", "Multiply", "Screen", "Overlay", "Darken", "Lighten",
    "ColorDodge", "ColorBurn", "HardLight", "SoftLight",
    "Difference", "Exclusion",
)
_NON_SEPARABLE = ("Hue", "Saturation", "Color", "Luminosity")

# Float tolerance — Java evaluates the blend lambdas in float32; pypdfbox in
# float64. The grid values are exact in both, so divergence is only the last
# couple of float32 ULPs of an irrational result (e.g. SoftLight's sqrt).
_TOL = 5e-4


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


# ---------------------------------------------------------------------------
# Resolution fuzz cases. Each builder returns the /BM operand passed to
# get_instance; the expected resolved name + separable flag come from the
# live oracle (keyed by the leading "RESOLVE <label>" tokens).
# ---------------------------------------------------------------------------
def _resolve_cases() -> tuple[tuple[str, object], ...]:
    cases: list[tuple[str, object]] = []
    for mode_name in (*_SEPARABLE, *_NON_SEPARABLE):
        cases.append((f"name_{mode_name}", _name(mode_name)))
    cases.extend(
        [
            ("name_Compatible", _name("Compatible")),
            ("name_Unknown", _name("Bogus")),
            ("name_empty", _name("")),
            ("name_lowercase", _name("multiply")),
            ("null", None),
            ("integer", COSInteger.get(3)),
            ("string", COSString("Multiply")),
            ("arr_first_wins", COSArray([_name("Darken"), _name("Screen")])),
            (
                "arr_unknown_then_known",
                COSArray([_name("Bogus"), _name("ColorBurn")]),
            ),
            (
                "arr_two_unknown_then_known",
                COSArray([_name("Foo"), _name("Bar"), _name("Hue")]),
            ),
            ("arr_all_unknown", COSArray([_name("Foo"), _name("Bar")])),
            (
                "arr_compatible_first",
                COSArray([_name("Compatible"), _name("Multiply")]),
            ),
            (
                "arr_nonname_then_known",
                COSArray([COSInteger.get(1), _name("Lighten")]),
            ),
            ("arr_empty", COSArray()),
            ("arr_single", COSArray([_name("SoftLight")])),
        ]
    )
    return tuple(cases)


_RESOLVE_CASES = _resolve_cases()


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    lines = run_probe_text("BlendModeFuzzProbe").splitlines()
    return {" ".join(line.split(" ", 2)[:2]): line for line in lines}


@requires_oracle
@pytest.mark.parametrize(
    ("label", "operand"),
    _RESOLVE_CASES,
    ids=[label for label, _ in _RESOLVE_CASES],
)
def test_resolution_matches_oracle(
    label: str, operand: object, java_lines: dict[str, str]
) -> None:
    mode = BlendMode.get_instance(operand)  # type: ignore[arg-type]
    sep = "true" if mode.is_separable_blend_mode() else "false"
    python_line = f"RESOLVE {label} name={mode.get_name()} sep={sep}"
    assert python_line == java_lines[f"RESOLVE {label}"]


@requires_oracle
@pytest.mark.parametrize("mode_name", (*_SEPARABLE, *_NON_SEPARABLE))
def test_channel_function_presence_matches_oracle(
    mode_name: str, java_lines: dict[str, str]
) -> None:
    mode = BlendMode.get(mode_name)
    present = "true" if mode.get_blend_channel_function() is not None else "false"
    python_line = f"CHANFN {mode_name} present={present}"
    assert python_line == java_lines[f"CHANFN {mode_name}"]


def _parse_blend_pairs(line: str) -> dict[tuple[str, str], float]:
    """Parse a ``BLEND <Mode> s:b=v ...`` line into {(s_str, b_str): value}."""
    parsed: dict[tuple[str, str], float] = {}
    for token in line.split(" ")[2:]:
        coords, value = token.split("=")
        s_str, b_str = coords.split(":")
        parsed[(s_str, b_str)] = float(value)
    return parsed


@requires_oracle
@pytest.mark.parametrize("mode_name", _SEPARABLE)
def test_separable_blend_grid_matches_oracle(
    mode_name: str, java_lines: dict[str, str]
) -> None:
    java_pairs = _parse_blend_pairs(java_lines[f"BLEND {mode_name}"])
    mode = BlendMode.get(mode_name)
    fn = mode.get_blend_channel_function()
    assert fn is not None
    # Exactly the 25-pair grid is projected.
    assert len(java_pairs) == len(_GRID) * len(_GRID)
    for s in _GRID:
        for b in _GRID:
            s_str = _canon(s)
            b_str = _canon(b)
            py_value = fn(s, b)
            assert py_value == pytest.approx(mode.blend(s, b))
            assert py_value == pytest.approx(
                java_pairs[(s_str, b_str)], abs=_TOL
            ), f"{mode_name} blend({s}, {b})"


def _canon(value: float) -> str:
    """Mirror the probe's grid label (0, 0.25, 0.5, 0.75, 1)."""
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Value-pinned contract checks (no oracle dependency) for behaviour the
# above grid does not surface directly.
# ---------------------------------------------------------------------------
def test_non_separable_blend_raises_from_scalar_blend() -> None:
    for mode_name in _NON_SEPARABLE:
        mode = BlendMode.get(mode_name)
        with pytest.raises(ValueError):
            mode.blend(0.5, 0.5)
        # The RGB-triple path works for the same mode.
        result = mode.blend_separable_rgb((0.3, 0.6, 0.9), (0.2, 0.5, 0.8))
        assert len(result) == 3


def test_unknown_name_blend_falls_back_to_normal() -> None:
    # get_instance collapses unknowns to Normal, but a directly-interned
    # unknown name (via get) still blends as Normal for rendering.
    bogus = BlendMode.get("Bogus")
    assert bogus.get_blend_channel_function() is None
    assert bogus.blend(0.42, 0.13) == 0.42  # Normal: returns source.


def test_array_first_recognised_wins_python_side() -> None:
    operand = COSArray([_name("Bogus"), _name("Multiply"), _name("Screen")])
    assert BlendMode.get_instance(operand) is BlendMode.MULTIPLY


def test_channel_function_is_reusable_singleton() -> None:
    # Capturing the callable once and reusing matches per-call blend().
    fn = BlendMode.MULTIPLY.get_blend_channel_function()
    assert fn is not None
    assert fn(0.5, 0.5) == BlendMode.MULTIPLY.blend(0.5, 0.5) == 0.25
