from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
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


def test_wave776_content_stream_close_is_idempotent() -> None:
    appearance = PDAppearanceStream(COSStream())
    content = PDAppearanceContentStream(appearance)

    content.close()
    content.close()

    assert appearance.get_stream().to_byte_array() == b""


def test_wave776_non_stroking_color_on_demand_empty_components_returns_false() -> None:
    appearance = PDAppearanceStream(COSStream())
    content = PDAppearanceContentStream(appearance)

    assert content.set_non_stroking_color_on_demand(PDColor([], PDPattern())) is False

    content.close()
    assert appearance.get_stream().to_byte_array() == b""


def test_wave776_empty_appearance_entry_has_no_stream_or_cos_object() -> None:
    entry = PDAppearanceEntry()

    assert entry.get_appearance_stream() is None
    with pytest.raises(ValueError, match="no underlying COS object"):
        entry.get_cos_object()


def test_wave776_appearance_stream_resources_self_reference_returns_empty() -> None:
    stream = COSStream()
    stream.set_item(
        COSName.get_pdf_name("Resources"),
        COSName.get_pdf_name("SelfReference"),
    )

    resources = PDAppearanceStream(stream).get_resources()

    assert resources is not None
    assert isinstance(resources.get_cos_object(), COSDictionary)
    assert len(resources.get_cos_object()) == 0


def test_wave776_appearance_stream_set_resources_none_clears_entry() -> None:
    appearance = PDAppearanceStream(COSStream())
    appearance.set_resources(COSDictionary())

    appearance.set_resources(None)

    assert appearance.get_resources() is None
    assert not appearance.get_cos_object().contains_key(COSName.get_pdf_name("Resources"))


def test_wave776_appearance_stream_malformed_matrix_entry_returns_identity() -> None:
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
                COSFloat(12.0),
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


def test_wave776_appearance_dictionary_accepts_raw_cos_entries() -> None:
    appearance = PDAppearanceDictionary(COSDictionary())
    normal_stream = COSStream()
    rollover_dict = COSDictionary()

    appearance.set_normal_appearance(normal_stream)
    appearance.set_rollover_appearance(rollover_dict)

    normal = appearance.get_normal_appearance()
    rollover = appearance.get_rollover_appearance()
    assert normal is not None
    assert normal.get_cos_object() is normal_stream
    assert rollover is not None
    assert rollover.get_cos_object() is rollover_dict
