"""Wave 1275 parity test for COSDocument.get_stream_cache."""

from __future__ import annotations

import contextlib

from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.io import ScratchFile


def test_get_stream_cache_returns_scratch_file_instance() -> None:
    scratch = ScratchFile()
    try:
        doc = COSDocument(scratch_file=scratch)
        try:
            cache = doc.get_stream_cache()
            assert cache is scratch
            # Equivalent to the existing property accessor.
            assert cache is doc.scratch_file
        finally:
            doc.close()
    finally:
        with contextlib.suppress(ValueError):
            scratch.close()


def test_get_stream_cache_default_owns_scratch() -> None:
    doc = COSDocument()
    try:
        cache = doc.get_stream_cache()
        assert isinstance(cache, ScratchFile)
    finally:
        doc.close()
