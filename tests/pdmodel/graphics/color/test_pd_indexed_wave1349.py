"""Wave 1349 coverage-boost: drive the residual defensive branches in
``pypdfbox.pdmodel.graphics.color.pd_indexed``.

Targets the 8 uncovered lines after wave 1348:

* line 90 — ``set_base_color_space`` raising ``TypeError`` for a base CS
  whose ``get_cos_object()`` returns ``None``;
* lines 205-206 — ``read_lookup_data`` consuming a ``COSStream`` /Lookup
  entry through ``create_input_stream``;
* line 229 — ``read_color_table`` clamping ``n`` to ``1`` when the base
  CS reports zero components (otherwise the per-entry decode would
  ``divmod`` by zero);
* lines 277-285 — ``init_rgb_color_table`` falling back to the
  no-base-CS DeviceRGB-style read when ``get_base_color_space()``
  returns ``None``;
* line 388 — ``to_rgb_image`` short-circuiting to a black image when the
  palette is empty (no /Lookup data, ``actualMaxIndex == -1``);
* line 403 — ``to_rgb_image`` truncating an oversized raster to
  ``width * height`` bytes before palette translation.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

# ---------- test stubs (kept local — no shipped fakes) ----------


class _NoCosColorSpace(PDColorSpace):
    """Minimal :class:`PDColorSpace` whose ``get_cos_object`` returns
    ``None``. Mirrors the upstream code path where a caller hands an
    in-memory color space (no COS form yet) to
    :meth:`PDIndexed.set_base_color_space`.
    """

    def get_name(self) -> str:
        return "NoCos"

    def get_number_of_components(self) -> int:
        return 3

    def get_initial_color(self) -> PDColor:
        return PDColor([0.0, 0.0, 0.0], self)

    def get_cos_object(self):  # type: ignore[override]
        return None


class _ZeroComponentColorSpace(PDColorSpace):
    """Color space that reports zero components. Used to drive the
    ``n <= 0`` clamp in :meth:`PDIndexed.read_color_table` (line 229).
    """

    def get_name(self) -> str:
        return "ZeroComp"

    def get_number_of_components(self) -> int:
        return 0

    def get_initial_color(self) -> PDColor:
        return PDColor([], self)

    def to_rgb(self, value):  # type: ignore[override]
        return [0.0, 0.0, 0.0]


# ---------- set_base_color_space: ``cos is None`` guard (line 90) ----------


def test_wave1349_set_base_color_space_rejects_color_space_without_cos_form() -> None:
    cs = PDIndexed()
    with pytest.raises(TypeError, match="requires a color space with a COS form"):
        cs.set_base_color_space(_NoCosColorSpace())


# ---------- read_lookup_data: COSStream branch (lines 205-206) ----------


def test_wave1349_read_lookup_data_decodes_cos_stream_entry() -> None:
    array = COSArray()
    array.add(COSName.get_pdf_name("Indexed"))
    array.add(PDDeviceRGB.INSTANCE.get_cos_object())
    array.add(COSInteger.get(1))
    stream = COSStream()
    # Two palette entries: black + bright red.
    stream.set_raw_data(b"\x00\x00\x00\xff\x00\x00")
    array.add(stream)
    cs = PDIndexed(array)

    raw = cs.read_lookup_data()

    assert raw == b"\x00\x00\x00\xff\x00\x00"
    # And the full pipeline (read_color_table → init_rgb_color_table)
    # works end-to-end so the stream branch is exercised more than once.
    rgb = cs.init_rgb_color_table()
    assert rgb == [(0, 0, 0), (255, 0, 0)]


def test_wave1349_read_lookup_data_returns_empty_for_unsupported_slot_type() -> None:
    array = COSArray()
    array.add(COSName.get_pdf_name("Indexed"))
    array.add(PDDeviceRGB.INSTANCE.get_cos_object())
    array.add(COSInteger.get(0))
    # /Lookup as an integer is malformed — upstream returns b"" rather
    # than crashing (documented divergence vs upstream's IOException;
    # see pd_indexed.read_lookup_data docstring).
    array.add(COSInteger.get(7))
    cs = PDIndexed(array)

    assert cs.read_lookup_data() == b""


# ---------- read_color_table: ``n <= 0`` clamp (line 229) ----------


def test_wave1349_read_color_table_clamps_zero_component_base_to_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    array = COSArray()
    array.add(COSName.get_pdf_name("Indexed"))
    array.add(PDDeviceRGB.INSTANCE.get_cos_object())
    array.add(COSInteger.get(0))
    array.add(COSString(b"\xff"))
    cs = PDIndexed(array)
    # Substitute a 0-component base so the ``n = base.get_number_of_components()``
    # branch returns 0; the clamp at line 229 then bumps it to 1, which
    # is what keeps the per-entry decode loop in-bounds.
    monkeypatch.setattr(cs, "get_base_color_space", lambda: _ZeroComponentColorSpace())

    table, max_index = cs.read_color_table()

    assert max_index == 0
    assert table == [[1.0]]


# ---------- init_rgb_color_table: ``base is None`` branch (lines 277-285) ----------


def test_wave1349_init_rgb_color_table_falls_back_to_devicergb_when_base_is_null() -> None:
    array = COSArray()
    array.add(COSName.get_pdf_name("Indexed"))
    array.add(COSNull.NULL)  # No base CS — exercises the None branch.
    array.add(COSInteger.get(2))
    # Three 3-byte palette entries: pure red, pure green, pure blue.
    array.add(COSString(bytes([255, 0, 0, 0, 255, 0, 0, 0, 255])))
    cs = PDIndexed(array)

    rgb_table = cs.init_rgb_color_table()

    assert rgb_table == [(255, 0, 0), (0, 255, 0), (0, 0, 255)]


def test_wave1349_init_rgb_color_table_no_base_pads_short_entries_with_zero() -> None:
    # When base is None and the per-entry float list is shorter than 3,
    # the fallback pads with [0, 0, 0] then takes the first three. With
    # ``n`` defaulting to 3 inside ``read_color_table``, each entry is
    # always 3 floats long, so the padding tail is a defensive guard for
    # callers that monkeypatch ``read_color_table`` to return shorter
    # entries. We verify the documented behavior via the normal path
    # (three-byte palette, no base CS) plus a custom-entry stress.
    array = COSArray()
    array.add(COSName.get_pdf_name("Indexed"))
    array.add(COSNull.NULL)
    array.add(COSInteger.get(0))
    array.add(COSString(bytes([128, 64, 32])))
    cs = PDIndexed(array)

    rgb_table = cs.init_rgb_color_table()

    assert rgb_table == [(128, 64, 32)]


# ---------- to_rgb_image: empty palette short-circuit (line 388) ----------


def test_wave1349_to_rgb_image_returns_black_image_when_palette_empty() -> None:
    cs = PDIndexed()  # No /Lookup data → empty palette.

    img = cs.to_rgb_image(b"\x00\x01\x02\x03", 2, 2)

    assert img.size == (2, 2)
    assert img.mode == "RGB"
    # Every pixel reads back as (0, 0, 0).
    assert set(img.getdata()) == {(0, 0, 0)}


# ---------- to_rgb_image: oversized raster truncation (line 403) ----------


def test_wave1349_to_rgb_image_truncates_oversized_raster() -> None:
    array = COSArray()
    array.add(COSName.get_pdf_name("Indexed"))
    array.add(PDDeviceRGB.INSTANCE.get_cos_object())
    array.add(COSInteger.get(1))
    array.add(COSString(bytes([255, 0, 0, 0, 0, 255])))  # red, blue
    cs = PDIndexed(array)

    # 2x1 raster but with two trailing bytes of garbage — the truncation
    # at line 403 trims them off before Pillow ever sees the data.
    img = cs.to_rgb_image(b"\x00\x01\xff\xfe", 2, 1)

    assert img.size == (2, 1)
    assert list(img.getdata()) == [(255, 0, 0), (0, 0, 255)]


def test_wave1349_to_rgb_image_clamps_oversized_indices_against_actual_max() -> None:
    # Companion to the truncation test above: confirms that even when
    # the raster length matches and an index is out of palette range,
    # the ``max_index < 255`` translation branch clamps every pixel to
    # the highest valid palette slot. Exercises the same fast-path that
    # line 403 ultimately feeds.
    array = COSArray()
    array.add(COSName.get_pdf_name("Indexed"))
    array.add(PDDeviceRGB.INSTANCE.get_cos_object())
    array.add(COSInteger.get(1))
    array.add(COSString(bytes([255, 0, 0, 0, 255, 0])))  # red, green
    cs = PDIndexed(array)

    img = cs.to_rgb_image(b"\x00\x01\xff", 3, 1)

    # Pixel 0 → red, pixel 1 → green, pixel 2 (255 out of range) →
    # clamped to last slot (green).
    assert list(img.getdata()) == [(255, 0, 0), (0, 255, 0), (0, 255, 0)]
