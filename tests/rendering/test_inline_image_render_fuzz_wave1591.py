"""Wave 1591 — inline-image (BI/ID/EI) RENDER + PDInlineImage raster decode
fuzz.

A ``BI``/``ID``/``EI`` inline image is built into a :class:`PDInlineImage`
from the BI parameter dict + the ID bytes and drawn through the *same*
unit-square -> device CTM paste pipeline as an image XObject (upstream
``PDFGraphicsStreamEngine`` routes ``showInlineImage`` through the same
``drawImage`` path). This module hammers the inline-specific surface:

* abbreviated colour-space keys ``/G`` ``/RGB`` ``/CMYK`` resolved to the
  device singletons via ``PDInlineImage.to_long_name`` / ``create_color_space``;
* the ``/I`` (and ``/Indexed``) inline array head rebuilt into a real
  ``[/Indexed base hival lookup]`` colour space;
* a *named* colour-space abbreviation resolved against the page
  ``/Resources /ColorSpace`` (the inline ``/CS /Cs1`` form);
* the abbreviated geometry/sample keys ``/W`` ``/H`` ``/BPC`` and the
  ``/D`` (``/Decode``) abbreviation, plus their long-form fallbacks;
* a 1-bit inline raster decoded to the right size;
* the ``/IM`` (``/ImageMask``) inline *stencil* painted in the active
  non-stroking (fill) colour — NOT from the image samples — with the
  ``/D [0 1]`` (default) and ``/D [1 0]`` (inverting) decode senses;
* the inline render going through the same ``_paste_image`` unit-square map
  as an XObject (y-flipped device bbox, no double flip).

The stencil-decode cases also pin the wave-1591 bug fix: a ``PDInlineImage``
returns its ``/Decode`` as a raw ``COSArray`` (whose ``COSNumber`` items have
no Python ordering), so the pre-fix ``decode[0] > decode[1]`` in
``_paint_stencil_mask`` raised ``TypeError`` and (caught at the call site)
silently dropped every inline stencil with an inverting ``/D [1 0]``.
"""

from __future__ import annotations

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.color import (
    PDDeviceCMYK,
    PDDeviceGray,
    PDDeviceRGB,
)
from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _decode_first_pair


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _make_params(**entries) -> COSDictionary:
    """Build an inline-image parameter dict. Values that are plain ints map
    to COSInteger, bools to COSBoolean, str to COSName, COSBase pass through."""
    d = COSDictionary()
    for key, value in entries.items():
        cos_key = _n(key)
        if isinstance(value, bool):
            d.set_item(cos_key, COSBoolean.get(value))
        elif isinstance(value, int):
            d.set_item(cos_key, COSInteger.get(value))
        elif isinstance(value, float):
            d.set_item(cos_key, COSFloat(value))
        elif isinstance(value, str):
            d.set_item(cos_key, _n(value))
        else:
            d.set_item(cos_key, value)
    return d


def _decode_array(values) -> COSArray:
    arr = COSArray()
    for v in values:
        arr.add(COSInteger.get(v) if isinstance(v, int) else COSFloat(float(v)))
    return arr


# ============================================================ geometry: W/H


@pytest.mark.parametrize(
    ("params", "expected_w", "expected_h"),
    [
        ({"W": 4, "H": 3}, 4, 3),
        ({"Width": 4, "Height": 3}, 4, 3),
        # Short form preferred when both present.
        ({"W": 7, "Width": 99, "H": 2, "Height": 88}, 7, 2),
        ({"W": 1, "H": 1}, 1, 1),
    ],
    ids=["abbrev", "longform", "short_wins", "single_pixel"],
)
def test_width_height_abbreviation(params, expected_w, expected_h) -> None:
    img = PDInlineImage(_make_params(**params), b"\x00\x00\x00\x00", None)
    assert img.get_width() == expected_w
    assert img.get_height() == expected_h


def test_missing_width_height_is_negative_one() -> None:
    img = PDInlineImage(_make_params(), b"", None)
    assert img.get_width() == -1
    assert img.get_height() == -1


# ============================================================ BPC abbreviation


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"BPC": 8}, 8),
        ({"BitsPerComponent": 8}, 8),
        ({"BPC": 1}, 1),
        ({"BPC": 4, "BitsPerComponent": 16}, 4),
    ],
    ids=["abbrev8", "long8", "one", "short_wins"],
)
def test_bpc_abbreviation(params, expected) -> None:
    img = PDInlineImage(_make_params(**params), b"\x00", None)
    assert img.get_bits_per_component() == expected


def test_stencil_forces_bpc_one() -> None:
    # /IM true -> bits-per-component is always 1 regardless of /BPC.
    img = PDInlineImage(_make_params(W=2, H=2, IM=True, BPC=8), b"\x00", None)
    assert img.is_stencil() is True
    assert img.get_bits_per_component() == 1


# =================================================== abbreviated colour space


@pytest.mark.parametrize(
    ("cs_abbrev", "expected_cls"),
    [
        ("G", PDDeviceGray),
        ("RGB", PDDeviceRGB),
        ("CMYK", PDDeviceCMYK),
        ("DeviceGray", PDDeviceGray),
        ("DeviceRGB", PDDeviceRGB),
        ("DeviceCMYK", PDDeviceCMYK),
    ],
    ids=["G", "RGB", "CMYK", "long_gray", "long_rgb", "long_cmyk"],
)
def test_abbreviated_colorspace_resolves_to_device(cs_abbrev, expected_cls) -> None:
    img = PDInlineImage(
        _make_params(W=1, H=1, BPC=8, CS=cs_abbrev), b"\x00\x00\x00\x00", None
    )
    cs = img.get_color_space()
    assert isinstance(cs, expected_cls)


@pytest.mark.parametrize(
    ("abbrev", "long"),
    [("G", "DeviceGray"), ("RGB", "DeviceRGB"), ("CMYK", "DeviceCMYK")],
)
def test_to_long_name_expands_abbreviation(abbrev, long) -> None:
    img = PDInlineImage(_make_params(), b"", None)
    assert img.to_long_name(_n(abbrev)) == _n(long)


def test_to_long_name_passes_through_unknown() -> None:
    img = PDInlineImage(_make_params(), b"", None)
    # A non-abbreviated name (named resource CS) is returned verbatim.
    assert img.to_long_name(_n("Cs1")) == _n("Cs1")


def test_colorspace_via_long_form_fallback() -> None:
    # /ColorSpace long key honoured when /CS absent.
    img = PDInlineImage(
        _make_params(W=1, H=1, BPC=8, ColorSpace="DeviceRGB"),
        b"\x00\x00\x00",
        None,
    )
    assert isinstance(img.get_color_space(), PDDeviceRGB)


# =============================== named colour space resolved against resources


def _resources_with_named_cs(name: str, base: str) -> PDResources:
    """Build a PDResources whose /ColorSpace maps ``name`` to an ICCBased-ish
    array; here we map it straight to a device base so resolution succeeds
    without a stream profile."""
    resources = PDResources()
    cs_dict = COSDictionary()
    # Map the named entry directly to a device space name so PDColorSpace
    # resolves it (a real file would point at an [/ICCBased <stream>]).
    cs_dict.set_item(_n(name), _n(base))
    resources.get_cos_object().set_item(_n("ColorSpace"), cs_dict)
    return resources


def test_named_colorspace_resolved_against_resources() -> None:
    resources = _resources_with_named_cs("Cs1", "DeviceRGB")
    img = PDInlineImage(
        _make_params(W=1, H=1, BPC=8, CS="Cs1"), b"\x00\x00\x00", resources
    )
    cs = img.get_color_space()
    assert isinstance(cs, PDDeviceRGB)


def test_named_colorspace_gray_resolved_against_resources() -> None:
    resources = _resources_with_named_cs("MyGray", "DeviceGray")
    img = PDInlineImage(
        _make_params(W=1, H=1, BPC=8, CS="MyGray"), b"\x00", resources
    )
    assert isinstance(img.get_color_space(), PDDeviceGray)


def test_unknown_named_colorspace_without_resources_raises() -> None:
    img = PDInlineImage(_make_params(W=1, H=1, BPC=8, CS="Nope"), b"\x00", None)
    with pytest.raises(OSError):
        img.get_color_space()


# =================================== /I (Indexed) abbreviated array colour space


def _indexed_inline_cs(head: str) -> COSArray:
    """Build an inline indexed colour-space array ``[head base hival lookup]``
    using the abbreviated ``head`` (``/I``) and abbreviated base (``/RGB``)."""
    arr = COSArray()
    arr.add(_n(head))
    arr.add(_n("RGB"))  # abbreviated base -> must expand to DeviceRGB
    arr.add(COSInteger.get(1))  # hival
    # 2-entry palette: black, white (RGB triplets).
    arr.add(COSString(bytes([0, 0, 0, 255, 255, 255])))
    return arr


@pytest.mark.parametrize("head", ["I", "Indexed"])
def test_indexed_abbreviation_resolves(head) -> None:
    arr = _indexed_inline_cs(head)
    img = PDInlineImage(
        _make_params(W=2, H=1, BPC=8, CS=arr), b"\x00\x01", None
    )
    cs = img.get_color_space()
    # The resolved CS must expose an Indexed-style component count of 1.
    assert cs.get_number_of_components() == 1


def test_indexed_inline_palette_decodes_to_pil() -> None:
    arr = _indexed_inline_cs("I")
    # 2x1 image: index 0 (black), index 1 (white).
    img = PDInlineImage(_make_params(W=2, H=1, BPC=8, CS=arr), b"\x00\x01", None)
    pil = img.to_pil_image()
    assert pil is not None
    assert pil.size == (2, 1)
    rgb = pil.convert("RGB")
    assert rgb.getpixel((0, 0)) == (0, 0, 0)
    assert rgb.getpixel((1, 0)) == (255, 255, 255)


# ============================================================ /D abbreviation


def test_decode_abbreviation_short_form() -> None:
    img = PDInlineImage(
        _make_params(W=1, H=1, BPC=8, CS="G", D=_decode_array([1, 0])),
        b"\x00",
        None,
    )
    decode = img.get_decode()
    assert decode is not None
    assert _decode_first_pair(decode) == (1.0, 0.0)


def test_decode_abbreviation_long_form_fallback() -> None:
    img = PDInlineImage(
        _make_params(W=1, H=1, BPC=8, CS="G", Decode=_decode_array([1, 0])),
        b"\x00",
        None,
    )
    assert _decode_first_pair(img.get_decode()) == (1.0, 0.0)


def test_decode_as_floats_helper() -> None:
    img = PDInlineImage(
        _make_params(W=1, H=1, D=_decode_array([0, 1, 0, 1])), b"\x00", None
    )
    assert img.get_decode_as_floats() == [0.0, 1.0, 0.0, 1.0]


def test_decode_absent_is_none() -> None:
    img = PDInlineImage(_make_params(W=1, H=1), b"\x00", None)
    assert img.get_decode() is None
    assert img.get_decode_as_floats() is None


# ====================================== _decode_first_pair (wave-1591 fix unit)


@pytest.mark.parametrize(
    ("decode", "expected"),
    [
        (_decode_array([1, 0]), (1.0, 0.0)),
        (_decode_array([0, 1]), (0.0, 1.0)),
        ([1.0, 0.0], (1.0, 0.0)),  # XObject list[float] shape
        ([0.0, 1.0], (0.0, 1.0)),
        (None, None),
        (_decode_array([1]), None),  # too short
    ],
    ids=["cos_1_0", "cos_0_1", "list_1_0", "list_0_1", "none", "short"],
)
def test_decode_first_pair_handles_cosarray_and_list(decode, expected) -> None:
    # The crux of the wave-1591 fix: a COSArray of COSNumber must not raise
    # on ordering — it is normalised to floats, exactly like a list[float].
    assert _decode_first_pair(decode) == expected


# ====================================================== 1-bit inline raster


def test_one_bit_gray_inline_decodes_size() -> None:
    # 8x1 DeviceGray 1bpc -> one byte of samples.
    img = PDInlineImage(
        _make_params(W=8, H=1, BPC=1, CS="G"), bytes([0b10101010]), None
    )
    pil = img.to_pil_image()
    assert pil is not None
    assert pil.size == (8, 1)


def test_one_bit_inline_decode_inverted() -> None:
    # 1bpc with /D [1 0] inverts; both polarities must decode to a raster.
    img = PDInlineImage(
        _make_params(W=8, H=1, BPC=1, CS="G", D=_decode_array([1, 0])),
        bytes([0b11110000]),
        None,
    )
    pil = img.to_pil_image()
    assert pil is not None
    assert pil.size == (8, 1)


# ============================================================ render helpers


def _make_doc(width: float = 100.0, height: float = 100.0):
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _renderer_with_canvas(width_px: int = 100, height_px: int = 100):
    from pypdfbox.rendering import _aggdraw_compat as aggdraw
    from pypdfbox.rendering.pdf_renderer import _GState

    doc, _ = _make_doc(float(width_px), float(height_px))
    rdr = PDFRenderer(doc)
    rdr._image = Image.new("RGB", (width_px, height_px), (255, 255, 255))
    rdr._draw = aggdraw.Draw(rdr._image)
    rdr._gs_stack = [_GState()]
    rdr._device_ctm = (1.0, 0.0, 0.0, -1.0, 0.0, float(height_px))
    return doc, rdr


# =================================== inline image uses the same unit-square map


@pytest.mark.parametrize(
    ("w", "h", "x", "y"),
    [
        (40.0, 40.0, 10.0, 10.0),
        (60.0, 20.0, 0.0, 0.0),
        (30.0, 30.0, 60.0, 60.0),
    ],
    ids=["centered", "wide_origin", "topright"],
)
def test_inline_image_pastes_at_yflipped_box(w, h, x, y) -> None:
    """``show_inline_image`` blits through ``_paste_image`` — the same
    unit-square -> device map as a ``Do`` XObject — so a ``w 0 0 h x y cm``
    places the inline raster at the y-flipped device bbox."""
    page_h = 100
    doc, rdr = _renderer_with_canvas(page_h, page_h)
    captured: dict = {}

    def fake_paste(im, box=None, mask=None):  # noqa: ANN001
        captured["box"] = box
        captured["size"] = im.size

    rdr._image.paste = fake_paste  # type: ignore[method-assign]
    try:
        rdr._gs.ctm = (w, 0.0, 0.0, h, x, y)
        img = PDInlineImage(
            _make_params(W=2, H=2, BPC=8, CS="RGB"),
            bytes([0] * (2 * 2 * 3)),
            None,
        )
        rdr.show_inline_image(img)
        assert "box" in captured, "inline image was not pasted"
        assert captured["box"] == (round(x), round(page_h - (y + h)))
        assert captured["size"] == (round(w), round(h))
    finally:
        doc.close()


# ======================================= inline stencil painted in fill colour


def _inline_stencil_capture(fill_rgb, sample_bytes, decode=None, width=8, height=4):
    """Run ``show_inline_image`` on an /IM stencil with the blit replaced by
    a spy on ``_paste_image``; return the RGBA matte handed to the paste."""
    doc, rdr = _renderer_with_canvas(60, 60)
    captured: dict = {}

    def spy(pil_image, interpolate=True):  # noqa: ANN001
        captured["rgba"] = pil_image.copy()
        captured["interpolate"] = interpolate

    rdr._paste_image = spy  # type: ignore[method-assign]
    try:
        rdr._gs.fill_rgb = fill_rgb
        rdr._gs.ctm = (40.0, 0.0, 0.0, 40.0, 10.0, 10.0)
        entries = {"W": width, "H": height, "IM": True}
        if decode is not None:
            entries["D"] = _decode_array(decode)
        img = PDInlineImage(_make_params(**entries), sample_bytes, None)
        rdr.show_inline_image(img)
        return captured
    finally:
        doc.close()


def test_inline_stencil_uses_fill_color_not_samples() -> None:
    """An /IM inline stencil paints the active non-stroking colour wherever
    the 1-bit matte is opaque — the image samples only select the alpha."""
    fill = (12, 200, 64)
    # Row 0 all-opaque bits (0x00), rows 1-3 all-transparent (0xFF).
    cap = _inline_stencil_capture(fill, bytes([0x00, 0xFF, 0xFF, 0xFF]))
    rgba = cap["rgba"]
    assert rgba.mode == "RGBA"
    assert rgba.getpixel((0, 0)) == (12, 200, 64, 255)
    assert rgba.getpixel((0, 1)) == (12, 200, 64, 0)


@pytest.mark.parametrize("fill", [(255, 0, 0), (0, 0, 0), (50, 90, 255)])
def test_inline_stencil_tints_with_fill(fill) -> None:
    cap = _inline_stencil_capture(fill, bytes([0x00, 0xFF, 0xFF, 0xFF]))
    r, g, b, a = cap["rgba"].getpixel((0, 0))
    assert (r, g, b) == fill
    assert a == 255


def test_inline_stencil_default_decode_sample0_opaque() -> None:
    cap = _inline_stencil_capture((255, 0, 0), bytes([0x00, 0xFF, 0xFF, 0xFF]))
    rgba = cap["rgba"]
    assert rgba.getpixel((0, 0))[3] == 255  # sample 0 paints
    assert rgba.getpixel((0, 1))[3] == 0  # sample 1 transparent


def test_inline_stencil_decode_1_0_inverts() -> None:
    """``/D [1 0]`` inverts the stencil polarity. Pre wave-1591 this raised
    ``TypeError`` (COSArray ordering) at the ``decode[0] > decode[1]`` check
    and silently painted nothing; now sample 1 paints, sample 0 is clear."""
    cap = _inline_stencil_capture(
        (255, 0, 0), bytes([0x00, 0xFF, 0xFF, 0xFF]), decode=[1, 0]
    )
    rgba = cap["rgba"]
    assert "rgba" in cap, "inverted-decode inline stencil produced no paste"
    assert rgba.getpixel((0, 0))[3] == 0
    assert rgba.getpixel((0, 1))[3] == 255


@pytest.mark.parametrize(
    ("decode", "row0_alpha", "row1_alpha"),
    [
        (None, 255, 0),
        ([0, 1], 255, 0),
        ([1, 0], 0, 255),
    ],
    ids=["default", "explicit_0_1", "inverted_1_0"],
)
def test_inline_stencil_decode_matrix(decode, row0_alpha, row1_alpha) -> None:
    cap = _inline_stencil_capture(
        (10, 20, 30), bytes([0x00, 0xFF, 0xFF, 0xFF]), decode=decode
    )
    rgba = cap["rgba"]
    assert rgba.getpixel((0, 0))[3] == row0_alpha
    assert rgba.getpixel((0, 1))[3] == row1_alpha


def test_inline_stencil_long_form_imagemask_key() -> None:
    """The long-form ``/ImageMask true`` key is honoured exactly like ``/IM``."""
    doc, rdr = _renderer_with_canvas(60, 60)
    captured: dict = {}

    def spy(pil_image, interpolate=True):  # noqa: ANN001
        captured["rgba"] = pil_image.copy()

    rdr._paste_image = spy  # type: ignore[method-assign]
    try:
        rdr._gs.fill_rgb = (5, 5, 200)
        rdr._gs.ctm = (40.0, 0.0, 0.0, 40.0, 10.0, 10.0)
        img = PDInlineImage(
            _make_params(W=8, H=4, ImageMask=True),
            bytes([0x00, 0xFF, 0xFF, 0xFF]),
            None,
        )
        assert img.is_stencil() is True
        rdr.show_inline_image(img)
        assert "rgba" in captured
        assert captured["rgba"].getpixel((0, 0)) == (5, 5, 200, 255)
    finally:
        doc.close()


def test_inline_stencil_get_stencil_image_requires_stencil() -> None:
    # Non-stencil inline image -> get_stencil_image raises (upstream contract).
    img = PDInlineImage(_make_params(W=1, H=1, BPC=8, CS="G"), b"\x00", None)
    with pytest.raises(ValueError):
        img.get_stencil_image(paint=(0, 0, 0))
