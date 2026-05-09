from __future__ import annotations

import pytest

from tests.pdfparser.test_cos_parser_wave673 import _FailingHandler, _parser


def test_wave1007_parser_helper_builds_cos_parser_with_buffer() -> None:
    parser = _parser(b"%PDF-")

    assert parser.get_file_len() == 5


def test_wave1007_failing_handler_raises_when_called_directly() -> None:
    with pytest.raises(AssertionError, match="skip-encryption streams"):
        _FailingHandler().decrypt_stream(b"plain", 10, 0)
