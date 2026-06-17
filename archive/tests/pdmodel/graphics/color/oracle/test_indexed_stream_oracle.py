"""Live PDFBox differential parity for ``PDIndexed.toRGB`` when the ``/Lookup``
palette is carried as a **COSStream** (not a literal ``COSString``), across a
DeviceRGB base (3 bytes/entry) and a DeviceCMYK base (4 bytes/entry), including
out-of-range indices.

The Java side is ``oracle/probes/IndexedStreamProbe.java``: it builds two
Indexed colour spaces whose ``/Lookup`` entry is a ``FlateDecode`` ``COSStream``
and, for a fixed set of indices (including negative and ``> hival``), emits
canonical ``csname index -> r g b`` lines where r/g/b are 0-255 ints obtained as
``round(component * 255)`` clamped to ``[0, 255]`` — the same rounding the helper
below applies. The Python side reconstructs the matching ``PDIndexed`` spaces
(same stream lookup, same base, same hival) and the same indices, then compares.

This exercises three high-value behaviours that a string-only lookup test does
not reach:

* **stream dereference** — the palette bytes come from decoding the stream's
  ``/Filter`` chain (``FlateDecode``), not from a literal string. A regression
  that treats the stream slot as empty/unsupported would zero the palette.
* **per-entry byte slicing by base component count** — DeviceRGB slices 3 bytes
  per entry, DeviceCMYK slices 4. Using the wrong component count shifts every
  entry.
* **index clamp to ``[0, hival]``** — negative indices clamp to 0, indices
  ``> hival`` clamp to the last entry.

Two parity tiers, matching ``test_color_space_to_rgb_oracle.py``:

**Exact-match tier — DeviceRGB base.** Palette dereference + base DeviceRGB
identity, no colour-management module involved. pypdfbox and PDFBox agree
byte-for-byte on every index (including the out-of-range clamps).

**Documented-divergence tier — DeviceCMYK base.** The per-entry CMYK→RGB
conversion routes through the JVM colour-management module (the bundled
``CGATS001Compat-v2-micro.icc`` profile) in PDFBox, while pypdfbox uses the
explicit subtractive ``(1-c)(1-k)`` math chosen in waves 1330C / 1386 (see
``pd_device_cmyk.py``). Deltas reach ~35/255 — not rounding epsilons — so we
pin pypdfbox's deterministic output and assert PDFBox differs, exactly as the
sibling colour-space oracle does. The **clamp indices** (which entry is
selected) must still agree even in this tier — the divergence is only in the
CMYK→RGB conversion of the selected entry, never in which entry is selected.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared rounding (must match IndexedStreamProbe.clamp255) ----------


def _clamp255(value: float) -> int:
    """round(value * 255), clamped to [0, 255] — mirrors the Java probe."""
    r = round(value * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _rgb_int(cs: PDIndexed, index: float) -> tuple[int, int, int]:
    rgb = cs.to_rgb([float(index)])
    assert rgb is not None, f"{cs!r}.to_rgb([{index}]) returned None"
    return (_clamp255(rgb[0]), _clamp255(rgb[1]), _clamp255(rgb[2]))


# ---------- COS builders mirroring the Java probe ----------


def _indexed_stream(base_name: str, hival: int, palette: bytes) -> PDIndexed:
    """Build a ``PDIndexed`` whose ``/Lookup`` is a FlateDecode ``COSStream``,
    matching ``IndexedStreamProbe.indexedStream``."""
    lookup = COSStream()
    with lookup.create_output_stream(["FlateDecode"]) as os:
        os.write(palette)
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(COSName.get_pdf_name(base_name))
    arr.add(COSInteger.get(hival))
    arr.add(lookup)
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDIndexed), f"expected PDIndexed, got {type(cs)!r}"
    return cs


# RGB base: 4 entries * 3 bytes, hival 3.
_RGB_PALETTE = bytes(
    [
        0, 0, 0,        # 0 black
        255, 0, 0,      # 1 red
        0, 255, 0,      # 2 green
        128, 128, 255,  # 3 light blue
    ]
)
_RGB_INDICES = [-1, 0, 1, 2, 3, 4, 7]

# CMYK base: 3 entries * 4 bytes, hival 2.
_CMYK_PALETTE = bytes(
    [
        0, 0, 0, 0,      # 0 white (no ink)
        0, 255, 255, 0,  # 1 red (m+y)
        0, 0, 0, 255,    # 2 black (k)
    ]
)
_CMYK_INDICES = [-1, 0, 1, 2, 3, 5]


def _parse_probe(text: str) -> dict[str, dict[int, tuple[int, int, int]]]:
    """Parse ``csname index -> r g b`` into name -> {index: (r, g, b)}."""
    out: dict[str, dict[int, tuple[int, int, int]]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        left, right = line.split("->")
        name, idx = left.split()
        r, g, b = (int(x) for x in right.split())
        out.setdefault(name, {})[int(idx)] = (r, g, b)
    return out


@pytest.fixture(scope="module")
def _java_rgb() -> dict[str, dict[int, tuple[int, int, int]]]:
    return _parse_probe(run_probe_text("IndexedStreamProbe"))


# ---------- exact-match tier: DeviceRGB base ----------


@requires_oracle
def test_indexed_stream_rgb_base_exact(
    _java_rgb: dict[str, dict[int, tuple[int, int, int]]],
) -> None:
    """Stream ``/Lookup`` + DeviceRGB base: pypdfbox RGB == PDFBox RGB,
    byte-for-byte, per index including the out-of-range clamps."""
    cs = _indexed_stream("DeviceRGB", 3, _RGB_PALETTE)
    java = _java_rgb["RGBStream"]
    assert sorted(java) == sorted(_RGB_INDICES), (
        f"probe emitted indices {sorted(java)}"
    )
    for index in _RGB_INDICES:
        py_rgb = _rgb_int(cs, index)
        assert py_rgb == java[index], (
            f"RGBStream index {index}: pypdfbox {py_rgb} != PDFBox {java[index]}"
        )


# ---------- documented-divergence tier: DeviceCMYK base ----------

# pypdfbox's pinned deterministic output (subtractive (1-c)(1-k)); PDFBox routes
# each entry's CMYK->RGB through the bundled CGATS001 ICC profile so it differs.
# The selected *entry* (the clamp) is identical in both; only the CMYK->RGB
# conversion of that entry diverges.
_PYPDFBOX_CMYK_EXPECTED: dict[int, tuple[int, int, int]] = {
    -1: (255, 255, 255),  # clamp to entry 0 (white, no ink)
    0: (255, 255, 255),   # entry 0
    1: (255, 0, 0),       # entry 1 (m+y -> red)
    2: (0, 0, 0),         # entry 2 (k -> black)
    3: (0, 0, 0),         # clamp to entry 2
    5: (0, 0, 0),         # clamp to entry 2
}


@requires_oracle
def test_indexed_stream_cmyk_base_documented_divergence(
    _java_rgb: dict[str, dict[int, tuple[int, int, int]]],
) -> None:
    """Stream ``/Lookup`` + DeviceCMYK base: pypdfbox produces its pinned
    deterministic RGB; PDFBox differs because it routes each entry's CMYK->RGB
    through the JVM colour-management module. We assert both: pypdfbox matches
    its pin (regression guard) AND at least one entry differs from PDFBox (keeps
    the divergence rationale honest). The clamp (which entry) must still agree
    on the colourless white entry where the CMM and subtractive math coincide.
    """
    cs = _indexed_stream("DeviceCMYK", 2, _CMYK_PALETTE)
    java = _java_rgb["CMYKStream"]
    assert sorted(java) == sorted(_CMYK_INDICES), (
        f"probe emitted indices {sorted(java)}"
    )
    any_diff = False
    for index in _CMYK_INDICES:
        py_rgb = _rgb_int(cs, index)
        exp = _PYPDFBOX_CMYK_EXPECTED[index]
        assert py_rgb == exp, (
            f"CMYKStream index {index}: pypdfbox {py_rgb} drifted from pinned {exp}"
        )
        if py_rgb != java[index]:
            any_diff = True
    assert any_diff, (
        "CMYKStream: pypdfbox now matches PDFBox on every index — the documented "
        "DeviceCMYK CMM divergence no longer holds; move to the exact-match tier."
    )


@requires_oracle
def test_indexed_stream_cmyk_clamp_entry_agrees(
    _java_rgb: dict[str, dict[int, tuple[int, int, int]]],
) -> None:
    """Even in the CMM-divergent CMYK tier, the *clamp* must agree: an
    out-of-range index resolves to the SAME palette entry as hival, and a
    negative index to entry 0. We verify this by checking that PDFBox's RGB for
    an out-of-range index equals its RGB for hival (same entry), and likewise
    negative == 0 — independent of the CMYK->RGB conversion that diverges."""
    java = _java_rgb["CMYKStream"]
    # > hival (2) clamps to entry 2
    assert java[3] == java[2], "PDFBox: index 3 should clamp to hival entry 2"
    assert java[5] == java[2], "PDFBox: index 5 should clamp to hival entry 2"
    # negative clamps to entry 0
    assert java[-1] == java[0], "PDFBox: index -1 should clamp to entry 0"
    # pypdfbox makes the same clamp choice
    cs = _indexed_stream("DeviceCMYK", 2, _CMYK_PALETTE)
    assert _rgb_int(cs, 3) == _rgb_int(cs, 2)
    assert _rgb_int(cs, 5) == _rgb_int(cs, 2)
    assert _rgb_int(cs, -1) == _rgb_int(cs, 0)
