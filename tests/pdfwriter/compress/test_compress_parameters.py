"""Hand-written parity tests for :class:`CompressParameters`.

Exercises the full public surface mirrored from
``org.apache.pdfbox.pdfwriter.compress.CompressParameters`` (PDFBox
3.0.x): the two pre-built singletons, the default object-stream size
constant, the size getter, the ``is_compress`` predicate, and the
negative-size validation.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdfwriter import CompressParameters
from pypdfbox.pdfwriter.compress import CompressParameters as CP_FromCompress
from pypdfbox.pdfwriter.compress.compress_parameters import (
    CompressParameters as CP_FromModule,
)


def test_class_is_re_exported_consistently() -> None:
    assert CompressParameters is CP_FromCompress
    assert CompressParameters is CP_FromModule


def test_default_object_stream_size_constant() -> None:
    # Upstream pins this at 200; downstream consumers depend on it.
    assert CompressParameters.DEFAULT_OBJECT_STREAM_SIZE == 200


def test_default_constructor_uses_default_size() -> None:
    params = CompressParameters()
    assert params.get_object_stream_size() == 200
    assert params.is_compress() is True


def test_explicit_size_is_round_trippable() -> None:
    for size in (1, 50, 200, 1024):
        params = CompressParameters(size)
        assert params.get_object_stream_size() == size
        assert params.is_compress() is True


def test_zero_disables_compression() -> None:
    params = CompressParameters(0)
    assert params.get_object_stream_size() == 0
    assert params.is_compress() is False


def test_negative_size_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        CompressParameters(-1)


def test_default_compression_singleton_matches_default_constructor() -> None:
    assert (
        CompressParameters.DEFAULT_COMPRESSION.get_object_stream_size()
        == CompressParameters.DEFAULT_OBJECT_STREAM_SIZE
    )
    assert CompressParameters.DEFAULT_COMPRESSION.is_compress() is True


def test_no_compression_singleton_disables_compression() -> None:
    assert CompressParameters.NO_COMPRESSION.get_object_stream_size() == 0
    assert CompressParameters.NO_COMPRESSION.is_compress() is False


def test_singletons_are_independent_instances() -> None:
    # Upstream constructs them as separate ``new`` instances; mutation of
    # one (if a future field is added) must not bleed into the other.
    assert (
        CompressParameters.DEFAULT_COMPRESSION
        is not CompressParameters.NO_COMPRESSION
    )
