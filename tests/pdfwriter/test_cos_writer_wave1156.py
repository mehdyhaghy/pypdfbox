from __future__ import annotations

from typing import Any

import pytest

from tests.pdfwriter import test_cos_writer_wave395 as wave395_tests


def test_wave1156_bad_pddocument_fake_is_encrypted_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class WriterCallingIsEncrypted:
        def __init__(self, output: object) -> None:
            self.output = output

        def __enter__(self) -> WriterCallingIsEncrypted:
            return self

        def __exit__(self, *exc_info: Any) -> None:
            return None

        def write(self, document: object) -> None:
            assert document.is_encrypted() is False
            raise TypeError("did not return a COSDocument")

    monkeypatch.setattr(wave395_tests, "COSWriter", WriterCallingIsEncrypted)

    wave395_tests.test_wave395_write_with_bad_pddocument_get_document_type_raises()
