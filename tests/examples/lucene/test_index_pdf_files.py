"""Tests for ``pypdfbox.examples.lucene.index_pdf_files``."""
from __future__ import annotations

import pytest

from pypdfbox.examples.lucene.index_pdf_files import IndexPDFFiles


def test_constructor_is_private_like() -> None:
    with pytest.raises(RuntimeError):
        IndexPDFFiles()


def test_main_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        IndexPDFFiles.main([])


def test_index_docs_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        IndexPDFFiles.index_docs(object(), "/tmp")
