from __future__ import annotations

import pytest

from tests.pdfwriter import test_cos_writer_xref_entry as xref_entry_tests


def test_wave1155_frozen_immutable_assertion_path(monkeypatch: pytest.MonkeyPatch) -> None:
    class MutableEntry:
        def __init__(self, *, offset: int, key: object) -> None:
            self.offset = offset
            self.key = key

    monkeypatch.setattr(xref_entry_tests, "COSWriterXRefEntry", MutableEntry)

    with pytest.raises(AssertionError, match="expected frozen dataclass"):
        xref_entry_tests.test_frozen_immutable()
