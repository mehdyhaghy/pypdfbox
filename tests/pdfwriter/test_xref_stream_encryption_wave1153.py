from __future__ import annotations

import pytest

from pypdfbox.pdfwriter.cos_writer import COSWriter
from tests.pdfwriter import test_xref_stream_encryption as xref_stream_encryption_tests


def test_xref_stream_round_trip_skip_branch_when_writer_surface_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(COSWriter, "_do_write_xref_stream", raising=False)
    monkeypatch.delattr(COSWriter, "write_xref_stream", raising=False)
    monkeypatch.delattr(COSWriter, "_write_xref_stream", raising=False)

    with pytest.raises(pytest.skip.Exception, match="xref-stream output deferred"):
        xref_stream_encryption_tests.test_xref_stream_encrypt_on_write_round_trip()
