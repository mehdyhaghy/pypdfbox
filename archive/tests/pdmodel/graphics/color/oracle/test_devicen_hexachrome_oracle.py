"""Live PDFBox differential parity for a HIGH-COLORANT (N>=5) DeviceN colour
space — a hexachrome space with six named colorants and only a tint transform
(no ``/Attributes``), exercising the tint-transform -> alternate -> RGB path at
full arity.

The sibling ``test_devicen_attr_oracle.py`` covers the *attribute-driven* 3-
colorant NChannel DeviceN; this file covers the plain high-channel
tint-transform DeviceN that no other probe builds:

    [/DeviceN [/Cyan /Magenta /Yellow /Black /Orange /Green] /DeviceCMYK <tint>]

The Java side is ``oracle/probes/DeviceNHexachromeProbe.java``. The Type-4 tint
transform maps the 6 tints (c m y k o g) onto a 4-channel CMYK value via
cross-channel mixing (C = c+0.7g, M = m+0.5o, Y = y+0.9o+0.6g, K = k, each
clamped to [0,1] by /Range), written in PURE-STACK PostScript (no named-var
``def``, which PDFBox rejects). Emitted lines:

  ``COLORANTS <name>...``           getColorantNames
  ``NUMCOMPONENTS <n>``            getNumberOfComponents
  ``NCHANNEL <true|false>``        isNChannel
  ``ALTERNATE <name>``             getAlternateColorSpace().getName
  ``INITIAL <c>...``               getInitialColor().getComponents
  ``TORGB <c>... -> r g b``        toRGB (0-255 ints, round(c*255) clamped)

Two parity tiers, by colour-management model:

**Exact-match tier** — pure structure / arithmetic, no CMM: the colorant-name
list (6 names, in order), the component count (6), the NChannel flag (False —
no ``/Attributes``), the alternate colour-space name (DeviceCMYK), and the
initial colour (all-1.0 tuple of arity 6). These COS-driven accessors must
match byte-for-byte.

**Documented-divergence tier** — the tint-transform DeviceN ``toRGB`` evaluates
the Type-4 function to CMYK and routes through DeviceCMYK -> RGB; pypdfbox uses
explicit subtractive CMYK math while PDFBox routes the CMYK step through the JVM
CMM (CGATS001 ICC). The same project-wide DeviceCMYK divergence pinned in
``test_color_to_rgb_oracle.py`` / ``test_devicen_attr_oracle.py``. We assert
pypdfbox matches its deterministic pin AND that at least one tuple differs from
PDFBox, so the structural routing (Type-4 eval -> alternate -> RGB) is verified
while the final CMM step is allowed to diverge.

REGRESSION GUARD: the pinned pypdfbox RGB values caught a real bug (wave 1467) —
``PDFunctionType4.eval`` was returning the WHOLE residual stack (including the 6
unconsumed inputs a pure-stack program leaves behind) instead of only the top N
values declared by /Range, so every tint here mapped onto garbage CMYK. Fixed
to take only the top ``/Range`` values, matching upstream ``popReal`` semantics.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared rounding (must match DeviceNHexachromeProbe.clamp255) ----


def _clamp255(value: float) -> int:
    r = round(value * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _rgb_int(cs: PDDeviceN, comps: list[float]) -> tuple[int, int, int]:
    rgb = cs.to_rgb(comps)
    assert rgb is not None, f"{cs!r}.to_rgb({comps}) returned None"
    return (_clamp255(rgb[0]), _clamp255(rgb[1]), _clamp255(rgb[2]))


# ---------- COS builders mirroring the Java probe exactly ----------

# Pure-stack Type-4 program: C = c+0.7g, M = m+0.5o, Y = y+0.9o+0.6g, K = k.
# Stack bottom..top on entry: c m y k o g (g = index 0). /Range clamps to [0,1].
_TINT_PS = (
    "{ "
    "5 index 1 index 0.7 mul add "
    "5 index 3 index 0.5 mul add "
    "5 index 4 index 0.9 mul add 3 index 0.6 mul add "
    "5 index "
    "}"
)
_COLORANTS = ("Cyan", "Magenta", "Yellow", "Black", "Orange", "Green")


def _type4(domain: list[float], rng: list[float], ps: str) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 4)
    s.set_item("Domain", COSArray.of_cos_floats(domain))
    s.set_item("Range", COSArray.of_cos_floats(rng))
    with s.create_output_stream() as os_:
        os_.write(ps.encode("ascii"))
    return s


def _hexachrome() -> PDDeviceN:
    """6-colorant DeviceN (CMYK + Orange + Green) -> DeviceCMYK via a
    pure-stack Type-4 tint transform; no /Attributes."""
    names = COSArray()
    for nm in _COLORANTS:
        names.add(COSName.get_pdf_name(nm))
    tint = _type4(
        [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        [0, 1, 0, 1, 0, 1, 0, 1],
        _TINT_PS,
    )
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(names)
    arr.add(COSName.get_pdf_name("DeviceCMYK"))
    arr.add(tint)
    return PDDeviceN(arr)


# toRGB input tuples — MUST match DeviceNHexachromeProbe.java in order.
_TINTS: list[list[float]] = [
    [0, 0, 0, 0, 0, 0],
    [1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 1, 0],
    [0, 0, 0, 0, 0, 1],
    [0.2, 0.4, 0.6, 0.1, 0.8, 0.3],
    [0.5, 0.5, 0.5, 0, 0.5, 0.5],
]

# pypdfbox's own deterministic RGB for the CMM-divergent DeviceCMYK tail
# (Type-4 -> subtractive DeviceCMYK -> RGB). Pinned so a regression in the
# Type-4 eval (which returned the whole residual stack before wave 1467) or the
# explicit CMYK math is caught; PDFBox differs because it routes the final CMYK
# step through the JVM CMM.
_PYPDFBOX_RGB: list[tuple[int, int, int]] = [
    (255, 255, 255),
    (0, 0, 0),
    (0, 255, 255),
    (255, 128, 25),
    (77, 255, 102),
    (135, 46, 0),
    (38, 64, 0),
]


def _parse_probe(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        tag = line.split()[0]
        out.setdefault(tag, []).append(line)
    return out


@pytest.fixture(scope="module")
def _probe() -> dict[str, list[str]]:
    return _parse_probe(run_probe_text("DeviceNHexachromeProbe"))


# ---------- accessor parity (exact tier) ----------


@requires_oracle
def test_colorant_names(_probe: dict[str, list[str]]) -> None:
    """getColorantNames() == PDFBox's, in order (6 hexachrome colorants)."""
    java = _probe["COLORANTS"][0].split()[1:]
    assert _hexachrome().get_colorant_names() == java
    assert java == list(_COLORANTS)


@requires_oracle
def test_number_of_components(_probe: dict[str, list[str]]) -> None:
    """getNumberOfComponents() == PDFBox's (6 colorants, N >= 5)."""
    java = int(_probe["NUMCOMPONENTS"][0].split()[1])
    assert _hexachrome().get_number_of_components() == java
    assert java == 6


@requires_oracle
def test_is_n_channel(_probe: dict[str, list[str]]) -> None:
    """isNChannel() == PDFBox's (False — no /Attributes)."""
    java = _probe["NCHANNEL"][0].split()[1] == "true"
    assert _hexachrome().is_n_channel() is java
    assert java is False


@requires_oracle
def test_alternate_color_space_name(_probe: dict[str, list[str]]) -> None:
    """getAlternateColorSpace().getName() == PDFBox's (DeviceCMYK)."""
    java = _probe["ALTERNATE"][0].split()[1]
    alt = _hexachrome().get_alternate_color_space()
    assert alt is not None
    assert alt.get_name() == java


@requires_oracle
def test_initial_color(_probe: dict[str, list[str]]) -> None:
    """getInitialColor().getComponents() == PDFBox's (all-1.0, arity 6)."""
    java = [float(x) for x in _probe["INITIAL"][0].split()[1:]]
    py = list(_hexachrome().get_initial_color().get_components())
    assert py == pytest.approx(java)
    assert py == [1.0] * 6


# ---------- toRGB parity ----------


def _torgb_rows(probe: dict[str, list[str]]) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for line in probe["TORGB"]:
        parts = line.split()
        idx = parts.index("->")
        r, g, b = (int(x) for x in parts[idx + 1 : idx + 4])
        out.append((r, g, b))
    return out


@requires_oracle
def test_to_rgb_documented_divergence(_probe: dict[str, list[str]]) -> None:
    """Tint-transform DeviceN toRGB: the Type-4 function maps the 6 tints to
    CMYK, then routes through DeviceCMYK -> RGB. pypdfbox uses explicit
    subtractive CMYK math while PDFBox routes the CMYK step through the JVM CMM
    (CGATS001 ICC). Assert pypdfbox matches its deterministic pin AND that at
    least one tuple differs from PDFBox — verifying the Type-4 eval + routing
    is correct while allowing the documented final-step CMM divergence."""
    java = _torgb_rows(_probe)
    dn = _hexachrome()
    assert len(java) == len(_TINTS)
    any_diff = False
    for comps, j_rgb, exp in zip(_TINTS, java, _PYPDFBOX_RGB, strict=True):
        py_rgb = _rgb_int(dn, list(comps))
        assert py_rgb == exp, (
            f"hexachrome {comps}: pypdfbox {py_rgb} drifted from pinned {exp}"
        )
        if py_rgb != j_rgb:
            any_diff = True
    assert any_diff, (
        "hexachrome: pypdfbox now matches PDFBox on every tuple — the "
        "documented DeviceCMYK CMM divergence no longer holds."
    )
