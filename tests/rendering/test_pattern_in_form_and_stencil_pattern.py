"""Synthetic coverage for two forward-ported PDFBox 3.0.9 rendering fixes.

* PDFBOX-5250: a pattern painted inside a form XObject (plain form or
  transparency group) is positioned relative to the form's own space, i.e.
  the stream's initial matrix includes the form ``/Matrix``.
* PDFBOX-6077: a stencil image mask filled with a pattern paints the pattern
  through the mask. Pixels the pattern never painted into (gaps between
  tiling cells) stay transparent instead of turning opaque black, and an
  ExtGState soft mask still applies.

The upstream regression PDFs are JIRA downloads (see
``tests/rendering/upstream/test_quality.py``); these tests build minimal
PDFs in-memory and assert on rendered pixel values instead.
"""

from __future__ import annotations

import io

from pypdfbox.pdmodel import PDDocument
from pypdfbox.rendering import PDFRenderer

PAGE_SIZE = 200


def _build_pdf(objects: list[bytes]) -> bytes:
    """Assemble a PDF whose object ``n`` (1-based) is ``objects[n - 1]``.
    Object 1 must be the catalog."""
    out = io.BytesIO()
    out.write(b"%PDF-1.7\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number)
        out.write(body)
        out.write(b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n" % (len(objects) + 1))
    out.write(b"0000000000 65535 f \n")
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, xref)
    )
    return out.getvalue()


def _stream(dictionary: bytes, data: bytes) -> bytes:
    return b"<< %s /Length %d >>\nstream\n%s\nendstream" % (
        dictionary,
        len(data),
        data,
    )


def _render(pdf: bytes):
    with PDDocument.load(pdf) as doc:
        return PDFRenderer(doc).render_image_with_dpi(0, 72).convert("RGB")


def _px(image, user_x: float, user_y: float) -> tuple[int, int, int]:
    """Pixel at user-space ``(x, y)`` (72 dpi, y-up)."""
    return image.getpixel((int(user_x), int(PAGE_SIZE - 1 - user_y)))


def _is_red(rgb: tuple[int, int, int]) -> bool:
    return rgb[0] > 200 and rgb[1] < 60 and rgb[2] < 60


def _is_green(rgb: tuple[int, int, int]) -> bool:
    return rgb[1] > 100 and rgb[0] < 60 and rgb[2] < 60


WHITE = (255, 255, 255)

# Colored tiling pattern, cell 100x100: left half red, right half green.
_SPLIT_TILE = _stream(
    b"/Type /Pattern /PatternType 1 /PaintType 1 /TilingType 1 "
    b"/BBox [0 0 100 100] /XStep 100 /YStep 100 /Resources << >>",
    b"1 0 0 rg 0 0 50 100 re f 0 1 0 rg 50 0 50 100 re f",
)


# ---------------------------------------------------------------------------
# PDFBOX-5250: patterns inside forms / transparency groups
# ---------------------------------------------------------------------------


def _pattern_in_form_pdf(pattern: bytes, *, group: bool, extra: bytes = b"") -> bytes:
    group_entry = b"/Group << /S /Transparency >> " if group else b""
    form = _stream(
        b"/Type /XObject /Subtype /Form /BBox [0 0 200 200] "
        b"/Matrix [1 0 0 1 50 0] " + group_entry
        + b"/Resources << /Pattern << /P0 5 0 R >> " + extra + b">>",
        b"/Pattern cs /P0 scn 0 0 50 50 re f",
    )
    page_content = _stream(b"", b"/Fm0 Do")
    return _build_pdf(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
            b"/Resources << /XObject << /Fm0 4 0 R >> >> /Contents 6 0 R >>",
            form,
            pattern,
            page_content,
        ]
    )


def test_tiling_pattern_in_plain_form_uses_form_matrix() -> None:
    # The form translates by (50, 0): the pattern cell origin lands at page
    # x=50, so the filled rect (page x 50..100) shows the red half.
    image = _render(_pattern_in_form_pdf(_SPLIT_TILE, group=False))
    assert _is_red(_px(image, 60, 25))
    assert _is_red(_px(image, 95, 25))
    # Outside the filled rect stays white.
    assert _px(image, 25, 25) == WHITE
    assert _px(image, 150, 25) == WHITE


def test_tiling_pattern_in_transparency_group_uses_group_matrix() -> None:
    # PDFBOX-5250: the transparency group's /Matrix is part of the initial
    # matrix too, exactly like a plain form (before the fix the pattern was
    # anchored at page x=0 and the filled rect showed the green half).
    image = _render(_pattern_in_form_pdf(_SPLIT_TILE, group=True))
    assert _is_red(_px(image, 60, 25))
    assert _is_red(_px(image, 95, 25))
    assert not _is_green(_px(image, 95, 25))
    assert _px(image, 25, 25) == WHITE


def test_shading_pattern_in_transparency_group_uses_group_matrix() -> None:
    # Axial shading red (x=0) -> green (x=100) in pattern space. Inside the
    # group translated by 50, page x=52 is pattern x=2: almost pure red.
    shading_pattern = (
        b"<< /Type /Pattern /PatternType 2 /Shading << /ShadingType 2 "
        b"/ColorSpace /DeviceRGB /Coords [0 0 100 0] /Extend [true true] "
        b"/Function << /FunctionType 2 /Domain [0 1] /C0 [1 0 0] "
        b"/C1 [0 1 0] /N 1 >> >> >>"
    )
    image = _render(_pattern_in_form_pdf(shading_pattern, group=True))
    r, g, _b = _px(image, 52, 25)
    assert r > 220 and g < 40
    # Page x=98 is pattern x=48: roughly halfway between red and green.
    r, g, _b = _px(image, 98, 25)
    assert 90 < r < 170 and 90 < g < 170


def test_pattern_in_annotation_appearance_uses_appearance_matrix() -> None:
    # The appearance stream's /BBox [0 0 50 50] is mapped onto the
    # annotation /Rect [50 0 100 50], so the appearance space starts at page
    # x=50 and the tiling pattern inside it shows its red half there.
    appearance = _stream(
        b"/Type /XObject /Subtype /Form /BBox [0 0 50 50] "
        b"/Resources << /Pattern << /P0 5 0 R >> >>",
        b"/Pattern cs /P0 scn 0 0 50 50 re f",
    )
    pdf = _build_pdf(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
            b"/Annots [6 0 R] /Contents 7 0 R >>",
            appearance,
            _SPLIT_TILE,
            b"<< /Type /Annot /Subtype /Square /Rect [50 0 100 50] /F 4 "
            b"/AP << /N 4 0 R >> >>",
            _stream(b"", b""),
        ]
    )
    image = _render(pdf)
    assert _is_red(_px(image, 60, 25))
    assert _is_red(_px(image, 95, 25))


# ---------------------------------------------------------------------------
# PDFBOX-6077: stencil masks filled with patterns
# ---------------------------------------------------------------------------

# Tiling pattern with gaps: a 10x10 red cell on a 20x20 lattice.
_GAPPED_TILE = _stream(
    b"/Type /Pattern /PatternType 1 /PaintType 1 /TilingType 1 "
    b"/BBox [0 0 10 10] /XStep 20 /YStep 20 /Resources << >>",
    b"1 0 0 rg 0 0 10 10 re f",
)

# 16x1 stencil: left 8 samples 0 (painted with the default /Decode [0 1]),
# right 8 samples 1 (masked out).
_STENCIL = _stream(
    b"/Type /XObject /Subtype /Image /Width 16 /Height 1 /ImageMask true "
    b"/BitsPerComponent 1",
    b"\x00\xff",
)

# 2x1 stencil (upstream's "small mask" size): left sample 0, right sample 1.
_SMALL_STENCIL = _stream(
    b"/Type /XObject /Subtype /Image /Width 2 /Height 1 /ImageMask true "
    b"/BitsPerComponent 1",
    b"\x40",
)


def _stencil_pdf(
    pattern: bytes,
    *,
    ext_gstate: bytes | None = None,
    smask_group: bytes | None = None,
    stencil: bytes = _STENCIL,
) -> bytes:
    gs_res = b"/ExtGState << /GS0 8 0 R >> " if ext_gstate is not None else b""
    gs_op = b"/GS0 gs " if ext_gstate is not None else b""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Resources << /XObject << /Im0 4 0 R >> /Pattern << /P0 5 0 R >> "
        + gs_res
        + b">> /Contents 6 0 R >>",
        stencil,
        pattern,
        _stream(
            b"",
            b"q /Pattern cs /P0 scn 100 0 0 100 0 0 cm " + gs_op + b"/Im0 Do Q",
        ),
        _stream(b"", b""),  # placeholder keeps numbering stable
    ]
    if ext_gstate is not None:
        objects.append(ext_gstate)
        assert smask_group is not None
        objects.append(smask_group)
    return _build_pdf(objects)


def test_stencil_mask_with_tiling_pattern_keeps_gaps_transparent() -> None:
    image = _render(_stencil_pdf(_GAPPED_TILE))
    # Masked-in pixel inside a pattern cell takes the pattern color.
    assert _is_red(_px(image, 5, 5))
    assert _is_red(_px(image, 25, 25))
    # Masked-in pixel in a gap between cells shows the white background,
    # not opaque black (PDFBOX-6077).
    assert _px(image, 15, 5) == WHITE
    assert _px(image, 5, 15) == WHITE
    # Masked-out half stays background even where a pattern cell sits.
    assert _px(image, 65, 5) == WHITE
    assert _px(image, 85, 25) == WHITE
    # Outside the image unit square nothing is painted.
    assert _px(image, 5, 150) == WHITE


def test_stencil_mask_with_shading_pattern_paints_shading() -> None:
    shading_pattern = (
        b"<< /Type /Pattern /PatternType 2 /Shading << /ShadingType 2 "
        b"/ColorSpace /DeviceRGB /Coords [0 0 100 0] /Extend [true true] "
        b"/Function << /FunctionType 2 /Domain [0 1] /C0 [0 0 1] "
        b"/C1 [0 1 0] /N 1 >> >> >>"
    )
    image = _render(_stencil_pdf(shading_pattern))
    r, g, b = _px(image, 2, 50)
    assert b > 220 and g < 40 and r < 40
    r, g, b = _px(image, 48, 50)
    assert 80 < b < 170 and 80 < g < 170
    # Masked-out half stays background.
    assert _px(image, 75, 50) == WHITE


def test_stencil_mask_with_tiling_pattern_honors_soft_mask() -> None:
    # Luminosity soft mask: white (alpha 1) over page x 0..30, black backdrop
    # (alpha 0) elsewhere. The ``gs`` runs after the image ``cm`` so the mask
    # group is drawn in the scaled unit-square space (1 unit = 100 pt).
    ext_gstate = b"<< /Type /ExtGState /SMask << /S /Luminosity /G 9 0 R >> >>"
    smask_group = _stream(
        b"/Type /XObject /Subtype /Form /BBox [0 0 2 2] "
        b"/Group << /S /Transparency /CS /DeviceGray >>",
        b"1 g 0 0 0.3 2 re f",
    )
    image = _render(
        _stencil_pdf(_GAPPED_TILE, ext_gstate=ext_gstate, smask_group=smask_group)
    )
    # Inside the soft mask: the soft-masked pattern stays visible.
    assert _is_red(_px(image, 5, 5))
    assert _is_red(_px(image, 25, 25))
    # Pattern cell inside the stencil but outside the soft mask: hidden.
    assert _px(image, 45, 5) == WHITE
    # Gaps stay background.
    assert _px(image, 15, 5) == WHITE


def test_small_stencil_mask_with_pattern_uses_upstream_small_mask_polarity() -> None:
    # Upstream's pattern-stencil branch draws masks of at most 8x8 samples
    # (other than 1x1, PDFBOX-5802) without inverting them, so the decoded
    # sample value 1 is what gets painted (checked against PDFBox 3.0.8).
    image = _render(_stencil_pdf(_GAPPED_TILE, stencil=_SMALL_STENCIL))
    assert _px(image, 5, 5) == WHITE
    assert _is_red(_px(image, 65, 5))
    assert _px(image, 75, 5) == WHITE  # gap between cells


def test_stencil_mask_with_solid_color_still_paints_fill_color() -> None:
    pdf = _build_pdf(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
            b"/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>",
            _STENCIL,
            _stream(b"", b"q 0 0 1 rg 100 0 0 100 0 0 cm /Im0 Do Q"),
        ]
    )
    image = _render(pdf)
    assert _px(image, 15, 5) == (0, 0, 255)
    assert _px(image, 75, 5) == WHITE


def test_dilate_alpha_widens_to_four_neighbors() -> None:
    import numpy as np

    alpha = np.zeros((5, 5), dtype=np.uint8)
    alpha[2, 2] = 200
    widened = PDFRenderer._dilate_alpha(alpha)
    expected = np.zeros((5, 5), dtype=np.uint8)
    expected[2, 2] = expected[1, 2] = expected[3, 2] = 200
    expected[2, 1] = expected[2, 3] = 200
    assert (widened == expected).all()
    # The input is not modified in place.
    assert alpha.sum() == 200
    # A one-pixel seam inside an opaque area is closed.
    seam = np.full((3, 5), 255, dtype=np.uint8)
    seam[:, 2] = 0
    assert (PDFRenderer._dilate_alpha(seam) == 255).all()
