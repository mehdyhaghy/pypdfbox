"""Live Apache PDFBox differential parity for ``PDVisibleSignDesigner``.

Drives ``VisibleSignDesignerProbe`` (Java PDFBox 3.0.7) and the Python port
through the same geometry inputs (rotation, page + image dimensions, x/y),
runs ``adjustForRotation()`` on both, and asserts that the resulting
coordinates, swapped image dimensions, six affine-transform matrix entries,
and the four-integer formatter rectangle agree exactly.

The probe sets the private ``rotation``/``imageWidth``/``imageHeight``/
``pageWidth``/``pageHeight`` fields via reflection (the public constructors
require a real PDF + image); the Python parity port exposes the same state via
``_rotation`` and the public dimension setters.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sign_designer import (
    PDVisibleSignDesigner,
)
from tests.oracle.harness import requires_oracle, run_probe_text

# rotation, page_w, page_h, image_w, image_h, x, y
_CASES = [
    (0, 600.0, 800.0, 100.0, 40.0, 10.0, 20.0),
    (90, 600.0, 800.0, 100.0, 40.0, 10.0, 20.0),
    (180, 600.0, 800.0, 100.0, 40.0, 10.0, 20.0),
    (270, 600.0, 800.0, 100.0, 40.0, 10.0, 20.0),
    (90, 612.0, 792.0, 150.0, 75.0, 33.0, 47.0),
    (270, 595.0, 842.0, 220.0, 33.0, 5.0, 9.0),
    (180, 595.0, 842.0, 220.0, 33.0, 5.0, 9.0),
]


def _parse(line: str) -> dict[str, float | tuple[int, ...]]:
    out: dict[str, float | tuple[int, ...]] = {}
    for token in line.strip().split():
        key, _, val = token.partition("=")
        if key == "rect":
            out[key] = tuple(int(x) for x in val.split(","))
        else:
            out[key] = float(val)
    return out


def _python_geometry(case: tuple) -> dict[str, float | tuple[int, ...]]:
    rotation, page_w, page_h, image_w, image_h, x, y = case
    d = PDVisibleSignDesigner()
    d.page_width(page_w).page_height(page_h)
    d.width(image_w).height(image_h)
    d._rotation = rotation
    d.coordinates(x, y)
    d.adjust_for_rotation()
    t = d.get_transform()
    rect = tuple(d.get_formatter_rectangle_parameters())
    return {
        "x": float(d.get_x_axis()),
        "y": float(d.get_y_axis()),
        "w": float(d.get_width()),
        "h": float(d.get_height()),
        "m00": float(t.m00),
        "m10": float(t.m10),
        "m01": float(t.m01),
        "m11": float(t.m11),
        "m02": float(t.m02),
        "m12": float(t.m12),
        "rect": rect,
    }


@requires_oracle
@pytest.mark.parametrize(
    "case",
    _CASES,
    ids=[f"rot{c[0]}_{c[3]:.0f}x{c[4]:.0f}" for c in _CASES],
)
def test_adjust_for_rotation_matches_pdfbox(case: tuple) -> None:
    java = _parse(run_probe_text("VisibleSignDesignerProbe", *(str(v) for v in case)))
    py = _python_geometry(case)

    assert py["x"] == java["x"]
    assert py["y"] == java["y"]
    assert py["w"] == java["w"]
    assert py["h"] == java["h"]
    # Java builds the AffineTransform from 32-bit ``float`` operands, so the
    # matrix divisions (e.g. imageWidth/imageHeight) are single-precision. The
    # Python port computes in 64-bit; compare both narrowed to float32 so the
    # only permitted difference is IEEE-754 storage width, not the geometry.
    for k in ("m00", "m10", "m01", "m11", "m02", "m12"):
        py_f32 = struct.unpack("f", struct.pack("f", py[k]))[0]
        java_f32 = struct.unpack("f", struct.pack("f", java[k]))[0]
        assert py_f32 == java_f32, f"{k}: py={py[k]} java={java[k]}"
    assert py["rect"] == java["rect"]
