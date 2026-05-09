from __future__ import annotations

import pytest

from pypdfbox.pdfwriter.content_stream_writer import ContentStreamWriter
from tests.pdfwriter import test_writer_remaining_wave759 as writer_remaining_tests


def test_unknown_cosbase_test_helper_accept_path_is_executed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def call_accept_then_raise(self: ContentStreamWriter, token: object) -> None:
        del self
        token.accept(None)  # type: ignore[attr-defined]
        raise OSError("Unknown type")

    monkeypatch.setattr(ContentStreamWriter, "write_token", call_accept_then_raise)

    writer_remaining_tests.test_content_stream_unknown_cosbase_subclass_raises()
