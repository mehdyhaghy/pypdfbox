"""Live PDFBox differential parity for ``PDColorSpace.toRGB`` across the
colour-space hierarchy (DeviceGray/RGB/CMYK, CalGray, CalRGB, Lab, Indexed,
Separation, DeviceN).

The Java side is ``oracle/probes/ColorSpaceProbe.java``: it builds a fixed
battery of colour spaces from in-memory COS objects (no fixture PDF needed)
and, for a fixed set of input component tuples, emits canonical
``csname comp... -> r g b`` lines where r/g/b are 0-255 ints obtained as
``round(component * 255)`` clamped to ``[0, 255]`` — exactly the rounding the
pypdfbox helper below applies. The Python side reconstructs the matching
``PDColorSpace`` subclasses and the same inputs, then compares.

Two parity tiers, by colour-management model:

**Exact-match tier** — pypdfbox and PDFBox agree byte-for-byte. These spaces
either are pure arithmetic (DeviceGray/RGB identity) or route their final
conversion through a path PDFBox also keeps un-managed:

  * DeviceGray, DeviceRGB        — identity / channel replication
  * CalGray                      — neutral axis; PDFBox's AWT sRGB conversion
                                   of an equal-XYZ grey rounds identically to
                                   the IEC D65 matrix pypdfbox uses
  * Indexed (DeviceRGB base)     — palette dereference, no CMM
  * SeparationPS (DeviceGray alt)— Type-4 tint -> grey, no CMM

**Documented-divergence tier** — pypdfbox deliberately differs from PDFBox
because PDFBox routes the final conversion through the JVM's colour-management
module (``java.awt.color.ICC_ColorSpace`` / the bundled
``CGATS001Compat-v2-micro.icc`` CMYK profile) while pypdfbox uses explicit,
platform-deterministic colour math (the project chose this in waves 1330C /
1386 so output never drifts with a bundled-profile or LittleCMS version — see
``pd_device_cmyk.py`` docstring and HISTORY.md line 2415). These are NOT
rounding epsilons (deltas reach 21-34 / 255), so we do not paper over them
with ``pytest.approx``; instead we pin pypdfbox's own deterministic output and
record PDFBox's value alongside for traceability:

  * DeviceCMYK                   — subtractive ``(1-c)(1-k)`` vs ICC profile
  * Separation / DeviceN via CMYK— inherit the DeviceCMYK divergence
  * CalRGB, Lab                  — explicit IEC 61966-2-1 D65 matrix vs the
                                   JVM AWT sRGB profile (D50 PCS + chromatic
                                   adaptation)

A mismatch in the exact tier is a real bug. A change in the divergence tier
means either pypdfbox's deterministic math changed (update the pin + note why)
or PDFBox's CMM output shifted (the recorded reference moved — informational).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared rounding (must match ColorSpaceProbe.clamp255) ----------


def _clamp255(value: float) -> int:
    """round(value * 255), clamped to [0, 255] — mirrors the Java probe."""
    r = round(value * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _rgb_int(cs: object, comps: list[float]) -> tuple[int, int, int]:
    rgb = cs.to_rgb(comps)  # type: ignore[attr-defined]
    assert rgb is not None, f"{cs!r}.to_rgb({comps}) returned None"
    return (_clamp255(rgb[0]), _clamp255(rgb[1]), _clamp255(rgb[2]))


# ---------- COS builders mirroring the Java probe ----------


def _type2(c0: list[float], c1: list[float], n: float = 1.0) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", COSArray.of_cos_floats([0.0, 1.0]))
    d.set_item("C0", COSArray.of_cos_floats(c0))
    d.set_item("C1", COSArray.of_cos_floats(c1))
    d.set_item("N", COSFloat(n))
    return d


def _type4(domain: list[float], rng: list[float], ps: str) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 4)
    s.set_item("Domain", COSArray.of_cos_floats(domain))
    s.set_item("Range", COSArray.of_cos_floats(rng))
    with s.create_output_stream() as os:
        os.write(ps.encode("ascii"))
    return s


def _device_gray() -> PDDeviceGray:
    return PDDeviceGray.INSTANCE


def _device_rgb() -> PDDeviceRGB:
    return PDDeviceRGB.INSTANCE


def _device_cmyk() -> PDDeviceCMYK:
    return PDDeviceCMYK.INSTANCE


def _cal_gray() -> PDCalGray:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalGray"))
    d = COSDictionary()
    d.set_item("WhitePoint", COSArray.of_cos_floats([0.9505, 1.0, 1.089]))
    d.set_item("Gamma", COSFloat(2.2))
    arr.add(d)
    return PDCalGray(arr)


def _cal_rgb() -> PDCalRGB:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalRGB"))
    d = COSDictionary()
    d.set_item("WhitePoint", COSArray.of_cos_floats([1.0, 1.0, 1.0]))
    d.set_item("Gamma", COSArray.of_cos_floats([1.8, 1.8, 1.8]))
    arr.add(d)
    return PDCalRGB(arr)


def _lab() -> PDLab:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Lab"))
    d = COSDictionary()
    d.set_item("WhitePoint", COSArray.of_cos_floats([0.9642, 1.0, 0.8249]))
    d.set_item("Range", COSArray.of_cos_floats([-128, 127, -128, 127]))
    arr.add(d)
    return PDLab(arr)


def _indexed() -> PDColorSpace:
    palette = bytes([0, 0, 0, 255, 0, 0, 0, 255, 0, 128, 128, 255])
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    arr.add(COSInteger.get(3))
    arr.add(COSString(palette))
    cs = PDColorSpace.create(arr)
    assert cs is not None
    return cs


def _separation_cmyk() -> PDSeparation:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name("MySpot"))
    arr.add(COSName.get_pdf_name("DeviceCMYK"))
    arr.add(_type2([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0], 1.0))
    return PDSeparation(arr)


def _separation_ps() -> PDSeparation:
    s4 = _type4([0.0, 1.0], [0.0, 1.0], "{ 1 exch sub }")
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name("PsSpot"))
    arr.add(COSName.get_pdf_name("DeviceGray"))
    arr.add(s4)
    return PDSeparation(arr)


def _device_n() -> PDDeviceN:
    names = COSArray()
    names.add(COSName.get_pdf_name("Spot1"))
    names.add(COSName.get_pdf_name("Spot2"))
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(names)
    arr.add(COSName.get_pdf_name("DeviceCMYK"))
    arr.add(
        _type4(
            [0.0, 1.0, 0.0, 1.0],
            [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
            "{ 0 0 }",
        )
    )
    return PDDeviceN(arr)


# Map the probe's emitted color-space name -> (builder, list of input tuples).
# Inputs MUST match ColorSpaceProbe.java exactly, in the same order.
_BATTERY: dict[str, tuple[object, list[list[float]]]] = {
    "DeviceGray": (_device_gray(), [[0.0], [0.5], [1.0]]),
    "DeviceRGB": (
        _device_rgb(),
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.25, 0.5, 0.75],
            [1.0, 1.0, 1.0],
        ],
    ),
    "DeviceCMYK": (
        _device_cmyk(),
        [
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
            [1.0, 1.0, 1.0, 1.0],
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 1.0, 0.0],
            [0.2, 0.4, 0.6, 0.1],
        ],
    ),
    "CalGray": (_cal_gray(), [[0.0], [0.5], [1.0]]),
    "CalRGB": (
        _cal_rgb(),
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 0.5, 0.5],
            [1.0, 1.0, 1.0],
        ],
    ),
    "Lab": (
        _lab(),
        [
            [0.0, 0.0, 0.0],
            [100.0, 0.0, 0.0],
            [50.0, 80.0, 0.0],
            [50.0, 0.0, -80.0],
            [75.0, -40.0, 40.0],
        ],
    ),
    "Indexed": (_indexed(), [[0.0], [1.0], [2.0], [3.0]]),
    "Separation": (_separation_cmyk(), [[0.0], [0.5], [1.0]]),
    "SeparationPS": (_separation_ps(), [[0.0], [0.5], [1.0]]),
    "DeviceN": (
        _device_n(),
        [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],
    ),
}

# Color spaces whose final conversion PDFBox routes through the JVM CMM while
# pypdfbox uses explicit deterministic math (see module docstring). Differences
# here are expected and documented, not rounding epsilons.
_DIVERGENT = {"DeviceCMYK", "CalRGB", "Lab", "Separation", "DeviceN"}


def _parse_probe(text: str) -> dict[str, list[tuple[int, int, int]]]:
    """Parse ``csname comp... -> r g b`` lines into name -> [(r,g,b), ...]."""
    out: dict[str, list[tuple[int, int, int]]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        left, right = line.split("->")
        name = left.split()[0]
        r, g, b = (int(x) for x in right.split())
        out.setdefault(name, []).append((r, g, b))
    return out


@pytest.fixture(scope="module")
def _java_rgb() -> dict[str, list[tuple[int, int, int]]]:
    return _parse_probe(run_probe_text("ColorSpaceProbe"))


# ---------- exact-match tier ----------


@requires_oracle
@pytest.mark.parametrize(
    "name",
    [n for n in _BATTERY if n not in _DIVERGENT],
)
def test_color_space_to_rgb_exact(
    name: str, _java_rgb: dict[str, list[tuple[int, int, int]]]
) -> None:
    """pypdfbox RGB == PDFBox RGB, byte-for-byte, per input tuple."""
    cs, inputs = _BATTERY[name]
    java = _java_rgb[name]
    assert len(java) == len(inputs), f"{name}: probe emitted {len(java)} rows"
    for comps, j_rgb in zip(inputs, java, strict=True):
        py_rgb = _rgb_int(cs, list(comps))
        assert py_rgb == j_rgb, (
            f"{name} {comps}: pypdfbox {py_rgb} != PDFBox {j_rgb}"
        )


# ---------- documented-divergence tier ----------

# pypdfbox's own deterministic output for the CMM-divergent spaces. Pinned
# here so a regression in pypdfbox's explicit colour math is caught; the
# PDFBox value (different by design) is asserted to actually differ so the
# divergence rationale stays honest if PDFBox's CMM output ever changes.
_PYPDFBOX_DIVERGENT_EXPECTED: dict[str, list[tuple[int, int, int]]] = {
    # subtractive (1-c)(1-k); PDFBox uses CGATS001 ICC profile
    "DeviceCMYK": [
        (255, 255, 255),
        (0, 0, 0),
        (0, 0, 0),
        (0, 255, 255),
        (255, 0, 0),
        (184, 138, 92),
    ],
    # IEC 61966-2-1 D65 matrix; PDFBox uses AWT sRGB profile (D50 PCS)
    "CalRGB": [
        (0, 0, 0),
        (255, 0, 67),
        (159, 142, 140),
        (255, 249, 244),
    ],
    "Lab": [
        (0, 0, 0),
        (255, 252, 221),
        (238, 0, 106),
        (0, 125, 227),
        (141, 201, 87),
    ],
    # Separation/DeviceN via DeviceCMYK alternate inherit the CMYK divergence
    "Separation": [
        (255, 255, 255),
        (255, 128, 128),
        (255, 0, 0),
    ],
    "DeviceN": [
        (255, 255, 255),
        (0, 255, 255),
        (255, 0, 255),
        (128, 128, 255),
    ],
}


@requires_oracle
@pytest.mark.parametrize("name", sorted(_DIVERGENT))
def test_color_space_to_rgb_documented_divergence(
    name: str, _java_rgb: dict[str, list[tuple[int, int, int]]]
) -> None:
    """pypdfbox produces its pinned deterministic RGB; PDFBox differs because
    it routes through the JVM colour-management module. We assert both: that
    pypdfbox matches its pin (regression guard) AND that at least one tuple
    differs from PDFBox (keeps the divergence rationale honest)."""
    cs, inputs = _BATTERY[name]
    java = _java_rgb[name]
    expected = _PYPDFBOX_DIVERGENT_EXPECTED[name]
    assert len(java) == len(inputs)
    any_diff = False
    for comps, j_rgb, exp in zip(inputs, java, expected, strict=True):
        py_rgb = _rgb_int(cs, list(comps))
        assert py_rgb == exp, (
            f"{name} {comps}: pypdfbox {py_rgb} drifted from pinned {exp}"
        )
        if py_rgb != j_rgb:
            any_diff = True
    assert any_diff, (
        f"{name}: pypdfbox now matches PDFBox on every tuple — the documented "
        f"CMM divergence no longer holds; move {name} to the exact-match tier."
    )
