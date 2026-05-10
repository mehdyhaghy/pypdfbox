"""Round-out wave tests for graphics/color parity additions.

Covers the small set of mechanical parity gaps closed in this wave:

* :meth:`PDIndexed.__str__` — upstream ``PDIndexed.toString``.
* :meth:`PDLab.get_a_range` / :meth:`PDLab.get_b_range` /
  :meth:`PDLab.set_a_range` / :meth:`PDLab.set_b_range` — upstream
  per-component ``getARange`` / ``getBRange`` / ``setARange`` /
  ``setBRange`` (PDRange tuples become ``(min, max)`` in the lite
  surface, matching :meth:`PDICCBased.get_range_for_component`).
* :meth:`PDSeparation.__str__` — upstream ``PDSeparation.toString``.
* :meth:`PDDeviceNAttributes.set_colorants` — upstream
  ``PDDeviceNAttributes.setColorants(Map)``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceNAttributes
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation

# ---------- helpers ----------


def _type2(c0: list[float], c1: list[float]) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", COSArray.of_cos_floats([0.0, 1.0]))
    d.set_item("C0", COSArray.of_cos_floats(c0))
    d.set_item("C1", COSArray.of_cos_floats(c1))
    d.set_item("N", COSFloat(1.0))
    return d


def _make_indexed(hival: int, lookup: COSString) -> PDIndexed:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(hival))
    arr.add(lookup)
    return PDIndexed(arr)


# ---------- PDIndexed.__str__ ----------


def test_pd_indexed_str_includes_base_hival_and_lookup_count() -> None:
    """``str(indexed)`` mirrors upstream ``PDIndexed.toString``:
    ``Indexed{base:DeviceRGB hival:3 lookup:(4 entries)}``."""
    cs = _make_indexed(3, COSString(bytes(range(0, 12))))
    assert str(cs) == "Indexed{base:DeviceRGB hival:3 lookup:(4 entries)}"


def test_pd_indexed_str_handles_empty_lookup_gracefully() -> None:
    """A default-ctor PDIndexed has a ``COSNull`` lookup slot — string
    form must not blow up; report ``0 entries``."""
    s = str(PDIndexed())
    assert s.startswith("Indexed{base:DeviceRGB hival:255")
    assert "lookup:(0 entries)" in s


def test_pd_indexed_str_reports_palette_entry_count_for_grayscale_base() -> None:
    """For a 1-component base CS (grayscale equivalent), the palette
    entry count is ``len(lookup)``. Build with DeviceGray-equivalent
    via DeviceRGB but smaller — verify the count formula divides by
    base components."""
    # 7 entries * 3 RGB components = 21 bytes, hival=6
    cs = _make_indexed(6, COSString(bytes(range(0, 21))))
    assert "lookup:(7 entries)" in str(cs)


# ---------- PDLab a/b range accessors ----------


def test_pd_lab_get_a_range_default_is_minus_100_to_100() -> None:
    assert PDLab().get_a_range() == (-100.0, 100.0)


def test_pd_lab_get_b_range_default_is_minus_100_to_100() -> None:
    assert PDLab().get_b_range() == (-100.0, 100.0)


def test_pd_lab_get_a_range_reads_from_full_range_array() -> None:
    cs = PDLab()
    cs.set_range([-80.0, 80.0, -60.0, 60.0])
    assert cs.get_a_range() == (-80.0, 80.0)
    assert cs.get_b_range() == (-60.0, 60.0)


def test_pd_lab_set_a_range_only_touches_a_slots() -> None:
    cs = PDLab()
    cs.set_range([-80.0, 80.0, -60.0, 60.0])
    cs.set_a_range((-50.0, 50.0))
    # a moved, b stayed
    assert cs.get_a_range() == (-50.0, 50.0)
    assert cs.get_b_range() == (-60.0, 60.0)
    assert cs.get_range() == [-50.0, 50.0, -60.0, 60.0]


def test_pd_lab_set_b_range_only_touches_b_slots() -> None:
    cs = PDLab()
    cs.set_range([-80.0, 80.0, -60.0, 60.0])
    cs.set_b_range((-30.0, 30.0))
    assert cs.get_a_range() == (-80.0, 80.0)
    assert cs.get_b_range() == (-30.0, 30.0)


def test_pd_lab_set_a_range_none_resets_to_default() -> None:
    """Upstream's ``setARange(null)`` resets the a* slots to (-100, 100)."""
    cs = PDLab()
    cs.set_range([-50.0, 50.0, -25.0, 25.0])
    cs.set_a_range(None)
    assert cs.get_a_range() == (-100.0, 100.0)
    # b is preserved
    assert cs.get_b_range() == (-25.0, 25.0)


def test_pd_lab_set_b_range_none_resets_to_default() -> None:
    cs = PDLab()
    cs.set_range([-50.0, 50.0, -25.0, 25.0])
    cs.set_b_range(None)
    assert cs.get_a_range() == (-50.0, 50.0)
    assert cs.get_b_range() == (-100.0, 100.0)


def test_pd_lab_set_component_range_creates_range_array_if_missing() -> None:
    """If ``/Range`` was never written, the component setter must
    create the 4-entry array first."""
    cs = PDLab()
    # Confirm /Range is missing before the call
    params = cs.get_cos_object().get_object(1)
    assert isinstance(params, COSDictionary)
    assert params.get_dictionary_object(COSName.get_pdf_name("Range")) is None
    cs.set_a_range((-10.0, 10.0))
    rng = params.get_dictionary_object(COSName.get_pdf_name("Range"))
    assert isinstance(rng, COSArray)
    assert rng.to_float_array() == pytest.approx([-10.0, 10.0, -100.0, 100.0])


def test_pd_lab_set_range_invalidates_initial_color() -> None:
    """Upstream sets ``initialColor = null`` after setComponentRangeArray
    so that the next ``getInitialColor`` recomputes against the new
    range. Verify the recomputation by exercising both setters."""
    cs = PDLab()
    # Set positive a-min so the initial color picks it up.
    cs.set_a_range((10.0, 50.0))
    initial = cs.get_initial_color()
    # Initial color is [0, max(0, a_min), max(0, b_min)]
    assert initial.get_components() == [0.0, 10.0, 0.0]
    cs.set_b_range((20.0, 60.0))
    initial = cs.get_initial_color()
    assert initial.get_components() == [0.0, 10.0, 20.0]


# ---------- PDSeparation.__str__ ----------


def test_pd_separation_str_format_matches_upstream_shape() -> None:
    """Upstream: ``Separation{"<colorant>" <alt name> <tint>}``."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name("PANTONE 185 C"))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    arr.add(_type2([0.0, 0.0, 0.0], [1.0, 0.0, 0.0]))
    cs = PDSeparation(arr)
    s = str(cs)
    assert s.startswith('Separation{"PANTONE 185 C" DeviceRGB ')
    assert s.endswith("}")


def test_pd_separation_str_default_ctor_uses_empty_colorant_and_none_alt() -> None:
    """Default-ctor placeholders → empty colorant, ``None`` alternate,
    ``None`` tint. The string form must not blow up."""
    s = str(PDSeparation())
    assert s == 'Separation{"" None None}'


def test_pd_separation_str_after_setters_round_trips() -> None:
    cs = PDSeparation()
    cs.set_colorant_name("Black")
    cs.set_alternate_color_space(PDDeviceRGB.INSTANCE)
    cs.set_tint_transform(_type2([0.0, 0.0, 0.0], [0.0, 0.0, 0.0]))
    s = str(cs)
    assert s.startswith('Separation{"Black" DeviceRGB ')


# ---------- PDDeviceNAttributes.set_colorants ----------


def test_pd_device_n_attributes_set_colorants_writes_dict_entry() -> None:
    """``set_colorants`` populates ``/Colorants`` with each entry's COS
    representation. We seed values with named device color spaces (each
    serializes to its own COSName), so the keys/values can be inspected
    via the COS dictionary directly."""
    attrs = PDDeviceNAttributes()
    attrs.set_colorants(
        {
            "Cyan": PDDeviceRGB.INSTANCE,
            "Magenta": PDDeviceRGB.INSTANCE,
        }
    )
    cos = attrs.get_cos_dictionary()
    colorants = cos.get_dictionary_object(COSName.get_pdf_name("Colorants"))
    assert isinstance(colorants, COSDictionary)
    assert set(k.get_name() for k in colorants.key_set()) == {"Cyan", "Magenta"}


def test_pd_device_n_attributes_set_colorants_round_trips_via_get() -> None:
    """A round trip through the typed accessor recovers the same set of
    keys (with PDColorSpace values reified through ``PDColorSpace.create``)."""
    attrs = PDDeviceNAttributes()
    attrs.set_colorants({"Spot1": PDDeviceRGB.INSTANCE})
    out = attrs.get_colorants()
    assert set(out.keys()) == {"Spot1"}
    # Reified via PDColorSpace.create - should still report DeviceRGB.
    assert out["Spot1"].get_name() == "DeviceRGB"


def test_pd_device_n_attributes_set_colorants_none_removes_entry() -> None:
    """Upstream: passing ``null`` writes a ``null`` value (which the
    writer drops). In pypdfbox we just drop the key — equivalent
    observable behaviour."""
    attrs = PDDeviceNAttributes()
    attrs.set_colorants({"Cyan": PDDeviceRGB.INSTANCE})
    attrs.set_colorants(None)
    cos = attrs.get_cos_dictionary()
    assert cos.get_dictionary_object(COSName.get_pdf_name("Colorants")) is None
    assert attrs.get_colorants() == {}


def test_pd_device_n_attributes_set_colorants_replaces_existing_map() -> None:
    """A second call with a fresh map should replace, not merge."""
    attrs = PDDeviceNAttributes()
    attrs.set_colorants(
        {
            "Cyan": PDDeviceRGB.INSTANCE,
            "Magenta": PDDeviceRGB.INSTANCE,
        }
    )
    attrs.set_colorants({"Yellow": PDDeviceRGB.INSTANCE})
    out = attrs.get_colorants()
    assert set(out.keys()) == {"Yellow"}
