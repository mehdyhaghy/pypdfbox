"""Live PDFBox differential parity for an inline image whose ``/CS`` *names* a
colour space defined in the page's ``/Resources /ColorSpace`` dict.

Per PDF 32000-1 §8.9.7 an inline image's colour space may be one of the
abbreviations (``/G`` / ``/RGB`` / ``/CMYK`` / ``/I``) *or* a name that
resolves against the surrounding page resources — e.g. ``/CS /CS0`` where
``/CS0`` is ``[/Indexed /DeviceRGB ...]`` or ``[/Separation ...]`` in
``/Resources /ColorSpace``. The decode-level inline-image suite
(``test_inline_image_oracle.py``) exercises the abbreviation path and a
self-contained ``[/I /RGB ...]`` array; this module exercises the distinct
*named-CS-from-resources* resolution path through the full
``PDFRenderer`` paint pipeline:

``_op_inline_image`` -> ``PDInlineImage(params, data, self._resources)`` ->
``show_inline_image`` -> ``to_pil_image`` ->
``PDInlineImage.get_color_space`` -> ``create_color_space`` ->
``PDColorSpace.create(name, resources)`` -> ``resources.get_color_space``.

If that resolution path is broken the inline image either fails to paint
(blank page), falls back to gray, or paints the wrong colour from a
mis-resolved palette / tint transform. We render each page via Java PDFBox
(``oracle/probes/RenderProbe.java``) and via pypdfbox at 72 DPI and compare
exact dims + a 16x16 average-luminance grid (MAD < 6 / MAXDIFF < 60). A guard
test confirms a blank page scores far from the painted reference, so the gate
discriminates a real named-CS paint from a silently-dropped image.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.rendering.pdf_renderer import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60


# --------------------------------------------------------------------------
# Fixture synthesis — a one-page 200x200 PDF whose page ``/Resources
# /ColorSpace`` carries the named colour space the inline image references.
# --------------------------------------------------------------------------
def _build_pdf(color_space_dict: bytes, content: bytes, extra_objs: list[bytes]) -> bytes:
    """Build a one-page PDF.

    ``color_space_dict`` is the body of the page ``/Resources /ColorSpace``
    dict (e.g. ``b"/CS0 [/Indexed /DeviceRGB 1 <000000FFFFFF>]"``).
    ``content`` is the page content stream verbatim. ``extra_objs`` are any
    already-serialised indirect objects (object numbers >= 5) the colour
    space references (e.g. a Separation tint-transform function).
    """

    def obj(num: int, data: bytes) -> bytes:
        return f"{num} 0 obj\n".encode() + data + b"\nendobj\n"

    stream_obj = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)
    resources = b"<< /ColorSpace << " + color_space_dict + b" >> >>"
    parts = [
        obj(1, b"<< /Type /Catalog /Pages 2 0 R >>"),
        obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        obj(
            3,
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
            b"/Contents 4 0 R /Resources " + resources + b" >>",
        ),
        obj(4, stream_obj),
    ]
    parts += extra_objs
    count = len(parts) + 1
    pdf = bytearray(b"%PDF-1.7\n")
    offsets: list[int] = []
    for part in parts:
        offsets.append(len(pdf))
        pdf += part
    xref_off = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % count
    for off in offsets:
        pdf += b"%010d 00000 n \n" % off
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        count,
        xref_off,
    )
    return bytes(pdf)


def _inline(params: bytes, data: bytes) -> bytes:
    return b"BI " + params + b" ID\n" + data + b"\nEI\n"


def _draw_inline(params: bytes, data: bytes) -> bytes:
    """Content stream: an inline image scaled to fill a 100x100 box centred
    on the 200x200 page."""
    return b"q 100 0 0 100 50 50 cm\n" + _inline(params, data) + b"Q\n"


# (a) Indexed named CS in resources: /CS0 = [/Indexed /DeviceRGB 1
#     <000000 FFFFFF>] — 2-entry palette index0=black, index1=white. The
#     inline image is 2x2 1-bpc; row0 = [0,1], row1 = [1,0]. Each 1-bit row
#     is byte-padded, so row0 = 0b01000000, row1 = 0b10000000.
def _indexed_named_cs() -> bytes:
    color_space = b"/CS0 [/Indexed /DeviceRGB 1 <000000FFFFFF>]"
    samples = bytes([0b01000000, 0b10000000])
    content = _draw_inline(b"/W 2 /H 2 /BPC 1 /CS /CS0", samples)
    return _build_pdf(color_space, content, [])


# (b) Separation named CS in resources: /CS0 = [/Separation /Spot
#     /DeviceRGB 5 0 R] with a type-2 exponential tint transform mapping
#     tint 0 -> white [1 1 1], tint 1 -> red [1 0 0]. Inline image is 2x2
#     8-bpc with tint samples [0, 255, 128, 255].
def _separation_named_cs() -> bytes:
    tint_fn = (
        b"5 0 obj\n"
        b"<< /FunctionType 2 /Domain [0 1] /C0 [1 1 1] /C1 [1 0 0] /N 1 >>"
        b"\nendobj\n"
    )
    color_space = b"/CS0 [/Separation /Spot /DeviceRGB 5 0 R]"
    samples = bytes([0, 255, 128, 255])
    content = _draw_inline(b"/W 2 /H 2 /BPC 8 /CS /CS0", samples)
    return _build_pdf(color_space, content, [tint_fn])


_CASES: list[tuple[str, bytes]] = [
    ("indexed_named_cs", _indexed_named_cs()),
    ("separation_named_cs", _separation_named_cs()),
]


def _grid_from_image(img) -> list[int]:
    """16x16 average-luminance fingerprint — matches RenderProbe.java's
    cell mapping (integer division of coordinate over cell size)."""
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    total = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            total[idx] += pixels[x, y]
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 255 for i in range(_GRID * _GRID)
    ]


def _oracle_signature(tmp_path, pdf_bytes: bytes) -> tuple[tuple[int, int], list[int]]:
    fixture = tmp_path / "inline_named_cs.pdf"
    fixture.write_bytes(pdf_bytes)
    try:
        lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
        width, height = (int(v) for v in lines[0].split())
        grid = [int(v) for v in lines[1].split()]
        assert len(grid) == _GRID * _GRID
        return (width, height), grid
    finally:
        fixture.unlink(missing_ok=True)


@requires_oracle
@pytest.mark.parametrize(
    ("label", "content"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_inline_image_named_cs_render_matches_pdfbox(
    tmp_path, label: str, content: bytes
) -> None:
    """Full-page render parity for an inline image whose ``/CS`` names a
    colour space in the page resources: pypdfbox resolves the named CS the
    same way Java PDFBox does — exact dims + 16x16 luminance grid within
    perceptual tolerance. This is the high-value named-CS-from-resources
    path (vs the inline-abbreviation path covered elsewhere)."""
    (java_w, java_h), java_grid = _oracle_signature(tmp_path, content)

    with PDDocument.load(content) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — named-CS inline image painted grossly "
        f"differently (CS not resolved from resources / wrong colour?)"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond AA / codec tolerance"
    )


@requires_oracle
def test_blank_render_would_fail_named_cs_tolerance(tmp_path) -> None:
    """Guard the gate: a blank-white page is far from the painted named-CS
    reference, so the gate discriminates a real named-CS paint from a
    silently-dropped (unresolved-CS / unpainted) inline image."""
    _dims, java_grid = _oracle_signature(tmp_path, _indexed_named_cs())
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(java_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: a blank render passes the named-CS MAD gate"
    )
