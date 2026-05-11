"""Wave 1281: PDFXRefStream writer port."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDocument, COSName, COSObjectKey, COSStream
from pypdfbox.pdfparser import PDFXRefStream
from pypdfbox.pdfparser.xref import NormalXReference


def test_get_stream_requires_size() -> None:
    xs = PDFXRefStream(COSDocument())
    with pytest.raises(ValueError):
        xs.get_stream()


def test_add_entry_deduplicates_by_object_number() -> None:
    xs = PDFXRefStream(COSDocument())
    a = NormalXReference(100, COSObjectKey(5, 0), COSStream())
    b = NormalXReference(200, COSObjectKey(5, 0), COSStream())
    xs.add_entry(a)
    xs.add_entry(b)
    assert xs._stream_data == [a]  # type: ignore[attr-defined]


def test_index_entry_always_starts_at_zero() -> None:
    xs = PDFXRefStream(COSDocument())
    entries = xs._get_index_entry()  # type: ignore[attr-defined]
    # No entries added → ``{0}`` is still in the set → one (0, 1) range.
    assert entries == [0, 1]


def test_get_stream_writes_xref_type_and_size() -> None:
    doc = COSDocument()
    xs = PDFXRefStream(doc)
    xs.set_size(10)
    entry = NormalXReference(50, COSObjectKey(1, 0), COSStream())
    xs.add_entry(entry)
    stream = xs.get_stream()
    assert stream.get_cos_name(COSName.TYPE) == COSName.XREF
    assert stream.get_long(COSName.SIZE) == 10


def test_w_entry_uses_minimal_widths() -> None:
    xs = PDFXRefStream(COSDocument())
    # Two entries: small and larger byte offset to exercise width sizing.
    xs.add_entry(NormalXReference(255, COSObjectKey(1, 0), COSStream()))
    xs.add_entry(
        NormalXReference(70000, COSObjectKey(2, 0), COSStream())
    )
    widths = xs._get_w_entry()  # type: ignore[attr-defined]
    assert widths[0] == 1  # type=1 fits in one byte
    assert widths[1] >= 3  # 70000 needs 3 bytes
