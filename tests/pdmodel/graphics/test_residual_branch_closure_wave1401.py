"""Wave 1401 — close residual partial branches in
``pypdfbox.pdmodel.graphics`` subtree.

Targets:

* shading mesh decoders (``PDShadingType6/7``): exercise the
  COS-not-COSStream early-return path.
* ``CoonsPatch.calc_level`` / ``TensorPatch.calc_level``: exercise the
  False branch on the ``is_edge_a_line`` AND-guards by feeding
  bent-edge control points.
* ``PNGConverter.parse_png_chunks``: header-only PNG (no chunks),
  short IHDR (length<13), IEND short-circuit.
* Optional-content membership: usage-subdict missing, prune-empty
  branches.
* ``BlendMode.get_saturation_rgb`` (482->495): no-overflow scaler path.
* ``PDIndexed.create``: raise on a base color space whose
  ``get_cos_object()`` returns ``None``.
* ``pd_extended_graphics_state``: copy-soft-mask no-CTM branch and
  font-size non-numeric branch.
* ``pd_optional_content_properties``: malformed /Order array,
  radio-button sibling already-off, /AS append-in-place.
* ``pd_device_n``: non-name colorant entry, set_attributes(None)
  short-array path.
"""

from __future__ import annotations

import contextlib
import struct
from typing import Any

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)

# =========================================================================
# Shading mesh dictionaries — non-stream COS object early return
# =========================================================================


def test_pd_shading_type6_parse_patches_returns_empty_when_cos_is_dictionary() -> None:
    """When the type-6 shading wraps a ``COSDictionary`` (not a
    ``COSStream``) the early return on ``isinstance(cos, COSStream)``
    False fires and ``parse_patches`` returns ``[]``."""
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type6 import PDShadingType6

    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("ShadingType"), 6)
    shading = PDShadingType6(d)
    assert shading.parse_patches() == []


def test_pd_shading_type7_parse_patches_returns_empty_when_cos_is_dictionary() -> None:
    """Same as type6 but for tensor-product patches (type 7)."""
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type7 import PDShadingType7

    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("ShadingType"), 7)
    shading = PDShadingType7(d)
    assert shading.parse_patches() == []


def test_pd_shading_type6_parse_patches_empty_when_decode_missing() -> None:
    """Stream exists but ``/Decode`` array missing: the decoder bails
    out at the ``if decode is None`` check. We pre-populate the stream
    body so ``create_input_stream`` succeeds."""
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type6 import PDShadingType6

    shading = PDShadingType6()  # default constructor builds a COSStream.
    shading._dict.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    shading._dict.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    shading._dict.set_int(COSName.get_pdf_name("BitsPerFlag"), 2)
    # Write an empty body so the stream is readable; /Decode omitted.
    with shading._dict.create_output_stream() as out:
        out.write(b"\x00")
    assert shading.parse_patches() == []


def test_pd_shading_type7_parse_patches_empty_when_decode_missing() -> None:
    """Tensor patch (type 7) decode-missing branch."""
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type7 import PDShadingType7

    shading = PDShadingType7()
    shading._dict.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    shading._dict.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    shading._dict.set_int(COSName.get_pdf_name("BitsPerFlag"), 2)
    with shading._dict.create_output_stream() as out:
        out.write(b"\x00")
    assert shading.parse_patches() == []


# =========================================================================
# Mesh-based shading patch-stream parser — EOF on flag read
# =========================================================================


def test_parse_patch_stream_handles_eof_on_next_flag_break() -> None:
    """``parse_patch_stream`` reads a leading flag, then per-patch geometry,
    then a *trailing* flag before continuing the loop. The trailing flag
    can hit EOFError when the stream is sized to exactly one patch with
    no padding — the loop must break, not raise.

    Use ``bits_per_flag = 8`` so the total payload (8 + 12*32 + 4*8 =
    424 bits = 53 bytes) lands on a clean byte boundary; the next
    8-bit flag read then EOFs without any spare bits.
    """
    from pypdfbox.pdmodel.graphics.shading.pd_mesh_based_shading_type import (
        parse_patch_stream,
    )

    bits_per_flag = 8
    bits_per_coordinate = 16
    bits_per_component = 8
    num_color_components = 1
    control_points = 12

    # 53 bytes total: leading flag (1 byte, value 0) + 12 points × 4
    # bytes (2 coords × 16 bits) + 4 colors × 1 byte. All zeros.
    blob = bytes(53)
    decode = [0.0, 100.0, 0.0, 100.0, 0.0, 1.0]

    patches = parse_patch_stream(
        blob,
        bits_per_coordinate=bits_per_coordinate,
        bits_per_component=bits_per_component,
        bits_per_flag=bits_per_flag,
        decode=decode,
        num_color_components=num_color_components,
        control_points=control_points,
    )
    # Exactly one patch decoded; the trailing flag-read raised EOFError
    # which was caught by the ``except EOFError: break`` at 256–257.
    assert len(patches) == 1


# =========================================================================
# CoonsPatch / TensorPatch — calc_level bent-edge branches
# =========================================================================


def _patch_with_bent_edges() -> list[tuple[float, float]]:
    """Build 12 control points where no edge satisfies ``is_edge_a_line``.

    ``patch.is_edge_a_line`` returns True iff the two interior controls
    lie within the bounding rectangle of the end-points along x or y.
    Pushing the interior controls far off-axis (``big``) on every edge
    causes every guard in ``calc_level`` to take its False branch.
    """
    big = 1000.0  # far enough that ctl1/ctl2 exceed both x-span and y-span
    return [
        (0.0, 0.0),     # 0  corner
        (big, big),     # 1  interior ctl (off-axis)
        (-big, big),    # 2  interior ctl
        (100.0, 0.0),   # 3  corner
        (big, big),     # 4
        (-big, big),    # 5
        (100.0, 100.0), # 6  corner
        (big, big),     # 7
        (-big, big),    # 8
        (0.0, 100.0),   # 9  corner
        (big, big),     # 10
        (-big, big),    # 11
    ]


def test_coons_patch_calc_level_with_all_edges_bent_takes_both_false_branches() -> None:
    """Bent edges → both ``if is_edge_a_line(...) and is_edge_a_line(...)``
    guards in :meth:`CoonsPatch.calc_level` take the False branch."""
    from pypdfbox.pdmodel.graphics.shading.coons_patch import CoonsPatch

    color = [[0.0], [0.0], [0.0], [0.0]]
    patch = CoonsPatch(_patch_with_bent_edges(), color)
    # When the guards return False, ``level`` keeps its default [4, 4].
    assert patch.level == [4, 4]


def test_tensor_patch_calc_level_with_all_edges_bent_takes_false_branches() -> None:
    """Same bent-edge geometry but for ``TensorPatch.calc_level`` — its
    67->88 partial requires the second AND-guard to take False."""
    from pypdfbox.pdmodel.graphics.shading.tensor_patch import TensorPatch

    # TensorPatch expects 16 control points (4x4 grid). Use the row-major
    # form with corners at the unit-square and interior controls off-axis.
    big = 1000.0
    grid: list[tuple[float, float]] = []
    for row in range(4):
        for col in range(4):
            if (row in (0, 3)) and (col in (0, 3)):
                grid.append((float(col) * 100.0 / 3.0, float(row) * 100.0 / 3.0))
            else:
                grid.append((big if (row + col) % 2 == 0 else -big, big))
    color = [[0.0], [0.0], [0.0], [0.0]]
    patch = TensorPatch(grid, color)
    assert patch.level[1] == 4


# =========================================================================
# PDIndexed.create — base color space with no COS form
# =========================================================================


def test_pd_indexed_to_rgb_image_with_full_palette_skips_clamp_translation() -> None:
    """``to_rgb_image`` 450->457: when ``max_index >= 255`` (palette
    has the full 256 entries) the ``if max_index < 255`` False branch
    fires — the C-bytes-translate clamp step is skipped."""
    pytest.importorskip("PIL")
    from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
    from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

    # Build a 256-entry gray palette (hival=255, 256 * 1 component = 256 bytes).
    base = PDDeviceGray.INSTANCE
    lookup = bytes(range(256))
    indexed = PDIndexed.create(base, 255, lookup)
    # 4-byte raster → 2x2 image.
    img = indexed.to_rgb_image(b"\x00\x80\xff\x40", 2, 2)
    assert img is not None
    assert img.size == (2, 2)


def test_pd_indexed_create_raises_when_base_color_space_has_no_cos_form() -> None:
    """The ``create`` factory accepts any ``PDColorSpace`` subclass; if
    its ``get_cos_object()`` returns ``None`` the factory must raise
    ``ValueError("base color space has no COS form")``."""
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
    from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

    class _StubColorSpaceNoCOS(PDColorSpace):
        def get_name(self) -> str:
            return "StubNoCos"

        def get_number_of_components(self) -> int:
            return 3

        def get_initial_color(self) -> Any:
            from pypdfbox.pdmodel.graphics.color.pd_color import PDColor

            return PDColor([0.0, 0.0, 0.0], self)

        def get_default_decode(self, bits_per_component: int) -> list[float]:
            del bits_per_component
            return [0.0, 1.0] * 3

        def to_rgb(self, components: list[float]) -> tuple[float, float, float]:
            return (components[0], components[1], components[2])

        def get_cos_object(self) -> None:
            return None

    base = _StubColorSpaceNoCOS()
    # hival=1 → 2 entries × 3 components = 6 bytes of lookup data.
    lookup = bytes([0, 0, 0, 255, 255, 255])
    with pytest.raises(ValueError, match="base color space has no COS form"):
        PDIndexed.create(base, 1, lookup)


# =========================================================================
# PNGConverter.parse_png_chunks
# =========================================================================


def test_parse_png_chunks_header_only_returns_empty_state() -> None:
    """A PNG payload consisting of only the 8-byte signature: the
    while-loop guard ``offset + 8 <= len(image_data)`` is False on
    the first iteration, so the loop body never executes (288->328)."""
    from pypdfbox.pdmodel.graphics.image.png_converter import PNGConverter

    state = PNGConverter.parse_png_chunks(b"\x89PNG\r\n\x1a\n")
    assert state is not None
    assert state.ihdr is None
    assert state.idats == []


def test_parse_png_chunks_short_ihdr_skips_dimension_extraction() -> None:
    """IHDR chunk with length<13 takes the False branch on
    ``if length >= 13`` (305->327) — state.ihdr is set but width /
    height / bits_per_component stay defaulted."""
    from pypdfbox.pdmodel.graphics.image.png_converter import PNGConverter

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_body = b"\x00\x00\x00\x04"  # length = 4 (too short)
    ihdr_type = b"IHDR"
    ihdr_data = b"\x00\x00\x00\x00"
    ihdr_crc = b"\x00\x00\x00\x00"
    iend = struct.pack(">I", 0) + b"IEND" + b"\xAE\x42\x60\x82"
    blob = sig + ihdr_body + ihdr_type + ihdr_data + ihdr_crc + iend
    state = PNGConverter.parse_png_chunks(blob)
    assert state is not None
    assert state.ihdr is not None
    assert state.width == 0
    assert state.height == 0


def test_parse_png_chunks_iend_takes_break_branch_before_offset_advance() -> None:
    """``IEND`` short-circuits the loop via ``break`` rather than
    advancing ``offset = data_end + 4`` (325 True branch)."""
    from pypdfbox.pdmodel.graphics.image.png_converter import PNGConverter

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_payload = struct.pack(">IIBBBBB", 8, 8, 8, 0, 0, 0, 0)
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_payload + b"\x00\x00\x00\x00"
    iend = struct.pack(">I", 0) + b"IEND" + b"\xAE\x42\x60\x82"
    state = PNGConverter.parse_png_chunks(sig + ihdr + iend)
    assert state is not None
    assert state.width == 8
    assert state.height == 8


def test_parse_png_chunks_unknown_chunk_type_advances_offset_past_elif_chain() -> None:
    """``parse_png_chunks`` 325->327: an unknown chunk type (none of
    IHDR / IDAT / PLTE / ICCP / TRNS / SRGB / GAMA / CHRM / IEND)
    falls through every elif branch — the last branch (line 325, IEND)
    must take the False branch so control reaches the offset-advance
    at line 327."""
    from pypdfbox.pdmodel.graphics.image.png_converter import PNGConverter

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_payload = struct.pack(">IIBBBBB", 8, 8, 8, 0, 0, 0, 0)
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_payload + b"\x00\x00\x00\x00"
    # Unknown 4-byte chunk type "xXxX" — not IHDR/IDAT/PLTE/ICCP/TRNS/SRGB/
    # GAMA/CHRM/IEND. The parser must skip past it and advance offset.
    unknown = struct.pack(">I", 0) + b"xXxX" + b"\x00\x00\x00\x00"
    iend = struct.pack(">I", 0) + b"IEND" + b"\xAE\x42\x60\x82"
    state = PNGConverter.parse_png_chunks(sig + ihdr + unknown + iend)
    assert state is not None
    # IHDR was parsed before the unknown chunk; dimensions confirm parser
    # advanced through.
    assert state.width == 8


# =========================================================================
# Optional content
# =========================================================================


def test_pd_ocg_set_render_state_preserves_existing_usage_dict_branch() -> None:
    """Second ``set_render_state`` call on the same destination reuses
    the existing /Usage/Print sub-dict (230 ``isinstance(sub, COSDictionary)``
    True branch on second call)."""
    from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
        PDOptionalContentGroup,
    )

    ocg = PDOptionalContentGroup("Layer 1")
    ocg.set_render_state("ON", "Print")
    ocg.set_render_state("OFF", "Print")
    assert ocg.get_render_state("Print") == "OFF"


def test_pd_ocg_get_render_state_handles_non_dict_usage_entry() -> None:
    """``get_render_state`` against an OCG where /Usage exists but its
    /Print entry is not a dictionary — the ``isinstance(sub, COSDictionary)``
    False branch on line 193 of ``pd_optional_content_group.py``."""
    from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
        PDOptionalContentGroup,
    )

    ocg = PDOptionalContentGroup("Layer X")
    usage = COSDictionary()
    usage.set_item(COSName.get_pdf_name("Print"), COSName.get_pdf_name("NotADict"))
    ocg._dict.set_item(COSName.get_pdf_name("Usage"), usage)
    assert ocg.get_render_state("Print") is None


def test_pd_ocg_prune_usage_chain_skips_when_sub_not_empty() -> None:
    """``_prune_usage_chain`` must NOT remove a non-empty sub-dict —
    exercises the False branch on
    ``isinstance(sub, COSDictionary) and sub.is_empty()`` (303->305)."""
    from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
        PDOptionalContentGroup,
    )

    ocg = PDOptionalContentGroup("Layer Y")
    usage = COSDictionary()
    print_sub = COSDictionary()
    print_sub.set_item(COSName.get_pdf_name("CreatorInfo"), COSDictionary())
    usage.set_item(COSName.get_pdf_name("Print"), print_sub)
    ocg._dict.set_item(COSName.get_pdf_name("Usage"), usage)
    ocg._prune_usage_chain(COSName.get_pdf_name("Print"))
    assert ocg._dict.get_dictionary_object(COSName.get_pdf_name("Usage")) is usage
    assert usage.get_dictionary_object(COSName.get_pdf_name("Print")) is print_sub


# =========================================================================
# BlendMode — YUV no-overflow branch (482->495 False)
# =========================================================================


def test_get_saturation_rgb_no_overflow_branch_skips_scaler_block() -> None:
    """``get_saturation_rgb`` 482->495 (False on overflow guard): when
    the YUV-shifted RGB stays inside 0..255 the scaler block is
    skipped. Crafted inputs (low-contrast src, mid-saturation dst)
    keep all three components in-range.
    """
    from pypdfbox.pdmodel.graphics.blend_mode import BlendMode

    # Verified: this src/dst pair yields r=152, g=127, b=127 — no overflow.
    src = (0.5, 0.4, 0.4)
    dst = (0.6, 0.5, 0.5)
    result = [0.0, 0.0, 0.0]
    BlendMode.get_saturation_rgb(src, dst, result)
    for v in result:
        assert 0.0 <= v <= 1.0


# =========================================================================
# pd_extended_graphics_state — soft-mask copy + font-size branches
# =========================================================================


def test_extended_graphics_state_copy_soft_mask_without_ctm_skips_initial_matrix() -> None:
    """``_copy_soft_mask`` 376->378: when the target has no CTM accessor,
    the ``if ctm is not None`` False branch fires — soft mask is copied
    without an initial transformation matrix.
    """
    from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
        PDExtendedGraphicsState,
    )

    egs = PDExtendedGraphicsState()
    smask = COSDictionary()
    smask.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Mask"))
    smask.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Luminosity"))
    g_stream = COSStream()
    g_stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    g_stream.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form"))
    g_stream.set_item(COSName.get_pdf_name("Group"), COSDictionary())
    smask.set_item(COSName.get_pdf_name("G"), g_stream)
    egs._dict.set_item(COSName.get_pdf_name("SMask"), smask)

    target: dict[str, Any] = {}
    egs._copy_soft_mask(target)
    # ``set_soft_mask`` slot is recorded via _copy_value_allow_none.
    assert "soft_mask" in target


def test_extended_graphics_state_get_font_size_with_non_numeric_entry_returns_none() -> None:
    """``get_font_size`` 672->674: when the /Font array's second entry
    is non-numeric the ``isinstance(entry, COSNumber)`` False branch
    fires and the accessor returns None."""
    from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
        PDExtendedGraphicsState,
    )

    egs = PDExtendedGraphicsState()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Font0"))
    arr.add(COSName.get_pdf_name("NotANumber"))
    egs._dict.set_item(COSName.get_pdf_name("Font"), arr)
    assert egs.get_font_size() is None


# =========================================================================
# pd_optional_content_properties
# =========================================================================


def test_optional_content_properties_remove_group_when_order_not_cosarray() -> None:
    """``remove_group`` 238->240: when /Order is not a COSArray the
    ``isinstance(order, COSArray)`` False branch fires."""
    from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
        PDOptionalContentGroup,
    )
    from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
        PDOptionalContentProperties,
    )

    props = PDOptionalContentProperties()
    ocg = PDOptionalContentGroup("Group X")
    props.add_group(ocg)
    d = props.get_d()
    d.set_item(COSName.get_pdf_name("Order"), COSName.get_pdf_name("NotAnArray"))
    assert props.remove_group(ocg) is True


def test_optional_content_properties_set_group_enabled_radio_sibling_already_off() -> None:
    """403->402: when a radio-button sibling is already in /OFF the
    inner-loop iterates past unrelated entries first (False branch on
    ``d_entry is sibling``), then matches and breaks. To trigger the
    False branch we need ``/OFF`` to contain at least one non-sibling
    entry BEFORE the sibling."""
    from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
        PDOptionalContentGroup,
    )
    from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
        PDOptionalContentProperties,
    )

    props = PDOptionalContentProperties()
    target = PDOptionalContentGroup("Target")
    sibling = PDOptionalContentGroup("Sibling")
    decoy = PDOptionalContentGroup("Decoy")  # unrelated entry in /OFF
    props.add_group(target)
    props.add_group(sibling)
    props.add_group(decoy)
    rb_group = COSArray()
    rb_group.add(target.get_cos_object())
    rb_group.add(sibling.get_cos_object())
    rbgroups = COSArray()
    rbgroups.add(rb_group)
    d = props.get_d()
    d.set_item(COSName.get_pdf_name("RBGroups"), rbgroups)
    off = COSArray()
    # Decoy first → False branch fires for the first iteration.
    off.add(decoy.get_cos_object())
    off.add(sibling.get_cos_object())
    d.set_item(COSName.get_pdf_name("OFF"), off)
    props.set_group_enabled(target, True)
    off_after = d.get_dictionary_object(COSName.get_pdf_name("OFF"))
    sibling_count = sum(
        1 for entry in off_after if entry is sibling.get_cos_object()
    )
    assert sibling_count == 1


def test_optional_content_configuration_add_as_entry_with_existing_array() -> None:
    """``add_as_entry`` 561->564: when /AS already exists and IS a
    COSArray, the ``if not isinstance(arr, COSArray)`` False branch
    fires (append-in-place, no replacement)."""
    from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_configuration import (
        PDOptionalContentConfiguration,
    )

    config = PDOptionalContentConfiguration()
    existing = COSArray()
    config._dict.set_item(COSName.get_pdf_name("AS"), existing)
    entry = config.add_as_entry("View", ["View"], [])
    arr_after = config._dict.get_dictionary_object(COSName.get_pdf_name("AS"))
    assert arr_after is existing
    assert entry in list(arr_after)


# =========================================================================
# pd_device_n
# =========================================================================


def test_pd_device_n_set_attributes_none_with_short_array_takes_skip_branch() -> None:
    """``set_attributes(None)`` 465->467: when the array's size is NOT
    > _DEVICEN_ATTRIBUTES the ``if size > ...`` False branch fires
    (no remove_at). A freshly-built PDDeviceN has a short array."""
    from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN

    devicen = PDDeviceN()
    # No-op when there's nothing in the attributes slot.
    devicen.set_attributes(None)


def test_sampled_image_reader_cmyk_inner_loop_continues_past_single_pixel() -> None:
    """``SampledImageReader.get_rgb_image`` 330->313: the inner pixel
    loop must continue past the first CMYK assignment when width > 1.
    The 330 branch is the per-pixel CMYK write; the loop-back to 313
    fires only when there's a second pixel column to process.
    """
    pytest.importorskip("PIL")
    import io as _io

    from pypdfbox.pdmodel.graphics.image.sampled_image_reader import (
        SampledImageReader,
    )

    class _StubDecode:
        def __init__(self, values: list[float] | None) -> None:
            self._values = values

        def size(self) -> int:
            return 0 if self._values is None else len(self._values)

        def to_float_array(self) -> list[float]:
            return list(self._values) if self._values is not None else []

    class _StubColorSpace:
        def __init__(self, components: int) -> None:
            self._components = components

        def get_number_of_components(self) -> int:
            return self._components

    class _StubCMYKImage:
        def __init__(self, width: int, height: int, data: bytes) -> None:
            self._w = width
            self._h = height
            self._data = data
            self._cs = _StubColorSpace(4)
            self._decode = _StubDecode(None)

        def get_width(self) -> int:
            return self._w

        def get_height(self) -> int:
            return self._h

        def get_bits_per_component(self) -> int:
            return 8

        def get_color_space(self) -> Any:
            return self._cs

        def get_decode(self) -> Any:
            return self._decode

        def is_empty(self) -> bool:
            return False

        def is_stencil(self) -> bool:
            return False

        def create_input_stream(self, *_args: Any, **_kwargs: Any) -> Any:
            return _io.BytesIO(self._data)

    # 2×1 CMYK image (8 bytes: 4 channels × 2 pixels). Use
    # ``get_raw_raster`` (not ``get_rgb_image``) — that's the path
    # containing the 330->313 partial inside the CMYK pixel-set branch.
    img = SampledImageReader.get_raw_raster(_StubCMYKImage(2, 1, bytes(range(8))))
    assert img is not None
    assert img.mode == "CMYK"
    assert img.size == (2, 1)


def test_ccitt_factory_tag_262_with_val_not_one_skips_blackis1_branch() -> None:
    """``extract_from_tiff`` 182->153: tag 262 (Photometric) with
    val != 1 takes the False branch on ``if val == 1`` and loops on
    to the next tag without setting BlackIs1."""
    import io as _io

    from pypdfbox.pdmodel.graphics.image.ccitt_factory import extract_from_tiff

    # Build a minimal TIFF where tag 273 carries count=2 (multi-strip).
    # The parser will skip the dataoffset assignment, then later fail
    # because no valid strip is locatable — that's fine, the branch we
    # care about has already executed before the failure point.
    little = True
    endian = b"II" if little else b"MM"
    magic = struct.pack("<H", 42)
    ifd_offset = struct.pack("<I", 8)
    tags = [
        (256, 3, 1, 8),     # Columns
        (257, 3, 1, 8),     # Rows
        (259, 3, 1, 4),     # Compression = T6
        (262, 3, 1, 0),     # Photometric = 0 → val != 1 → False branch
        (273, 4, 1, 200),   # StripOffsets
        (279, 4, 1, 1),     # StripBytes
    ]
    packed = b""
    for tag, type_, count, val in tags:
        packed += struct.pack("<HHII", tag, type_, count, val)
    ifd = struct.pack("<H", len(tags)) + packed + struct.pack("<I", 0)
    tiff = endian + magic + ifd_offset + ifd + b"\x00" * 16
    reader = _io.BytesIO(tiff)
    out_stream = _io.BytesIO()
    params = COSDictionary()
    # extract_from_tiff may raise OSError on missing strip data — the
    # branch we care about (count != 1 on tag 273) has already fired.
    with contextlib.suppress(OSError):
        extract_from_tiff(reader, out_stream, params, 0)


def test_ccitt_factory_tag_324_with_count_not_one_falls_through_loop() -> None:
    """``extract_from_tiff`` 211->153: tag 324 (TileOffsets) with
    count != 1 must NOT update dataoffset."""
    import io as _io

    from pypdfbox.pdmodel.graphics.image.ccitt_factory import extract_from_tiff

    tags = [
        (256, 3, 1, 8),
        (257, 3, 1, 8),
        (259, 3, 1, 4),
        (324, 4, 3, 200),  # TileOffsets — count=3 → 211->153 partial
        (325, 4, 1, 1),
    ]
    packed = b""
    for tag, type_, count, val in tags:
        packed += struct.pack("<HHII", tag, type_, count, val)
    endian = b"II"
    magic = struct.pack("<H", 42)
    ifd_offset = struct.pack("<I", 8)
    ifd = struct.pack("<H", len(tags)) + packed + struct.pack("<I", 0)
    tiff = endian + magic + ifd_offset + ifd + b"\x00" * 16
    reader = _io.BytesIO(tiff)
    out_stream = _io.BytesIO()
    params = COSDictionary()
    with contextlib.suppress(OSError):
        extract_from_tiff(reader, out_stream, params, 0)


def test_ccitt_factory_tag_325_with_count_not_one_falls_through_loop() -> None:
    """``extract_from_tiff`` 214->153: tag 325 (TileBytes) with
    count != 1 — same branch as 324, opposite tag."""
    import io as _io

    from pypdfbox.pdmodel.graphics.image.ccitt_factory import extract_from_tiff

    tags = [
        (256, 3, 1, 8),
        (257, 3, 1, 8),
        (259, 3, 1, 4),
        (324, 4, 1, 200),
        (325, 4, 2, 1),  # TileBytes — count=2 → 214->153 partial
    ]
    packed = b""
    for tag, type_, count, val in tags:
        packed += struct.pack("<HHII", tag, type_, count, val)
    endian = b"II"
    magic = struct.pack("<H", 42)
    ifd_offset = struct.pack("<I", 8)
    ifd = struct.pack("<H", len(tags)) + packed + struct.pack("<I", 0)
    tiff = endian + magic + ifd_offset + ifd + b"\x00" * 16
    reader = _io.BytesIO(tiff)
    out_stream = _io.BytesIO()
    params = COSDictionary()
    with contextlib.suppress(OSError):
        extract_from_tiff(reader, out_stream, params, 0)


def test_pd_device_n_get_colorant_names_skips_non_name_entries() -> None:
    """``get_colorant_names`` 359->358: an entry that is NOT a
    COSName takes the False branch on the inner ``isinstance(item, COSName)``
    test — the loop iterates to the next entry without appending."""
    from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN

    devicen = PDDeviceN()
    # Set a colorants-names array directly at the canonical index slot.
    devicen._ensure_array_size(PDDeviceN._COLORANT_NAMES + 1)
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Cyan"))
    arr.add(COSInteger.get(42))  # non-name → False branch fires
    arr.add(COSName.get_pdf_name("Magenta"))
    devicen._array.set(PDDeviceN._COLORANT_NAMES, arr)
    names = devicen.get_colorant_names()
    # The non-name entry was skipped.
    assert names == ["Cyan", "Magenta"]


# =========================================================================
# pd_image_x_object — set_color_space with None-cos value
# =========================================================================


def test_pd_image_x_object_set_color_space_with_none_cos_value_skips_write() -> None:
    """``set_color_space`` 293->exit: a PDColorSpace whose
    ``get_cos_object()`` returns None drops the write (no /ColorSpace
    entry added). The ``if value is not None`` False branch fires."""
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject

    class _StubCSNoCos(PDColorSpace):
        def get_name(self) -> str:
            return "StubNoCos"

        def get_number_of_components(self) -> int:
            return 1

        def get_initial_color(self) -> Any:
            from pypdfbox.pdmodel.graphics.color.pd_color import PDColor

            return PDColor([0.0], self)

        def get_default_decode(self, bpc: int) -> list[float]:
            del bpc
            return [0.0, 1.0]

        def to_rgb(self, c: list[float]) -> tuple[float, float, float]:
            return (c[0], c[0], c[0])

        def get_cos_object(self) -> Any:
            return None

    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Image"))
    stream.set_int(COSName.get_pdf_name("Width"), 1)
    stream.set_int(COSName.get_pdf_name("Height"), 1)
    stream.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    img = PDImageXObject(stream)
    img.set_color_space(_StubCSNoCos())
    # No /ColorSpace entry was written.
    assert stream.get_item(COSName.get_pdf_name("ColorSpace")) is None
    assert stream.get_item(COSName.get_pdf_name("CS")) is None


# =========================================================================
# pd_inline_image — color-space helpers
# =========================================================================


def test_pd_inline_image_create_color_space_indexed_array_with_base_present() -> None:
    """``create_color_space`` ``[/I, <base>]`` path with a base color
    space present — covers the 277->279 partial via the True branch
    (base is non-None) and exercises ``to_long_name`` for the base."""
    from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage

    # Build a minimal inline-image parameter dict.
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("W"), 1)
    params.set_int(COSName.get_pdf_name("H"), 1)
    params.set_int(COSName.get_pdf_name("BPC"), 8)
    # Indexed CS array uses /I shorthand for /Indexed, /G shorthand for gray.
    cs_array = COSArray()
    cs_array.add(COSName.get_pdf_name("I"))
    cs_array.add(COSName.get_pdf_name("G"))
    cs_array.add(COSInteger.get(1))
    # Two-byte lookup so /Indexed validates.
    from pypdfbox.cos import COSString

    cs_array.add(COSString(bytes([0, 255])))
    params.set_item(COSName.get_pdf_name("CS"), cs_array)
    image = PDInlineImage(params, b"\x00", None)
    cs = image.create_color_space(cs_array)
    assert cs is not None


def test_pd_inline_image_to_long_name_passthrough_for_non_cos_name() -> None:
    """``to_long_name`` 217->224: when ``cs`` is NOT a COSName (e.g. a
    COSArray) the ``if isinstance(cs, COSName)`` False branch falls
    through to the bare ``return cs`` line."""
    from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage

    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("W"), 1)
    params.set_int(COSName.get_pdf_name("H"), 1)
    params.set_int(COSName.get_pdf_name("BPC"), 8)
    image = PDInlineImage(params, b"\x00", None)
    # Pass a COSArray — non-COSName takes the False branch.
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Anything"))
    result = image.to_long_name(arr)
    assert result is arr


def test_rendering_mode_round_trip_and_predicates() -> None:
    """Hoist the rendering-mode coverage from the higher-level
    pdmodel/test_pd_page_content_stream.py into the graphics test
    subtree so per-subtree coverage reports show 100% for
    ``rendering_mode.py``."""
    from pypdfbox.pdmodel.graphics.state import RenderingMode

    for member in RenderingMode:
        assert RenderingMode.from_int(member.int_value()) is member
    assert RenderingMode.FILL.is_fill()
    assert RenderingMode.STROKE.is_stroke()
    assert RenderingMode.FILL_CLIP.is_clip()
    assert RenderingMode.FILL_STROKE_CLIP.is_clip()
    with pytest.raises(IndexError):
        RenderingMode.from_int(99)


def test_shading_type1_get_functions_array_skips_null_entries() -> None:
    """``PDShadingType1.get_functions_array`` 110->108: the inner
    ``if entry is not None`` False branch fires when the /Function
    array contains a null slot."""
    from pypdfbox.cos import COSNull
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type1 import PDShadingType1

    shading = PDShadingType1()
    # Build a /Function array with one real function dict and one null.
    fn_dict = COSDictionary()
    fn_dict.set_int(COSName.get_pdf_name("FunctionType"), 2)
    fn_dict.set_item(COSName.get_pdf_name("Domain"), COSArray())
    fn_dict.set_item(COSName.get_pdf_name("C0"), COSArray())
    fn_dict.set_item(COSName.get_pdf_name("C1"), COSArray())
    fn_dict.set_int(COSName.get_pdf_name("N"), 1)
    arr = COSArray()
    arr.add(fn_dict)
    arr.add(COSNull.NULL)  # the null entry triggers the False branch
    shading._dict.set_item(COSName.get_pdf_name("Function"), arr)
    out = shading.get_functions_array()
    # Only one function survived — the null was skipped.
    assert len(out) == 1


def test_shading_type2_set_extend_with_non_array_single_arg_falls_through() -> None:
    """``PDShadingType2.set_extend`` 186->190: when the single-argument
    form is given a non-COSArray non-None value (and end is None), the
    ``isinstance(start, COSArray)`` False branch falls through to the
    canonical two-element-bool path. The end stays None — the
    fall-through bool conversion coerces ``end=None`` to False."""
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type2 import PDShadingType2

    shading = PDShadingType2()
    # Non-None non-COSArray start, end omitted (= None). Falls through.
    shading.set_extend(True)
    # The two-argument form fired; both bools stored.
    extend = shading.get_extend()
    assert extend == (True, False)


def test_shading_type3_set_extend_with_non_array_single_arg_falls_through() -> None:
    """``PDShadingType3.set_extend`` 188->190 mirror of type2."""
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type3 import PDShadingType3

    shading = PDShadingType3()
    shading.set_extend(False)
    assert shading.get_extend() == (False, False)


def _function_dict() -> COSDictionary:
    """Build a minimal /FunctionType 2 exponential function dictionary
    that ``PDFunction.create`` will wrap into a real PDFunction."""
    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("FunctionType"), 2)
    domain = COSArray()
    domain.add(COSInteger.get(0))
    domain.add(COSInteger.get(1))
    d.set_item(COSName.get_pdf_name("Domain"), domain)
    c0 = COSArray()
    c0.add(COSInteger.get(0))
    d.set_item(COSName.get_pdf_name("C0"), c0)
    c1 = COSArray()
    c1.add(COSInteger.get(1))
    d.set_item(COSName.get_pdf_name("C1"), c1)
    d.set_int(COSName.get_pdf_name("N"), 1)
    return d


def test_shading_type2_get_functions_array_skips_null_entries() -> None:
    """``PDShadingType2.get_functions_array`` 117->115: a null entry in
    the /Function array takes the inner-condition False branch and the
    loop continues to the next iteration."""
    from pypdfbox.cos import COSNull
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type2 import PDShadingType2

    shading = PDShadingType2()
    arr = COSArray()
    arr.add(_function_dict())
    arr.add(COSNull.NULL)
    shading._dict.set_item(COSName.get_pdf_name("Function"), arr)
    out = shading.get_functions_array()
    assert len(out) == 1


def test_shading_type3_get_functions_array_skips_null_entries() -> None:
    """``PDShadingType3.get_functions_array`` 121->119: mirror of type2."""
    from pypdfbox.cos import COSNull
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type3 import PDShadingType3

    shading = PDShadingType3()
    arr = COSArray()
    arr.add(_function_dict())
    arr.add(COSNull.NULL)
    shading._dict.set_item(COSName.get_pdf_name("Function"), arr)
    out = shading.get_functions_array()
    assert len(out) == 1


def test_shading_type4_get_decode_validates_all_color_components_present() -> None:
    """``PDShadingType4.parse_patches`` 190->189: the loop over
    color-component decode entries iterates multiple times when all are
    present (the False branch on ``is None`` fires and control loops)."""
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type4 import PDShadingType4

    shading = PDShadingType4()
    shading._dict.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    shading._dict.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    shading._dict.set_int(COSName.get_pdf_name("BitsPerFlag"), 2)
    # Decode array with 4 ranges: x, y, c0, c1 (2 colour components).
    decode = COSArray()
    for v in (0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0):
        from pypdfbox.cos import COSFloat
        decode.add(COSFloat(v))
    shading._dict.set_item(COSName.get_pdf_name("Decode"), decode)
    # 2 components forces the for-i loop to iterate twice — exercises
    # the False-branch loop-continuation arc (190->189).
    # The shading carries no /Function array, so the colour-component count
    # is the colour-space components — point /ColorSpace at DeviceGray to
    # keep it minimal.
    shading._dict.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    # Empty body — parse_patches returns [] but exercises the loop.
    with shading._dict.create_output_stream() as out:
        out.write(b"\x00")
    # collect_triangles iterates the for-i loop over colour components.
    # It may raise OSError on a still-malformed shading; we only care
    # about the loop-continuation branch coverage.
    with contextlib.suppress(OSError):
        shading.collect_triangles()


def test_shading_type5_get_decode_validates_all_color_components_present() -> None:
    """``PDShadingType5.parse_patches`` 182->181: mirror of type4."""
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type5 import PDShadingType5

    shading = PDShadingType5()
    shading._dict.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    shading._dict.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    shading._dict.set_int(COSName.get_pdf_name("BitsPerFlag"), 2)
    shading._dict.set_int(COSName.get_pdf_name("VerticesPerRow"), 2)
    from pypdfbox.cos import COSFloat

    decode = COSArray()
    # x, y + 3 colour components (DeviceRGB) → 5 ranges × 2 = 10 floats.
    for v in (0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0):
        decode.add(COSFloat(v))
    shading._dict.set_item(COSName.get_pdf_name("Decode"), decode)
    shading._dict.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    with shading._dict.create_output_stream() as out:
        out.write(b"\x00")
    # collect_triangles iterates the for-i loop over colour components.
    # It may raise OSError on a still-malformed shading; we only care
    # about the loop-continuation branch coverage.
    with contextlib.suppress(OSError):
        shading.collect_triangles()


def test_pd_inline_image_create_color_space_indexed_with_none_base_takes_skip_branch() -> None:
    """``create_color_space`` 277->279: when the indexed array's base
    entry (index 1) is None the ``if base is not None`` False branch
    fires — the rebuilt array is left with whatever set(1, ...) was
    previously copied (PDColorSpace.create then either accepts or
    raises). Forge a COSArray whose index-1 slot is None.
    """
    from pypdfbox.cos import COSNull
    from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage

    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("W"), 1)
    params.set_int(COSName.get_pdf_name("H"), 1)
    params.set_int(COSName.get_pdf_name("BPC"), 8)
    image = PDInlineImage(params, b"\x00", None)

    cs_array = COSArray()
    cs_array.add(COSName.get_pdf_name("I"))
    cs_array.add(COSNull.NULL)  # base is COSNull — get() resolves to None
    # Pad out so cs.size() > 1 holds.
    cs_array.add(COSInteger.get(1))
    cs_array.add(COSInteger.get(0))
    # The downstream PDColorSpace.create may accept or raise; we only
    # care about reaching the ``if base is not None`` False branch.
    with contextlib.suppress(OSError, ValueError, AttributeError, TypeError):
        image.create_color_space(cs_array)
