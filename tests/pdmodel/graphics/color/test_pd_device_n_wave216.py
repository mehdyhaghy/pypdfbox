"""Wave 216 round-out tests for :class:`PDDeviceN`,
:class:`PDDeviceNAttributes` and :class:`PDDeviceNProcess`.

Covers four small gaps against upstream PDFBox:

- ``PDDeviceN.__str__`` — upstream ``toString`` form with colorants,
  alternate, tint, attributes.
- ``PDDeviceNAttributes.__str__`` — upstream ``toString`` form with
  subtype prefix, optional process and colorants map.
- ``PDDeviceNProcess.__str__`` — upstream ``toString`` form
  ``Process{<cs> "<comp>"...}``.
- ``PDDeviceN.has_attributes`` — typed predicate over the
  ``/Attributes`` slot.
- ``PDDeviceN.get_colorant_index`` — name → index lookup, ``-1`` for
  missing.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_device_n import (
    PDDeviceN,
    PDDeviceNAttributes,
    PDDeviceNProcess,
)

# ---------- helpers ----------


def _type2(c0: list[float], c1: list[float], n: float = 1.0) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", COSArray.of_cos_floats([0.0, 1.0]))
    d.set_item("C0", COSArray.of_cos_floats(c0))
    d.set_item("C1", COSArray.of_cos_floats(c1))
    d.set_item("N", COSFloat(n))
    return d


def _device_n(
    colorants: list[str],
    tint: COSDictionary,
    alternate: str = "DeviceCMYK",
    attributes: COSDictionary | None = None,
) -> PDDeviceN:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(COSArray.of_cos_names(colorants))
    arr.add(COSName.get_pdf_name(alternate))
    arr.add(tint)
    if attributes is not None:
        arr.add(attributes)
    return PDDeviceN(arr)


# ---------- PDDeviceN.has_attributes ----------


def test_has_attributes_false_when_slot_absent() -> None:
    cs = _device_n(["X"], _type2([0.0], [1.0]))
    assert cs.has_attributes() is False


def test_has_attributes_true_when_attributes_dict_present() -> None:
    attrs = COSDictionary()
    attrs.set_name("Subtype", "DeviceN")
    cs = _device_n(["X"], _type2([0.0], [1.0]), attributes=attrs)
    assert cs.has_attributes() is True


def test_has_attributes_round_trip_via_setter() -> None:
    cs = PDDeviceN()
    assert cs.has_attributes() is False
    a = PDDeviceNAttributes()
    a.set_subtype("NChannel")
    cs.set_attributes(a)
    assert cs.has_attributes() is True
    cs.set_attributes(None)
    assert cs.has_attributes() is False


def test_has_attributes_false_when_slot_is_not_dictionary() -> None:
    """If the /Attributes slot exists but doesn't carry a COSDictionary
    (e.g. truncated PDF with placeholder), has_attributes is False —
    matches the lenient None return in get_attributes."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(COSArray.of_cos_names(["X"]))
    arr.add(COSName.get_pdf_name("DeviceCMYK"))
    arr.add(_type2([0.0], [1.0]))
    arr.add(COSName.get_pdf_name("Bogus"))  # not a dictionary
    cs = PDDeviceN(arr)
    assert cs.has_attributes() is False


# ---------- PDDeviceN.get_colorant_index ----------


def test_get_colorant_index_finds_first_position() -> None:
    cs = _device_n(
        ["Cyan", "Magenta", "Yellow", "Black"],
        _type2([0.0] * 4, [1.0] * 4),
    )
    assert cs.get_colorant_index("Cyan") == 0


def test_get_colorant_index_finds_middle_position() -> None:
    cs = _device_n(
        ["Cyan", "Magenta", "Yellow", "Black"],
        _type2([0.0] * 4, [1.0] * 4),
    )
    assert cs.get_colorant_index("Yellow") == 2


def test_get_colorant_index_returns_minus_one_when_absent() -> None:
    cs = _device_n(["Cyan", "Magenta"], _type2([0.0, 0.0], [1.0, 1.0]))
    assert cs.get_colorant_index("Spot1") == -1


def test_get_colorant_index_empty_default_ctor() -> None:
    assert PDDeviceN().get_colorant_index("Anything") == -1


def test_get_colorant_index_case_sensitive() -> None:
    """PDF colorant names are case-sensitive (PDF 32000-1 §7.3.5)."""
    cs = _device_n(["Cyan"], _type2([0.0], [1.0]))
    assert cs.get_colorant_index("cyan") == -1
    assert cs.get_colorant_index("Cyan") == 0


# ---------- PDDeviceNProcess.__str__ ----------


def test_process_str_empty_default() -> None:
    """Default process dict has no /ColorSpace and no /Components —
    upstream renders that as ``Process{None}``."""
    assert str(PDDeviceNProcess()) == "Process{None}"


def test_process_str_with_color_space_and_components() -> None:
    d = COSDictionary()
    d.set_item("ColorSpace", COSName.get_pdf_name("DeviceCMYK"))
    d.set_item(
        "Components",
        COSArray.of_cos_names(["Cyan", "Magenta", "Yellow", "Black"]),
    )
    p = PDDeviceNProcess(d)
    rendered = str(p)
    assert rendered.startswith('Process{DeviceCMYK')
    assert '"Cyan"' in rendered
    assert '"Black"' in rendered
    assert rendered.endswith("}")


# ---------- PDDeviceNAttributes.__str__ ----------


def test_attributes_str_empty_default() -> None:
    """Default attributes (no subtype, no process, no colorants) renders
    with empty subtype prefix and empty colorants map."""
    assert str(PDDeviceNAttributes()) == "{Colorants{}}"


def test_attributes_str_with_subtype_only() -> None:
    a = PDDeviceNAttributes()
    a.set_subtype("NChannel")
    assert str(a) == "NChannel{Colorants{}}"


def test_attributes_str_with_process() -> None:
    process_dict = COSDictionary()
    process_dict.set_item("ColorSpace", COSName.get_pdf_name("DeviceRGB"))
    process_dict.set_item(
        "Components", COSArray.of_cos_names(["Red", "Green", "Blue"])
    )
    attrs_dict = COSDictionary()
    attrs_dict.set_name("Subtype", "NChannel")
    attrs_dict.set_item("Process", process_dict)
    rendered = str(PDDeviceNAttributes(attrs_dict))
    # Subtype prefix and process appear in order, then colorants block.
    assert rendered.startswith("NChannel{Process{DeviceRGB")
    assert rendered.endswith("Colorants{}}")


def test_attributes_str_with_colorants() -> None:
    """Verify that named colorants appear in the colorants block. Build
    a Separation entry and confirm both name and CS-name surface."""
    sep_arr = COSArray()
    sep_arr.add(COSName.get_pdf_name("Separation"))
    sep_arr.add(COSName.get_pdf_name("PANTONE 185 C"))
    sep_arr.add(COSName.get_pdf_name("DeviceCMYK"))
    sep_arr.add(_type2([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 1.0, 0.0]))

    colorants_dict = COSDictionary()
    colorants_dict.set_item("PANTONE 185 C", sep_arr)
    attrs_dict = COSDictionary()
    attrs_dict.set_name("Subtype", "DeviceN")
    attrs_dict.set_item("Colorants", colorants_dict)

    rendered = str(PDDeviceNAttributes(attrs_dict))
    assert rendered.startswith("DeviceN{Colorants{")
    assert '"PANTONE 185 C": Separation' in rendered


# ---------- PDDeviceN.__str__ ----------


def test_device_n_str_default_ctor_lenient() -> None:
    """Default ctor leaves placeholder name slots — __str__ must not
    raise; alternate falls back to ``"None"`` and tint to ``"None"``."""
    rendered = str(PDDeviceN())
    assert rendered.startswith("DeviceN{")
    assert rendered.endswith("}")
    # No colorants in default ctor, no attributes appended.
    assert "Colorants" not in rendered


def test_device_n_str_full_form() -> None:
    cs = _device_n(
        ["Cyan", "Magenta"],
        _type2([0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]),
        alternate="DeviceCMYK",
    )
    rendered = str(cs)
    assert rendered.startswith('DeviceN{"Cyan" "Magenta" DeviceCMYK ')
    assert rendered.endswith("}")


def test_device_n_str_includes_attributes_when_present() -> None:
    attrs = COSDictionary()
    attrs.set_name("Subtype", "NChannel")
    cs = _device_n(
        ["X"],
        _type2([0.0], [1.0]),
        attributes=attrs,
    )
    rendered = str(cs)
    # Attributes section shows up after the tint section.
    assert "NChannel{Colorants{}}" in rendered
    assert rendered.endswith("}")


def test_device_n_str_omits_attributes_when_absent() -> None:
    cs = _device_n(["X"], _type2([0.0], [1.0]))
    rendered = str(cs)
    assert "NChannel" not in rendered
    assert "Colorants" not in rendered
