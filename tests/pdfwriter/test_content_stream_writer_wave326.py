from __future__ import annotations

import io

from pypdfbox.contentstream import Operator, OperatorName
from pypdfbox.cos import COSInteger
from pypdfbox.pdfwriter import ContentStreamWriter


def test_wave326_write_token_camel_case_alias_matches_snake_case() -> None:
    sink = io.BytesIO()

    ContentStreamWriter(sink).writeToken(COSInteger.get(326))

    assert sink.getvalue() == b"326 "


def test_wave326_write_tokens_camel_case_varargs_appends_newline() -> None:
    sink = io.BytesIO()

    ContentStreamWriter(sink).writeTokens(
        COSInteger.get(3),
        COSInteger.get(26),
    )

    assert sink.getvalue() == b"3 26 \n"


def test_wave326_write_tokens_camel_case_list_uses_list_overload() -> None:
    sink = io.BytesIO()

    ContentStreamWriter(sink).writeTokens(
        [
            COSInteger.get(326),
            Operator.get_operator(OperatorName.BEGIN_TEXT),
        ]
    )

    assert sink.getvalue() == b"326 BT\n"
