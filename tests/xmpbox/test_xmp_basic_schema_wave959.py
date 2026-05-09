from __future__ import annotations

import pytest

import tests.xmpbox.upstream.test_xmp_basic_schema as basic_schema


def test_wave959_thumbnail_sample_requires_metadata() -> None:
    with pytest.raises(ValueError, match="metadata is required"):
        basic_schema._sample_value("Thumbnail")
