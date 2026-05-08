from __future__ import annotations

import io

import pytest

from pypdfbox.pdfwriter import COSWriter


def test_wave311_set_startxref_rejects_bool() -> None:
    with COSWriter(io.BytesIO()) as writer, pytest.raises(ValueError):
        writer.set_startxref(True)


def test_wave311_set_pdf_version_rejects_bool_components() -> None:
    with COSWriter(io.BytesIO()) as writer:
        with pytest.raises(TypeError):
            writer.set_pdf_version(True, 7)
        with pytest.raises(TypeError):
            writer.set_pdf_version(1, False)
