"""Live PDFBox differential parity for the SPECIAL colour-space ``toRGB``
surface that ``test_color_space_to_rgb_oracle.py`` does not exercise:

* **Separation** with the ``/All`` and ``/None`` colorants (edge-case colorant
  names; upstream ``PDSeparation.toRGB`` routes both through the tint transform
  unchanged — the name only matters at render time, not for ``toRGB``),
* a **3-colorant DeviceN** (the sibling test only covers 2 colorants),
* **Indexed** index clamping / rounding edge cases (negative index, fractional
  index that rounds up/down, index past ``hival``, surplus lookup bytes) over
  both a DeviceGray and a DeviceRGB base,
* **Lab** with a custom ``/Range``,
* **ICCBased** N∈{1,3,4}: an embedded sRGB profile and the N-component
  ``/Alternate`` fallback that fires when the embedded profile is missing /
  unreadable.

The Java side is ``oracle/probes/ColorToRgbSpecialProbe.java``. It builds each
colour space from in-memory COS objects and, for a fixed set of input tuples,
emits ``csname comp... -> r g b`` lines (RGB are 0-255 ints,
``round(component*255)`` clamped to ``[0, 255]``). The probe takes the path to
a small sRGB ``.icc`` profile as ``argv[0]`` so both sides embed byte-identical
profile bytes (generated here via Pillow's ``ImageCms``).

Three parity tiers, by colour-management model — same taxonomy as the sibling
``test_color_space_to_rgb_oracle.py``:

**Exact-match tier** — pypdfbox and PDFBox agree byte-for-byte because the
conversion is pure arithmetic / a palette dereference / a pure-grey alternate,
none of which touches a CMM:

  * SepAllGray, DeviceN3Gray   — tint -> DeviceGray, no CMM
  * IdxGray, IdxRgb            — palette dereference + index clamp
  * IccFallbackRgb / IccFallbackGray
                               — empty profile -> /Alternate DeviceRGB/Gray

**Tolerance tier** — a CMM is involved but the transform is near-identity:

  * IccSrgb                    — embedded sRGB profile -> sRGB output. PDFBox
                                 routes through the JVM AWT CMM, pypdfbox
                                 through Pillow/LittleCMS2. Both are sRGB->sRGB
                                 so they agree to within <=2/255 (the CMM
                                 LSB-rounding tolerance; observed delta is 1 on
                                 the green channel of one tuple).

**Documented-divergence tier** — pypdfbox uses explicit deterministic colour
math while PDFBox routes the final step through the JVM CMM (the project chose
this in waves 1330C / 1386; see ``pd_device_cmyk.py`` / HISTORY.md). Deltas
reach 18-34/255, so these are NOT rounding epsilons:

  * SepAll, SepNone, DeviceN3  — tint -> DeviceCMYK (subtractive vs CGATS001 ICC)
  * IccFallbackCmyk            — /Alternate DeviceCMYK (inherits CMYK divergence)
  * LabCustom                  — IEC 61966-2-1 D65 matrix vs AWT sRGB (D50 PCS)

A mismatch in the exact tier is a real bug (deterministic tint routing / palette
lookup / fallback). A drift in the divergence tier means pypdfbox's explicit
math changed (update the pin) or PDFBox's CMM output shifted (informational).
"""

from __future__ import annotations

import contextlib
import os
import tempfile

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
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared rounding (must match ColorToRgbSpecialProbe.clamp255) ----------


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


def _build_srgb_icc() -> bytes:
    """An sRGB ICC profile via Pillow's ImageCms (LittleCMS2-backed), RGB
    colour space so /N == 3. Pillow is a declared dependency. Generated the
    same way the Java probe consumes it (via the file we hand it on argv) so
    both sides embed byte-identical profile bytes."""
    from PIL import ImageCms

    profile = ImageCms.createProfile("sRGB")
    return ImageCms.ImageCmsProfile(profile).tobytes()


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
    with s.create_output_stream() as os_:
        os_.write(ps.encode("ascii"))
    return s


def _sep(colorant: str, alternate: str, tint: object) -> PDSeparation:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name(colorant))
    arr.add(COSName.get_pdf_name(alternate))
    arr.add(tint.get_cos_object())  # type: ignore[attr-defined]
    return PDSeparation(arr)


def _sep_all_cmyk() -> PDSeparation:
    return _sep(
        "All", "DeviceCMYK", _type2([0, 0, 0, 0], [1, 1, 1, 1], 1.0)
    )


def _sep_none_cmyk() -> PDSeparation:
    return _sep(
        "None", "DeviceCMYK", _type2([0, 0, 0, 0], [0, 0, 0, 1], 1.0)
    )


def _sep_all_gray() -> PDSeparation:
    return _sep(
        "All", "DeviceGray", _type4([0, 1], [0, 1], "{ 1 exch sub }")
    )


def _device_n3_cmyk() -> PDDeviceN:
    names = COSArray()
    for nm in ("SpotA", "SpotB", "SpotC"):
        names.add(COSName.get_pdf_name(nm))
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(names)
    arr.add(COSName.get_pdf_name("DeviceCMYK"))
    arr.add(_type4([0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 0, 1, 0, 1], "{ 0 }"))
    return PDDeviceN(arr)


def _device_n3_gray() -> PDDeviceN:
    names = COSArray()
    for nm in ("G1", "G2", "G3"):
        names.add(COSName.get_pdf_name(nm))
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(names)
    arr.add(COSName.get_pdf_name("DeviceGray"))
    arr.add(_type4([0, 1, 0, 1, 0, 1], [0, 1], "{ add add 3 div 1 exch sub }"))
    return PDDeviceN(arr)


def _indexed(base: str, hival: int, palette: bytes) -> PDColorSpace:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(COSName.get_pdf_name(base))
    arr.add(COSInteger.get(hival))
    arr.add(COSString(palette))
    cs = PDColorSpace.create(arr)
    assert cs is not None
    return cs


def _idx_gray() -> PDColorSpace:
    return _indexed("DeviceGray", 2, bytes([0, 128, 255]))


def _idx_rgb() -> PDColorSpace:
    return _indexed(
        "DeviceRGB", 1, bytes([10, 20, 30, 200, 100, 50, 255, 255, 255])
    )


def _lab_custom() -> PDLab:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Lab"))
    d = COSDictionary()
    d.set_item("WhitePoint", COSArray.of_cos_floats([0.9642, 1.0, 0.8249]))
    d.set_item("Range", COSArray.of_cos_floats([-100, 100, -100, 100]))
    arr.add(d)
    return PDLab(arr)


def _icc_srgb(icc_bytes: bytes) -> PDColorSpace:
    s = COSStream()
    s.set_int("N", 3)
    with s.create_output_stream() as os_:
        os_.write(icc_bytes)
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(s)
    cs = PDColorSpace.create(arr)
    assert cs is not None
    return cs


def _icc_fallback(n: int, alternate: str) -> PDColorSpace:
    s = COSStream()
    s.set_int("N", n)
    s.set_item("Alternate", COSName.get_pdf_name(alternate))
    with s.create_output_stream() as os_:
        os_.write(b"")
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(s)
    cs = PDColorSpace.create(arr)
    assert cs is not None
    return cs


# Map the probe's emitted color-space name -> (builder, list of input tuples).
# Inputs MUST match ColorToRgbSpecialProbe.java exactly, in the same order.
def _battery(icc_bytes: bytes) -> dict[str, tuple[object, list[list[float]]]]:
    return {
        "SepAll": (_sep_all_cmyk(), [[0.0], [0.5], [1.0]]),
        "SepNone": (_sep_none_cmyk(), [[0.0], [0.5], [1.0]]),
        "SepAllGray": (_sep_all_gray(), [[0.0], [0.25], [1.0]]),
        "DeviceN3": (
            _device_n3_cmyk(),
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [0.3, 0.6, 0.9],
            ],
        ),
        "DeviceN3Gray": (
            _device_n3_gray(),
            [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [0.3, 0.6, 0.9]],
        ),
        "IdxGray": (
            _idx_gray(),
            [[-1.0], [0.0], [0.4], [0.6], [1.0], [2.0], [5.0]],
        ),
        "IdxRgb": (_idx_rgb(), [[0.0], [1.0], [2.0]]),
        "LabCustom": (
            _lab_custom(),
            [[25.0, 60.0, -60.0], [90.0, -30.0, 70.0], [0.0, 0.0, 0.0]],
        ),
        "IccSrgb": (
            _icc_srgb(icc_bytes),
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [0.25, 0.5, 0.75],
                [1.0, 1.0, 1.0],
            ],
        ),
        "IccFallbackRgb": (
            _icc_fallback(3, "DeviceRGB"),
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.25, 0.5, 0.75]],
        ),
        "IccFallbackGray": (
            _icc_fallback(1, "DeviceGray"),
            [[0.0], [0.5], [1.0]],
        ),
        "IccFallbackCmyk": (
            _icc_fallback(4, "DeviceCMYK"),
            [
                [0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
                [1.0, 0.0, 0.0, 0.0],
                [0.2, 0.4, 0.6, 0.1],
            ],
        ),
    }


# Exact-match tier: pure arithmetic / palette / pure-grey alternate, no CMM.
_EXACT = {
    "SepAllGray",
    "DeviceN3Gray",
    "IdxGray",
    "IdxRgb",
    "IccFallbackRgb",
    "IccFallbackGray",
}

# Tolerance tier: a CMM is involved but the transform is near-identity (sRGB).
_TOLERANCE = {"IccSrgb"}
_TOLERANCE_MAX_DELTA = 2  # <= 2/255, CMM LSB rounding (LittleCMS2 vs AWT)

# Documented-divergence tier: explicit deterministic math vs the JVM CMM.
_DIVERGENT = {"SepAll", "SepNone", "DeviceN3", "IccFallbackCmyk", "LabCustom"}


def _parse_probe(text: str) -> dict[str, list[tuple[int, int, int]]]:
    """Parse ``csname comp... -> r g b`` lines into name -> [(r,g,b), ...]."""
    out: dict[str, list[tuple[int, int, int]]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or "->" not in line:
            continue
        left, right = line.split("->")
        name = left.split()[0]
        r, g, b = (int(x) for x in right.split())
        out.setdefault(name, []).append((r, g, b))
    return out


@pytest.fixture(scope="module")
def _icc_bytes() -> bytes:
    return _build_srgb_icc()


@pytest.fixture(scope="module")
def _java_rgb(_icc_bytes: bytes) -> dict[str, list[tuple[int, int, int]]]:
    # mkstemp returns an os-level fd (no open Python file object) so we close
    # it immediately and let the Java probe own the path — avoids the Windows
    # "file opened exclusively" reopen problem. unlink in finally after the
    # probe (a separate process) has fully exited.
    fd, tmp_name = tempfile.mkstemp(suffix=".icc")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(_icc_bytes)
        text = run_probe_text("ColorToRgbSpecialProbe", tmp_name)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
    return _parse_probe(text)


# ---------- exact-match tier ----------


@requires_oracle
@pytest.mark.parametrize("name", sorted(_EXACT))
def test_special_color_to_rgb_exact(
    name: str,
    _icc_bytes: bytes,
    _java_rgb: dict[str, list[tuple[int, int, int]]],
) -> None:
    """pypdfbox RGB == PDFBox RGB, byte-for-byte, per input tuple. These spaces
    route through pure arithmetic / a palette dereference / a pure-grey or RGB
    /Alternate, so a mismatch is a real deterministic bug (tint routing, index
    clamp/rounding, or fallback-to-alternate)."""
    cs, inputs = _battery(_icc_bytes)[name]
    java = _java_rgb[name]
    assert len(java) == len(inputs), f"{name}: probe emitted {len(java)} rows"
    for comps, j_rgb in zip(inputs, java, strict=True):
        py_rgb = _rgb_int(cs, list(comps))
        assert py_rgb == j_rgb, (
            f"{name} {comps}: pypdfbox {py_rgb} != PDFBox {j_rgb}"
        )


# ---------- tolerance tier ----------


@requires_oracle
@pytest.mark.parametrize("name", sorted(_TOLERANCE))
def test_special_color_to_rgb_tolerance(
    name: str,
    _icc_bytes: bytes,
    _java_rgb: dict[str, list[tuple[int, int, int]]],
) -> None:
    """An embedded sRGB profile is converted sRGB->sRGB through a CMM on both
    sides (Pillow/LittleCMS2 here, AWT in PDFBox). Output agrees within the
    documented <=2/255 CMM LSB-rounding tolerance."""
    cs, inputs = _battery(_icc_bytes)[name]
    java = _java_rgb[name]
    assert len(java) == len(inputs)
    for comps, j_rgb in zip(inputs, java, strict=True):
        py_rgb = _rgb_int(cs, list(comps))
        for chan, (p, j) in enumerate(zip(py_rgb, j_rgb, strict=True)):
            assert abs(p - j) <= _TOLERANCE_MAX_DELTA, (
                f"{name} {comps} channel {chan}: pypdfbox {p} vs PDFBox {j} "
                f"exceeds the {_TOLERANCE_MAX_DELTA}/255 CMM tolerance"
            )


# ---------- documented-divergence tier ----------

# pypdfbox's own deterministic output for the CMM-divergent spaces. Pinned so a
# regression in pypdfbox's explicit colour math is caught; the PDFBox value
# (different by design) is asserted to actually differ so the divergence
# rationale stays honest if PDFBox's CMM output ever changes.
_PYPDFBOX_DIVERGENT_EXPECTED: dict[str, list[tuple[int, int, int]]] = {
    # tint -> DeviceCMYK (subtractive (1-c)(1-k)); PDFBox uses CGATS001 ICC.
    "SepAll": [(255, 255, 255), (64, 64, 64), (0, 0, 0)],
    "SepNone": [(255, 255, 255), (128, 128, 128), (0, 0, 0)],
    "DeviceN3": [
        (255, 255, 255),
        (0, 255, 255),
        (255, 0, 255),
        (255, 255, 0),
        (178, 102, 25),
    ],
    "IccFallbackCmyk": [
        (255, 255, 255),
        (0, 0, 0),
        (0, 255, 255),
        (184, 138, 92),
    ],
    # IEC 61966-2-1 D65 matrix; PDFBox uses the AWT sRGB profile (D50 PCS).
    "LabCustom": [(108, 0, 134), (218, 238, 52), (0, 0, 0)],
}


@requires_oracle
@pytest.mark.parametrize("name", sorted(_DIVERGENT))
def test_special_color_to_rgb_documented_divergence(
    name: str,
    _icc_bytes: bytes,
    _java_rgb: dict[str, list[tuple[int, int, int]]],
) -> None:
    """pypdfbox produces its pinned deterministic RGB; PDFBox differs because
    it routes the DeviceCMYK / Lab step through the JVM colour-management
    module. We assert both: that pypdfbox matches its pin (regression guard)
    AND that at least one tuple differs from PDFBox (keeps the divergence
    rationale honest)."""
    cs, inputs = _battery(_icc_bytes)[name]
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
