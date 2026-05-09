from __future__ import annotations

import pytest

from tests.pdfwriter import test_content_stream_writer_tail_wave782 as wave782


def test_wave1157_unknown_cos_accept_cleanup_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def write_token_and_raise(self: object, token: object) -> None:
        token.accept(object())  # type: ignore[attr-defined]
        raise OSError("Unknown type")

    monkeypatch.setattr(wave782.ContentStreamWriter, "write_token", write_token_and_raise)

    wave782.test_wave782_unknown_cosbase_subclass_raises_ioerror()
