"""Live PDFBox differential parity for ``PDIndexed.toRGB`` where the
``/Indexed`` base is a non-Device colour space — ``CalRGB`` (gamma + matrix +
white point), ``CalGray`` (gamma + white point), and ``ICCBased`` (embedded
sRGB profile).

The Java side is ``oracle/probes/IndexedCalProbe.java``. It constructs
``[/Indexed base hival lookup]`` arrays with a literal-stream ``/Lookup`` (one
byte per base component per palette entry) and emits ``csname index -> r g b``
lines for a set of indices INCLUDING out-of-range values (``-1`` clamped to
``0``, ``>= hival`` clamped to ``actualMaxIndex``).

Upstream behaviour (verified by disassembling PDFBox 3.0.7's
``PDIndexed.initRgbColorTable``):

* The cached ``rgbColorTable`` is built by feeding each palette entry through
  the base CS's ``toRGBImage(WritableRaster)``. For a ``CalRGB`` / ``CalGray``
  base that's the AWT CMM (D50 PCS); for an embedded sRGB ``ICCBased`` profile
  it's the profile's transform.
* ``PDIndexed.toRGB(float[])`` then returns ``rgbColorTable[clamp(index)] /
  255f`` — pure palette dereference + ``/ 255``.

Two parity tiers:

**ICC sRGB tier** — ``IdxIccSrgb``. The base profile is sRGB and the lookup
bytes already live in sRGB; LittleCMS2 (pypdfbox) and AWT CMM (PDFBox) agree
to within the documented ``<= 2/255`` CMM LSB-rounding tolerance — the same
tolerance the standalone ``IccSrgb`` row of ``test_color_to_rgb_oracle.py``
applies. Clamp behaviour for out-of-range indices is byte-exact (the clamp is
pure integer logic; only the per-entry RGB conversion involves a CMM).

**Documented-divergence tier** — ``IdxCalRgb`` / ``IdxCalGray``. The gamma
decode and ``/Matrix`` application are deterministic float arithmetic
identical on both sides, but the FINAL XYZ → sRGB step diverges (pypdfbox:
explicit IEC 61966-2-1 D65 matrix, same as the rest of the colour module;
PDFBox: the JVM AWT CMM via D50 PCS). pypdfbox's own output is pinned
(regression guard for the gamma decode / matrix application / XYZ → sRGB
matrix) and at least one tuple is asserted to differ from PDFBox so the
divergence rationale stays honest. The clamp branches (``-1`` and indices
above ``hival``) are byte-exact regardless — they merely re-fetch a cached
palette entry whose value is the divergent one, so equality with PDFBox
holds iff the in-range entry happens to match.

The probe takes the same kind of sRGB ICC profile bytes as
``ColorToRgbSpecialProbe`` does (we mint them via Pillow's
``ImageCms.createProfile("sRGB")`` here so both sides embed byte-identical
profile bytes) and we pass the file path on argv so the Java side reads it
back; the temp file is deleted in ``finally`` after the probe process exits.
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
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared rounding (must match IndexedCalProbe.clamp255) ----------


def _clamp255(value: float) -> int:
    r = round(value * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _rgb_int(cs: PDIndexed, index: int) -> tuple[int, int, int]:
    rgb = cs.to_rgb([float(index)])
    assert rgb is not None, f"{cs!r}.to_rgb([{index}]) returned None"
    return (_clamp255(rgb[0]), _clamp255(rgb[1]), _clamp255(rgb[2]))


# ---------- COS builders mirroring the Java probe ----------


def _floats(vals: list[float]) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(v))
    return a


def _build_srgb_icc() -> bytes:
    """Mint an sRGB ICC profile via Pillow's ImageCms (LittleCMS2-backed). The
    Java probe consumes the same bytes via its argv path argument."""
    from PIL import ImageCms

    profile = ImageCms.createProfile("sRGB")
    return ImageCms.ImageCmsProfile(profile).tobytes()


def _cal_rgb_unit() -> PDCalRGB:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalRGB"))
    d = COSDictionary()
    d.set_item("WhitePoint", _floats([1.0, 1.0, 1.0]))
    d.set_item("Gamma", _floats([1.8, 2.2, 2.4]))
    d.set_item(
        "Matrix",
        _floats(
            [
                0.4124, 0.2126, 0.0193,
                0.3576, 0.7152, 0.1192,
                0.1805, 0.0722, 0.9505,
            ]
        ),
    )
    arr.add(d)
    return PDCalRGB(arr)


def _cal_gray_unit() -> PDCalGray:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalGray"))
    d = COSDictionary()
    d.set_item("WhitePoint", _floats([1.0, 1.0, 1.0]))
    d.set_item("Gamma", COSFloat(2.2))
    arr.add(d)
    return PDCalGray(arr)


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


def _indexed_over(base: PDColorSpace, hival: int, palette: bytes) -> PDIndexed:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(base.get_cos_object())
    arr.add(COSInteger.get(hival))
    arr.add(COSString(palette))
    return PDIndexed(arr)


# Palette bytes MUST match IndexedCalProbe.java exactly.
_CAL_RGB_PALETTE = bytes(
    [
        0, 0, 0,
        255, 0, 0,
        128, 128, 128,
        64, 192, 32,
    ]
)
_CAL_GRAY_PALETTE = bytes([0, 64, 128, 192, 255])
_ICC_SRGB_PALETTE = bytes(
    [
        0, 0, 0,
        255, 0, 0,
        64, 128, 192,
        255, 255, 255,
    ]
)

_INDICES_4 = [-1, 0, 1, 2, 3, 4, 7]
_INDICES_5 = [-1, 0, 1, 2, 3, 4, 5, 10]


def _battery(icc_bytes: bytes) -> dict[str, tuple[PDIndexed, list[int]]]:
    return {
        "IdxCalRgb": (
            _indexed_over(_cal_rgb_unit(), 3, _CAL_RGB_PALETTE),
            _INDICES_4,
        ),
        "IdxCalGray": (
            _indexed_over(_cal_gray_unit(), 4, _CAL_GRAY_PALETTE),
            _INDICES_5,
        ),
        "IdxIccSrgb": (
            _indexed_over(_icc_srgb(icc_bytes), 3, _ICC_SRGB_PALETTE),
            _INDICES_4,
        ),
    }


# ICC sRGB → sRGB is a near-identity transform; LittleCMS2 vs AWT CMM agree
# within the same 2/255 LSB-rounding window applied to the standalone ICC sRGB
# row of ``test_color_to_rgb_oracle.py``.
_TOLERANCE = {"IdxIccSrgb"}
_TOLERANCE_MAX_DELTA = 2

# Documented-divergence tier: the calibrated CIE pipeline whose final
# XYZ → sRGB step routes through the AWT CMM (D50 PCS) in PDFBox vs the
# explicit IEC 61966-2-1 D65 matrix in pypdfbox.
_DIVERGENT = {"IdxCalRgb", "IdxCalGray"}

# pypdfbox's own deterministic output for the Cal*-base spaces. Pinned so a
# regression in the gamma decode / matrix application / XYZ → sRGB matrix
# (or the per-entry palette slicing inside ``init_rgb_color_table``) is caught;
# the PDFBox value (different by design — JVM CMM) is asserted to actually
# differ on at least one tuple so the divergence rationale stays honest.
_PYPDFBOX_DIVERGENT_EXPECTED: dict[str, list[tuple[int, int, int]]] = {
    # hival=3: -1 → 0 (clamped), 4 / 7 → 3 (clamped to actualMaxIndex).
    "IdxCalRgb": [
        (0, 0, 0),       # -1 clamped
        (0, 0, 0),       # 0
        (255, 0, 0),     # 1
        (146, 129, 121), # 2 mid grey
        (81, 193, 20),   # 3 mixed
        (81, 193, 20),   # 4 → 3
        (81, 193, 20),   # 7 → 3
    ],
    # hival=4: -1 → 0, 5 / 10 → 4.
    "IdxCalGray": [
        (0, 0, 0),         # -1 clamped
        (0, 0, 0),         # 0
        (68, 60, 59),      # 1 (lookup byte 64)
        (141, 126, 123),   # 2 (lookup byte 128)
        (210, 189, 185),   # 3 (lookup byte 192)
        (255, 249, 244),   # 4 (lookup byte 255)
        (255, 249, 244),   # 5 → 4
        (255, 249, 244),   # 10 → 4
    ],
}


def _parse_probe(text: str) -> dict[str, list[tuple[int, int, int]]]:
    """Parse ``csname index -> r g b`` lines into name -> [(r,g,b), ...]."""
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
    # Use mkstemp (no open Python file handle) + explicit unlink so Windows
    # CI doesn't trip on the "file opened exclusively" reopen issue when the
    # Java probe re-opens the path. Same pattern as test_color_to_rgb_oracle.
    fd, tmp_name = tempfile.mkstemp(suffix=".icc")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(_icc_bytes)
        text = run_probe_text("IndexedCalProbe", tmp_name)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
    return _parse_probe(text)


# ---------- ICC sRGB tier (tolerance) ----------


@requires_oracle
@pytest.mark.parametrize("name", sorted(_TOLERANCE))
def test_indexed_cal_to_rgb_icc_tolerance(
    name: str,
    _icc_bytes: bytes,
    _java_rgb: dict[str, list[tuple[int, int, int]]],
) -> None:
    """Indexed-over-ICCBased(sRGB): each palette entry runs sRGB → sRGB
    through a CMM on both sides (Pillow/LittleCMS2 here, AWT in PDFBox) and
    the per-index clamp is identical integer logic. A divergence beyond the
    documented ``<= 2/255`` CMM LSB-rounding tolerance is a real bug — either
    in the ICC sRGB conversion (covered by the standalone ``IccSrgb`` test) or
    in the Indexed slicing/clamp routing through that base."""
    cs, indices = _battery(_icc_bytes)[name]
    java = _java_rgb[name]
    assert len(java) == len(indices), f"{name}: probe emitted {len(java)} rows"
    for index, j_rgb in zip(indices, java, strict=True):
        py_rgb = _rgb_int(cs, index)
        for chan, (p, j) in enumerate(zip(py_rgb, j_rgb, strict=True)):
            assert abs(p - j) <= _TOLERANCE_MAX_DELTA, (
                f"{name} index {index} channel {chan}: pypdfbox {p} vs "
                f"PDFBox {j} exceeds the {_TOLERANCE_MAX_DELTA}/255 CMM "
                f"tolerance"
            )


# ---------- documented-divergence tier (Cal* bases) ----------


@requires_oracle
@pytest.mark.parametrize("name", sorted(_DIVERGENT))
def test_indexed_cal_to_rgb_documented_divergence(
    name: str,
    _icc_bytes: bytes,
    _java_rgb: dict[str, list[tuple[int, int, int]]],
) -> None:
    """Indexed-over-Cal* (unit white point → calibrated CIE pipeline). The
    gamma decode and ``/Matrix`` application are deterministic float arithmetic
    identical on both sides; only the FINAL XYZ → sRGB step diverges
    (pypdfbox's explicit IEC 61966-2-1 D65 matrix vs PDFBox's AWT CMM with a
    D50 PCS). The Indexed wrapper itself is pure palette slicing + clamp —
    asserting against the pypdfbox pin guards the slicing/clamp + the base
    conversion together (a regression in either drops a row), and asserting at
    least one row differs from PDFBox keeps the documented CMM divergence
    honest if PDFBox's CMM output ever changes."""
    cs, indices = _battery(_icc_bytes)[name]
    java = _java_rgb[name]
    expected = _PYPDFBOX_DIVERGENT_EXPECTED[name]
    assert len(java) == len(indices)
    assert len(expected) == len(indices)
    any_diff = False
    for index, j_rgb, exp in zip(indices, java, expected, strict=True):
        py_rgb = _rgb_int(cs, index)
        assert py_rgb == exp, (
            f"{name} index {index}: pypdfbox {py_rgb} drifted from "
            f"pinned {exp}"
        )
        if py_rgb != j_rgb:
            any_diff = True
    assert any_diff, (
        f"{name}: pypdfbox now matches PDFBox on every index — the "
        f"documented XYZ → sRGB CMM divergence no longer holds; move "
        f"{name} to the ICC tolerance tier."
    )


# ---------- guard: out-of-range index clamping is independent of the base ----------


@requires_oracle
@pytest.mark.parametrize(
    "name",
    sorted(_TOLERANCE | _DIVERGENT),
)
def test_indexed_cal_clamp_matches_in_range_entry(
    name: str,
    _icc_bytes: bytes,
    _java_rgb: dict[str, list[tuple[int, int, int]]],
) -> None:
    """Clamping ``index < 0`` to ``0`` and ``index > hival`` to
    ``actualMaxIndex`` is the same integer logic in pypdfbox and PDFBox; the
    out-of-range rows in the probe output must therefore match the in-range
    rows at the clamped index, regardless of the base CS. A divergence here
    points to a real bug in ``PDIndexed.to_rgb``'s index handling."""
    cs, indices = _battery(_icc_bytes)[name]
    rows = _java_rgb[name]
    by_index = dict(zip(indices, rows, strict=True))
    hival = cs.get_hival()
    assert by_index[-1] == by_index[0], (
        f"{name}: PDFBox row for index -1 != row for index 0"
    )
    for i in indices:
        if i > hival:
            assert by_index[i] == by_index[hival], (
                f"{name}: PDFBox row for index {i} (> hival {hival}) != "
                f"row for clamped index {hival}"
            )
    # pypdfbox: same invariant must hold.
    py_zero = _rgb_int(cs, 0)
    py_neg1 = _rgb_int(cs, -1)
    assert py_neg1 == py_zero, (
        f"{name}: pypdfbox row for index -1 {py_neg1} != row for index 0 "
        f"{py_zero}"
    )
    py_hival = _rgb_int(cs, hival)
    for i in indices:
        if i > hival:
            assert _rgb_int(cs, i) == py_hival, (
                f"{name}: pypdfbox row for index {i} (> hival {hival}) "
                f"!= row for clamped index {hival}"
            )
