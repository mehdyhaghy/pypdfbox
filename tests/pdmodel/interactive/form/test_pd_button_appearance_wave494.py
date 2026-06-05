from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
    _parse_default_appearance,
    _rect_from_cos,
)
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_AP = COSName.get_pdf_name("AP")
_AS = COSName.get_pdf_name("AS")
_DA = COSName.get_pdf_name("DA")
_DV = COSName.get_pdf_name("DV")
_KIDS = COSName.get_pdf_name("Kids")
_MK = COSName.get_pdf_name("MK")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")
_OPT = COSName.get_pdf_name("Opt")
_RECT = COSName.get_pdf_name("Rect")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray([COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)])


def _normal_appearance_with_on_state(on_value: str) -> COSDictionary:
    ap = COSDictionary()
    normal = COSDictionary()
    normal.set_item(COSName.get_pdf_name(on_value), COSStream())
    normal.set_item(_OFF, COSStream())
    ap.set_item(_N, normal)
    return ap


def _normal_body(field: object) -> bytes:
    widget_cos = field.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    return n.create_input_stream().read()


def test_button_flags_clear_mutually_exclusive_push_and_radio_wave494() -> None:
    button = PDButton(PDAcroForm())

    button.set_push_button(True)
    assert button.is_push_button() is True
    assert button.is_radio_button() is False

    button.set_radio_button(True)
    assert button.is_radio_button() is True
    assert button.is_push_button() is False


def test_button_local_value_presence_and_clear_helpers_wave494() -> None:
    button = PDButton(PDAcroForm())
    button.get_cos_object().set_item(_DV, COSString("Fallback"))
    button.get_cos_object().set_item(_OPT, COSString("Export"))

    assert button.has_value() is False
    assert button.has_default_value() is True
    assert button.has_export_values() is True
    # has_default_value detects the COSString /DV token, but get_default_value
    # mirrors upstream (only an instanceof COSName token is read) and returns
    # "" for a COSString /DV. Oracle PDFBox 3.0.7 returns "".
    assert button.get_default_value() == ""
    assert button.get_export_values() == ["Export"]

    button.set_value("Export")
    assert button.has_value() is True
    button.clear_value()
    button.clear_default_value()
    button.clear_export_values()

    assert button.has_value() is False
    assert button.has_default_value() is False
    assert button.has_export_values() is False
    assert button.get_value() == "Off"


def test_button_set_value_by_index_reports_empty_valid_range_wave494() -> None:
    button = PDButton(PDAcroForm())

    with pytest.raises(ValueError, match="valid indices are from 0 to -1"):
        button.set_value_by_index(0)


def test_button_check_value_accepts_off_and_known_state_wave494() -> None:
    button = PDButton(PDAcroForm())
    button.get_cos_object().set_item(_AP, _normal_appearance_with_on_state("Yes"))

    button.check_value("Yes")
    button.check_value("Off")

    with pytest.raises(ValueError, match="not a valid option"):
        button.check_value("Maybe")


def test_get_on_values_dedupes_export_values_wave494() -> None:
    button = PDButton(PDAcroForm())

    button.set_export_values(["A", "B", "A"])

    assert button.get_on_values() == {"A", "B"}


def test_get_on_values_walks_kid_appearances_and_skips_malformed_wave494() -> None:
    button = PDButton(PDAcroForm())
    kids = COSArray()
    kids.add(COSDictionary())
    kids.add(COSString("not-a-widget"))
    kids.add(COSDictionary())
    kids.get(2).set_item(_AP, _normal_appearance_with_on_state("Accepted"))  # type: ignore[attr-defined]
    button.get_cos_object().set_item(_KIDS, kids)

    assert button.get_on_values() == {"Accepted"}


def test_construct_appearances_falls_back_to_off_for_missing_state_wave494() -> None:
    button = PDButton(PDAcroForm())
    cos = button.get_cos_object()
    cos.set_item(_AP, _normal_appearance_with_on_state("Yes"))
    cos.set_name(COSName.get_pdf_name("V"), "Nope")

    button.construct_appearances()

    assert cos.get_name(_AS) == "Off"


def test_rect_from_cos_normalizes_reversed_coordinates_wave494() -> None:
    assert _rect_from_cos(_rect(20, 30, 5, 10)) == (5.0, 10.0, 20.0, 30.0)


def test_rect_from_cos_rejects_short_or_non_numeric_arrays_wave494() -> None:
    assert _rect_from_cos(COSArray([COSFloat(0), COSFloat(1), COSFloat(2)])) is None
    assert (
        _rect_from_cos(
            COSArray([COSFloat(0), COSFloat(1), COSString("2"), COSFloat(3)])
        )
        is None
    )


def test_parse_default_appearance_reads_rgb_and_cmyk_colors_wave494() -> None:
    assert _parse_default_appearance("/TiRo 9 Tf 0.1 0.2 0.3 rg") == (
        "TiRo",
        9.0,
        (0.1, 0.2, 0.3),
    )
    assert _parse_default_appearance("/CoRo 8 Tf 0.1 0.2 0.3 0.4 k") == (
        "CoRo",
        8.0,
        (0.1, 0.2, 0.3, 0.4),
    )


def test_appearance_support_predicate_matches_supported_public_fields_wave494() -> None:
    generator = PDAppearanceGenerator()

    assert generator.is_supported_field(PDTextField(PDAcroForm())) is True
    assert generator.is_supported_field(PDCheckBox(PDAcroForm())) is True
    assert generator.is_supported_field(PDSignatureField(PDAcroForm())) is True


def test_single_line_set_appearance_value_collapses_all_newline_classes_wave494() -> None:
    field = PDTextField(PDAcroForm())
    field.get_cos_object().set_item(_RECT, _rect(0, 0, 160, 20))
    field.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")

    PDAppearanceGenerator().set_appearance_value(
        field,
        "a\r\nb\nc\u000bd\u000ce\rf\u0085g\u2028h\u2029i",
    )

    assert field.get_value() == "a b c d e f g h i"
    assert b"a b c d e f g h i" in _normal_body(field)


def test_push_button_invalid_mk_color_arrays_are_ignored_wave494() -> None:
    button = PDPushButton(PDAcroForm())
    cos = button.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 30))
    mk = COSDictionary()
    mk.set_string(COSName.get_pdf_name("CA"), "Submit")
    mk.set_item(COSName.get_pdf_name("BG"), COSArray([COSFloat(0.1), COSFloat(0.2)]))
    mk.set_item(
        COSName.get_pdf_name("BC"),
        COSArray([COSFloat(0.1), COSString("bad"), COSFloat(0.3)]),
    )
    cos.set_item(_MK, mk)

    PDAppearanceGenerator().generate(button)

    body = _normal_body(button)
    assert b"Submit" in body
    assert b" rg" not in body
    assert b" RG" not in body


def test_unsigned_signature_renders_placeholder_and_resets_dash_wave494() -> None:
    field = PDSignatureField(PDAcroForm())
    field.get_cos_object().set_item(_RECT, _rect(0, 0, 160, 40))

    PDAppearanceGenerator().generate(field)

    body = _normal_body(field)
    assert b"[3 3] 0 d" in body
    assert b"[] 0 d" in body
    # Wave 1374 — placeholder updated to "Click to sign".
    assert b"Click to sign" in body


def test_radio_dot_zero_radius_writes_no_path_ops_wave494() -> None:
    stream = COSStream()
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
        PDAppearanceContentStream,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
        PDAppearanceStream,
    )

    appearance = PDAppearanceStream(stream)
    with PDAppearanceContentStream(appearance) as raw_cs:
        PDAppearanceGenerator()._draw_radio_dot(raw_cs, 0.0, 10.0)  # type: ignore[arg-type]

    body = stream.create_input_stream().read()
    assert b" m\n" not in body
    assert b" c\n" not in body


def test_auto_size_clamps_to_minimum_and_maximum_wave494() -> None:
    assert PDAppearanceGenerator._auto_size(1.0) == 4.0
    assert PDAppearanceGenerator._auto_size(100.0) == 12.0
    assert PDAppearanceGenerator._auto_size(10.0) == 7.0


def test_color_array_to_tuple_rejects_empty_and_accepts_integers_wave494() -> None:
    assert PDAppearanceGenerator._color_array_to_tuple(COSArray()) is None
    assert PDAppearanceGenerator._color_array_to_tuple(
        COSArray([COSInteger(1), COSInteger(0), COSInteger(1)])
    ) == (1.0, 0.0, 1.0)
