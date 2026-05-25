"""Wave 1403 branch-closure test for
:meth:`PDDeviceN.to_rgb_with_attributes`.

* ``656->658`` — the lazy attribute-cache build is *skipped* when
  ``self._spot_color_spaces`` is already populated: the
  ``if not self._spot_color_spaces and self.has_attributes()`` guard is
  false, so we go straight to the per-colorant blend at 658.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB


def _make_type2_identity(n_in: int, n_out: int) -> COSDictionary:
    d = COSDictionary()
    d.set_int(COSName.get_pdf_name("FunctionType"), 2)
    domain = COSArray()
    for _ in range(n_in):
        domain.add(COSFloat(0.0))
        domain.add(COSFloat(1.0))
    d.set_item(COSName.get_pdf_name("Domain"), domain)
    rng = COSArray()
    for _ in range(n_out):
        rng.add(COSFloat(0.0))
        rng.add(COSFloat(1.0))
    d.set_item(COSName.get_pdf_name("Range"), rng)
    c0 = COSArray()
    c1 = COSArray()
    for _ in range(n_out):
        c0.add(COSFloat(0.0))
        c1.add(COSFloat(1.0))
    d.set_item(COSName.get_pdf_name("C0"), c0)
    d.set_item(COSName.get_pdf_name("C1"), c1)
    d.set_item(COSName.get_pdf_name("N"), COSFloat(1.0))
    return d


def _make_devicen_with_process() -> PDDeviceN:
    process_dict = COSDictionary()
    process_dict.set_item(
        COSName.get_pdf_name("ColorSpace"),
        PDDeviceCMYK.INSTANCE.get_cos_object(),
    )
    components = COSArray()
    for name in ["Cyan", "Magenta", "Yellow", "Black"]:
        components.add(COSName.get_pdf_name(name))
    process_dict.set_item(COSName.get_pdf_name("Components"), components)
    attrs_dict = COSDictionary()
    attrs_dict.set_item(COSName.get_pdf_name("Process"), process_dict)

    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    names_array = COSArray()
    for n in ["Cyan", "Magenta", "Yellow", "Black"]:
        names_array.add(COSName.get_pdf_name(n))
    arr.add(names_array)
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(_make_type2_identity(4, 3))
    arr.add(attrs_dict)
    return PDDeviceN(arr)


def test_to_rgb_with_attributes_skips_cache_build_when_already_populated() -> None:
    """Pre-populate the spot-colour-space cache via an explicit
    ``init_color_conversion_cache()`` call, then invoke
    ``to_rgb_with_attributes``. On entry ``self._spot_color_spaces`` is
    truthy, so the lazy-build guard is false (656 → 658) and the
    per-colorant blend runs directly."""
    cs = _make_devicen_with_process()
    cs.init_color_conversion_cache()
    assert cs._spot_color_spaces  # cache populated -> guard will be false
    rgb = cs.to_rgb_with_attributes([0.0, 0.0, 0.0, 0.0])
    assert rgb is not None
    assert len(rgb) == 3
    for channel in rgb:
        assert 0.0 <= channel <= 1.0
