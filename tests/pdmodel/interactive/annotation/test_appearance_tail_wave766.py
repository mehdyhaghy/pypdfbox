from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_entry import (
    PDAppearanceEntry,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_line_info import PDLineInfo


def test_wave766_appearance_stream_resources_present_but_not_dict_returns_empty() -> None:
    stream = COSStream()
    stream.set_item(COSName.RESOURCES, COSName.get_pdf_name("SelfReference"))  # type: ignore[attr-defined]

    resources = PDAppearanceStream(stream).get_resources()

    assert resources is not None
    assert isinstance(resources.get_cos_object(), COSDictionary)
    assert len(resources.get_cos_object()) == 0


def test_wave766_appearance_stream_set_resources_none_clears_entry() -> None:
    appearance = PDAppearanceStream(COSStream())
    appearance.set_resources(COSDictionary())

    appearance.set_resources(None)

    assert appearance.get_resources() is None
    assert not appearance.get_cos_object().contains_key(COSName.RESOURCES)  # type: ignore[attr-defined]


def test_wave766_appearance_stream_matrix_malformed_entry_returns_identity() -> None:
    stream = COSStream()
    stream.set_item(
        COSName.get_pdf_name("Matrix"),
        COSArray(
            [
                COSFloat(1.0),
                COSFloat(0.0),
                COSFloat(0.0),
                COSFloat(1.0),
                COSName.get_pdf_name("Bad"),
                COSFloat(10.0),
            ]
        ),
    )

    assert PDAppearanceStream(stream).get_matrix() == [
        1.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
    ]


def test_wave766_appearance_dictionary_accepts_raw_cos_entries() -> None:
    appearance = PDAppearanceDictionary(COSDictionary())
    stream = COSStream()
    subdict = COSDictionary()

    appearance.set_normal_appearance(stream)
    appearance.set_rollover_appearance(subdict)

    normal = appearance.get_normal_appearance()
    rollover = appearance.get_rollover_appearance()
    assert normal is not None
    assert normal.get_cos_object() is stream
    assert rollover is not None
    assert rollover.get_cos_object() is subdict


def test_wave766_appearance_dictionary_rejects_invalid_entry_type() -> None:
    appearance = PDAppearanceDictionary(COSDictionary())

    with pytest.raises(TypeError, match="appearance entry"):
        appearance.set_down_appearance(42)  # type: ignore[arg-type]


class _NegativeModuloInt(int):
    def __mod__(self, other: object) -> int:
        if other == 90:
            return 0
        if other == 360:
            return -90
        return super().__mod__(other)  # type: ignore[arg-type]


def test_wave766_normalized_rotation_defensively_handles_negative_modulo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mk = PDAppearanceCharacteristicsDictionary()

    def fake_get_rotation() -> int:
        return _NegativeModuloInt(0)

    monkeypatch.setattr(mk, "get_rotation", fake_get_rotation)

    assert mk.get_normalized_rotation() == 270


def test_wave766_rollover_and_alternate_icon_form_absent_returns_none() -> None:
    mk = PDAppearanceCharacteristicsDictionary()

    assert mk.get_rollover_icon_form() is None
    assert mk.get_alternate_icon_form() is None


def test_wave766_appearance_entry_without_underlying_object() -> None:
    entry = PDAppearanceEntry()

    with pytest.raises(ValueError, match="no underlying COS object"):
        entry.get_cos_object()
    assert entry.get_appearance_stream() is None


def test_wave766_appearance_content_stream_close_is_idempotent() -> None:
    appearance = PDAppearanceStream(COSStream())
    content = PDAppearanceContentStream(appearance)
    content.move_to(1, 2)

    content.close()
    first_body = appearance.get_stream().to_byte_array()
    content.close()

    assert appearance.get_stream().to_byte_array() == first_body


def test_wave766_non_stroking_color_on_demand_with_empty_components_returns_false() -> None:
    appearance = PDAppearanceStream(COSStream())
    content = PDAppearanceContentStream(appearance)

    assert content.set_non_stroking_color_on_demand(PDColor([], PDPattern())) is False
    content.close()
    assert appearance.get_stream().to_byte_array() == b""


def test_wave766_line_info_pads_short_array_and_defaults_non_numeric_entries() -> None:
    raw = COSArray([COSName.get_pdf_name("Bad")])

    line = PDLineInfo(raw)

    assert raw.size() == 4
    assert line.get_start() == (0.0, 0.0)
    assert line.get_end() == (0.0, 0.0)


def test_wave766_appearance_dictionary_rejects_non_dictionary_constructor() -> None:
    with pytest.raises(TypeError, match="COSDictionary"):
        PDAppearanceDictionary(object())  # type: ignore[arg-type]
