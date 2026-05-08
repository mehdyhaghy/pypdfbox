from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.multipdf.pdf_merger_utility import SourceLike


@pytest.mark.parametrize(
    "source",
    [
        "input.pdf",
        Path("input.pdf"),
        b"%PDF-1.7\n",
        bytearray(b"%PDF-1.7\n"),
        memoryview(b"%PDF-1.7\n"),
        io.BytesIO(b"%PDF-1.7\n"),
    ],
)
def test_add_sources_wave300_rejects_single_source_like_inputs(source: object) -> None:
    util = PDFMergerUtility()

    with pytest.raises(TypeError, match=r"add_sources expected an iterable"):
        util.add_sources(source)  # type: ignore[arg-type]

    assert util.get_sources() == []


def test_add_sources_wave300_still_accepts_iterable_of_sources() -> None:
    util = PDFMergerUtility()
    sources: list[SourceLike] = [b"%PDF-1.7\n", memoryview(b"%PDF-1.7\n")]

    util.add_sources(sources)

    assert util.get_sources() == sources
