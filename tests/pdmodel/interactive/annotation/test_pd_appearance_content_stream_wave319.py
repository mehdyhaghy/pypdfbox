from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)


def _new_appearance() -> PDAppearanceStream:
    return PDAppearanceStream(COSStream())


def test_wave319_invalid_stroking_color_count_writes_no_operands() -> None:
    appearance = _new_appearance()

    with PDAppearanceContentStream(appearance) as content:
        content.set_stroking_color([0.25, 0.75])

    assert appearance.get_stream().to_byte_array() == b""


def test_wave319_invalid_non_stroking_color_count_writes_no_operands() -> None:
    appearance = _new_appearance()

    with PDAppearanceContentStream(appearance) as content:
        content.set_non_stroking_color([0.1, 0.2, 0.3, 0.4, 0.5])

    assert appearance.get_stream().to_byte_array() == b""
