"""Wave 1276 — hand-written coverage for :class:`PDDefaultAppearanceString`.

Exercises the parser (Tf / g / rg / k operators), the accessor surface
(font / size / colour), and the side-effect writers (``write_to`` /
``copy_needed_resources_to``).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.interactive.form.pd_default_appearance_string import (
    PDDefaultAppearanceString,
)
from pypdfbox.pdmodel.pd_resources import PDResources


def _helvetica() -> PDType1Font:
    helv = PDType1Font()
    helv.get_cos_object().set_name(
        COSName.get_pdf_name("BaseFont"), PDType1Font.HELVETICA
    )
    helv.get_cos_object().set_name(COSName.get_pdf_name("Subtype"), "Type1")
    return helv


def _resources_with_font(name: str = "Helv") -> tuple[PDResources, COSName]:
    res = PDResources()
    key = res.add(_helvetica())
    # ``res.add`` returns the synthesised key (``F0`` by default); allow
    # the caller to dictate the resource name when needed for parity with
    # upstream ``processSetFont`` resolving by exact ``/DA`` font name.
    if key.get_name() != name:
        helv = _helvetica()
        res.put(
            COSName.get_pdf_name("Font"),
            COSName.get_pdf_name(name),
            helv.get_cos_object(),
        )
        return res, COSName.get_pdf_name(name)
    return res, key


# ---------- constructor argument validation ----------


def test_constructor_rejects_none_da() -> None:
    res, _ = _resources_with_font()
    with pytest.raises(ValueError, match="/DA"):
        PDDefaultAppearanceString(None, res)


def test_constructor_rejects_none_dr() -> None:
    with pytest.raises(ValueError, match="/DR"):
        PDDefaultAppearanceString(COSString("/Helv 12 Tf 0 g"), None)


# ---------- parsing: Tf operator ----------


def test_parses_font_name_and_size_from_tf() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf"), res)
    assert da.get_font_name() == COSName.get_pdf_name("Helv")
    assert da.get_font_size() == pytest.approx(12.0)
    assert da.get_font() is not None


def test_parses_fractional_font_size() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("/Helv 10.5 Tf"), res)
    assert da.get_font_size() == pytest.approx(10.5)


def test_default_font_size_is_twelve_when_no_tf() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("0 g"), res)
    assert da.get_font_size() == pytest.approx(12.0)
    assert da.get_font() is None
    assert da.get_font_name() is None


def test_unknown_font_falls_back_to_helvetica() -> None:
    """PDFBOX-2661 fallback path — when /DR lacks the named font,
    substitute Standard-14 Helvetica instead of raising. Diverges from
    upstream (recorded in ``CHANGES.md``) so fields with broken /DA
    strings still render."""
    from pypdfbox.pdmodel.font import PDType1Font  # noqa: PLC0415

    res = PDResources()
    da = PDDefaultAppearanceString(COSString("/Missing 12 Tf"), res)
    font = da.get_font()
    assert font is not None
    assert font.get_name() == PDType1Font.HELVETICA
    assert da.get_font_size() == pytest.approx(12.0)


def test_unknown_font_named_helvetica_falls_back_via_canonical() -> None:
    """When /DA names a Standard-14 alias (``/Helv``) and /DR lacks it,
    fall back to the canonical font (``Helvetica``) rather than the
    generic default — matches the spirit of PDFBOX-2661's "special
    mapping" idea."""
    from pypdfbox.pdmodel.font import PDType1Font  # noqa: PLC0415

    res = PDResources()
    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf"), res)
    font = da.get_font()
    assert font is not None
    assert font.get_name() == PDType1Font.HELVETICA


def test_missing_tf_operands_raises_oserror() -> None:
    res, _ = _resources_with_font()
    with pytest.raises(OSError, match="set font operator"):
        PDDefaultAppearanceString(COSString("/Helv Tf"), res)


def test_tf_with_non_name_first_operand_silently_ignored() -> None:
    res, _ = _resources_with_font()
    # ``12 14 Tf`` — both operands numeric, parser should bail out and
    # leave font_name/font unset (mirrors upstream ``return``).
    da = PDDefaultAppearanceString(COSString("12 14 Tf"), res)
    assert da.get_font() is None
    assert da.get_font_name() is None


def test_tf_with_non_number_second_operand_silently_ignored() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("/Helv /Big Tf"), res)
    assert da.get_font() is None


# ---------- parsing: colour operators ----------


def test_gray_color_one_component() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf 0.5 g"), res)
    color = da.get_font_color()
    assert color is not None
    assert color.get_color_space() is PDDeviceGray.INSTANCE
    assert color.get_components() == [pytest.approx(0.5)]


def test_rgb_color_three_components() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(
        COSString("/Helv 12 Tf 0.019 0.305 0.627 rg"), res
    )
    color = da.get_font_color()
    assert color is not None
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    components = color.get_components()
    assert components[0] == pytest.approx(0.019)
    assert components[1] == pytest.approx(0.305)
    assert components[2] == pytest.approx(0.627)


def test_cmyk_color_four_components() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(
        COSString("/Helv 12 Tf 0.1 0.2 0.3 0.4 k"), res
    )
    color = da.get_font_color()
    assert color is not None
    assert color.get_color_space() is PDDeviceCMYK.INSTANCE
    assert len(color.get_components()) == 4


def test_wrong_number_of_color_components_raises() -> None:
    res, _ = _resources_with_font()
    # Two-component non-stroking-rgb is invalid.
    with pytest.raises(OSError, match="non stroking color"):
        PDDefaultAppearanceString(
            COSString("/Helv 12 Tf 0.3 0.6 rg"), res
        )


def test_unknown_operator_silently_ignored() -> None:
    res, _ = _resources_with_font()
    # ``BT`` / ``ET`` are no-ops for the /DA parser (only Tf + colour ops
    # are recognised); the parser must not raise.
    da = PDDefaultAppearanceString(
        COSString("BT /Helv 12 Tf 0 g ET"), res
    )
    assert da.get_font_size() == pytest.approx(12.0)


# ---------- direct accessor mutation ----------


def test_set_font_name_round_trip() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf"), res)
    new_name = COSName.get_pdf_name("Cour")
    da.set_font_name(new_name)
    assert da.get_font_name() is new_name


def test_set_font_round_trip() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf"), res)
    other = _helvetica()
    da.set_font(other)
    assert da.get_font() is other


def test_set_font_size_round_trip() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf"), res)
    da.set_font_size(24.5)
    assert da.get_font_size() == pytest.approx(24.5)


def test_set_font_color_round_trip() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf"), res)
    color = PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
    da.set_font_color(color)
    assert da.get_font_color() is color


# ---------- write_to ----------


def test_write_to_emits_font_and_color() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(
        COSString("/Helv 12 Tf 0.1 0.2 0.3 rg"), res
    )
    appearance = PDAppearanceStream(COSStream())
    with PDAppearanceContentStream(appearance) as cs:
        da.write_to(cs, zero_font_size=10.0)
    body = appearance.get_stream().to_byte_array()
    assert b"Tf" in body
    assert b"rg" in body


def test_write_to_uses_zero_font_size_when_da_size_is_zero() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("/Helv 0 Tf 0 g"), res)
    appearance = PDAppearanceStream(COSStream())
    with PDAppearanceContentStream(appearance) as cs:
        da.write_to(cs, zero_font_size=18.0)
    body = appearance.get_stream().to_byte_array()
    # Auto-size fallback should emit the zero_font_size operand.
    assert b"18" in body


def test_write_to_skips_color_when_unset() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf"), res)
    appearance = PDAppearanceStream(COSStream())
    with PDAppearanceContentStream(appearance) as cs:
        da.write_to(cs, zero_font_size=10.0)
    body = appearance.get_stream().to_byte_array()
    assert b"Tf" in body
    # No colour operator emitted (no g / rg / k).
    assert b" rg" not in body
    assert b" g\n" not in body
    assert b" k\n" not in body


# ---------- copy_needed_resources_to ----------


def test_copy_needed_resources_creates_resources_if_missing() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf"), res)
    appearance = PDAppearanceStream(COSStream())
    assert appearance.get_resources() is None
    da.copy_needed_resources_to(appearance)
    assert appearance.get_resources() is not None
    assert appearance.get_resources().get_font(COSName.get_pdf_name("Helv")) is not None


def test_copy_needed_resources_preserves_existing_font() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf"), res)
    appearance = PDAppearanceStream(COSStream())
    existing_resources = PDResources()
    existing_font_dict = COSDictionary()
    existing_font_dict.set_name(COSName.get_pdf_name("Subtype"), "Type1")
    existing_font_dict.set_name(
        COSName.get_pdf_name("BaseFont"), "Times-Roman"
    )
    existing_resources.put(
        COSName.get_pdf_name("Font"),
        COSName.get_pdf_name("Helv"),
        existing_font_dict,
    )
    appearance.set_resources(existing_resources)
    da.copy_needed_resources_to(appearance)
    # Should NOT have overwritten the existing /Helv entry — its
    # BaseFont remains Times-Roman.
    sub = (
        appearance.get_resources()
        .get_cos_object()
        .get_dictionary_object(COSName.get_pdf_name("Font"))
    )
    assert isinstance(sub, COSDictionary)
    entry = sub.get_dictionary_object(COSName.get_pdf_name("Helv"))
    assert isinstance(entry, COSDictionary)
    assert entry.get_name(COSName.get_pdf_name("BaseFont")) == "Times-Roman"


def test_copy_needed_resources_no_op_when_font_name_is_none() -> None:
    res, _ = _resources_with_font()
    # Build an instance with no Tf operator parsed.
    da = PDDefaultAppearanceString(COSString("0 g"), res)
    appearance = PDAppearanceStream(COSStream())
    da.copy_needed_resources_to(appearance)
    # Resources are still created, but no font is added.
    assert appearance.get_resources() is not None


def test_copy_needed_resources_carries_color_space() -> None:
    """A /DA stream that references a named ``/ColorSpace`` via ``cs``
    or ``CS`` should have the colour space copied into the appearance
    stream's /Resources. Pypdfbox extension over upstream's
    ``// todo: other kinds of resource…`` placeholder.
    """
    from pypdfbox.cos import COSArray  # noqa: PLC0415

    res, _ = _resources_with_font()
    # Register a DeviceN-style named colour space under /MyCs.
    cs_array = COSArray()
    cs_array.add(COSName.get_pdf_name("DeviceN"))
    cs_array.add(COSArray())
    cs_array.add(COSName.get_pdf_name("DeviceCMYK"))
    res.put(
        COSName.get_pdf_name("ColorSpace"),
        COSName.get_pdf_name("MyCs"),
        cs_array,
    )

    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf /MyCs cs"), res)
    appearance = PDAppearanceStream(COSStream())
    da.copy_needed_resources_to(appearance)

    target_res = appearance.get_resources()
    assert target_res is not None
    assert target_res.has_color_space(COSName.get_pdf_name("MyCs"))


def test_copy_needed_resources_carries_ext_g_state() -> None:
    """A /DA stream that references a named ``/ExtGState`` via ``gs``
    should have the ext-gstate copied across. Pypdfbox extension."""
    res, _ = _resources_with_font()

    gs_dict = COSDictionary()
    gs_dict.set_name(COSName.get_pdf_name("Type"), "ExtGState")
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("MyGs"),
        gs_dict,
    )

    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf /MyGs gs"), res)
    appearance = PDAppearanceStream(COSStream())
    da.copy_needed_resources_to(appearance)

    target_res = appearance.get_resources()
    assert target_res is not None
    assert target_res.has_ext_g_state(COSName.get_pdf_name("MyGs"))


def test_copy_needed_resources_preserves_existing_extra_resources() -> None:
    """When the appearance stream's /Resources already carries an entry
    under the same key, the existing entry stays intact even if the
    /DR has a different value under that key."""
    res, _ = _resources_with_font()
    target_color = COSDictionary()
    target_color.set_name(COSName.get_pdf_name("Type"), "ExtGState")
    target_color.set_name(COSName.get_pdf_name("Marker"), "target-original")

    # /DR has a *different* ExtGState under /MyGs.
    dr_color = COSDictionary()
    dr_color.set_name(COSName.get_pdf_name("Type"), "ExtGState")
    dr_color.set_name(COSName.get_pdf_name("Marker"), "dr-override")
    res.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("MyGs"),
        dr_color,
    )

    appearance = PDAppearanceStream(COSStream())
    existing_resources = PDResources()
    existing_resources.put(
        COSName.get_pdf_name("ExtGState"),
        COSName.get_pdf_name("MyGs"),
        target_color,
    )
    appearance.set_resources(existing_resources)

    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf /MyGs gs"), res)
    da.copy_needed_resources_to(appearance)

    # Target entry untouched — Marker still says "target-original".
    sub = (
        appearance.get_resources()
        .get_cos_object()
        .get_dictionary_object(COSName.get_pdf_name("ExtGState"))
    )
    assert isinstance(sub, COSDictionary)
    entry = sub.get_dictionary_object(COSName.get_pdf_name("MyGs"))
    assert isinstance(entry, COSDictionary)
    assert entry.get_name(COSName.get_pdf_name("Marker")) == "target-original"


# ---------- default_appearance accessors (pypdfbox-only) ----------


def test_default_appearance_accessor_returns_source() -> None:
    res, _ = _resources_with_font()
    da_string = COSString("/Helv 12 Tf 0 g")
    da = PDDefaultAppearanceString(da_string, res)
    assert da.get_default_appearance() is da_string


def test_default_resources_accessor_returns_source() -> None:
    res, _ = _resources_with_font()
    da = PDDefaultAppearanceString(COSString("/Helv 12 Tf 0 g"), res)
    assert da.get_default_resources() is res
