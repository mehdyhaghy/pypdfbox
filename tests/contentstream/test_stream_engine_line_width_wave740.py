from __future__ import annotations

from typing import Any, cast

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.state.set_line_width import SetLineWidth
from pypdfbox.cos import COSInteger, COSString


class _NoGraphicsStateEngine:
    def get_graphics_state(self) -> None:
        return None


def test_wave740_stream_engine_to_float_returns_none_for_non_number() -> None:
    assert PDFStreamEngine._to_float(COSString(b"not a number")) is None


def test_wave740_set_line_width_skips_when_graphics_state_is_missing() -> None:
    processor = SetLineWidth()
    processor.set_context(cast(Any, _NoGraphicsStateEngine()))

    processor.process(Operator.get_operator("w"), [COSInteger.get(9)])
