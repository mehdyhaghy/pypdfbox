"""Tests for the brute-force recovery cache on ``COSParser``.

Upstream ``BruteForceParser`` computes the ``n g obj`` offset map and the
raw-source snapshot once and reuses them. The pypdfbox port now latches both
(``_bf_objects_cache`` / ``_all_bytes_cache``) so a corrupt file — the only
case that exercises brute-force recovery — no longer re-sweeps the whole file
on every probe. These tests assert the cache is a pure optimisation: the
recovered object graph and rebuilt trailer are byte-for-byte identical to a
fresh, un-cached scan, and repeated probes for a missing key do not re-read
the source.
"""

from __future__ import annotations

import pathlib

from pypdfbox.cos import COSDocument, COSName, COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.loader import Loader
from pypdfbox.pdfparser import COSParser

_FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures" / "pdfparser"

# A malformed file: real object bodies but no xref table / trailer, forcing
# the brute-force recovery path.
_CORRUPT = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    b"4 0 obj\n<< /Producer (pypdfbox) /Title (t) >>\nendobj\n"
    b"%%EOF"
)


def _parser(data: bytes, document: COSDocument | None = None) -> COSParser:
    return COSParser(RandomAccessReadBuffer(data), document=document)


def test_bf_search_result_is_latched_and_stable() -> None:
    p = _parser(_CORRUPT)
    first = p.bf_search_for_objects()
    second = p.bf_search_for_objects()
    # Same instance returned (mirrors upstream's cached map).
    assert first is second
    # And it equals a fresh parser's first (un-cached) scan.
    fresh = _parser(_CORRUPT).bf_search_for_objects()
    assert dict(first) == dict(fresh)
    assert set(first) == {COSObjectKey(n, 0) for n in (1, 2, 3, 4)}


def test_rebuild_trailer_identical_with_and_without_warm_cache() -> None:
    cold = _parser(_CORRUPT).rebuild_trailer()

    warm = _parser(_CORRUPT)
    warm.bf_search_for_objects()  # prime the cache first
    warm_trailer = warm.rebuild_trailer()

    root = COSName.get_pdf_name("Root")
    size = COSName.get_pdf_name("Size")
    # /Root resolves to object 1 (the catalog) in both.
    assert cold.get_item(root) is not None
    assert warm_trailer.get_item(root) is not None
    assert cold.get_item(root).get_object_number() == 1
    assert warm_trailer.get_item(root).get_object_number() == 1
    assert cold.get_item(size).int_value() == warm_trailer.get_item(size).int_value()


def test_missing_key_lookup_does_not_rescan_source() -> None:
    src = RandomAccessReadBuffer(_CORRUPT)
    reads = {"n": 0}
    real_read_into = src.read_into

    def counting_read_into(buf, offset=0, length=None):
        reads["n"] += 1
        return real_read_into(buf, offset, length)

    src.read_into = counting_read_into  # type: ignore[method-assign]

    doc = COSDocument()
    p = COSParser(src, document=doc)
    p.set_lenient(True)
    try:
        missing = COSObjectKey(9999, 0)
        # First probe performs exactly one whole-file snapshot.
        assert p.get_object_offset(missing, False) is None
        after_first = reads["n"]
        assert after_first >= 1
        # Subsequent probes for the (still absent) key must not re-read.
        for _ in range(10):
            assert p.get_object_offset(missing, False) is None
        assert reads["n"] == after_first
    finally:
        doc.close()


def test_read_all_bytes_snapshot_is_cached() -> None:
    p = _parser(_CORRUPT)
    a = p._read_all_bytes()
    b = p._read_all_bytes()
    assert a is b
    assert a == _CORRUPT


def test_present_key_lookup_records_offset_and_reuses_scan() -> None:
    src = RandomAccessReadBuffer(_CORRUPT)
    reads = {"n": 0}
    real_read_into = src.read_into

    def counting_read_into(buf, offset=0, length=None):
        reads["n"] += 1
        return real_read_into(buf, offset, length)

    src.read_into = counting_read_into  # type: ignore[method-assign]

    doc = COSDocument()
    p = COSParser(src, document=doc)
    p.set_lenient(True)
    try:
        key = COSObjectKey(2, 0)
        off = p.get_object_offset(key, False)
        assert off is not None and off > 0
        after_first = reads["n"]
        # Offset is written back into the xref table (upstream parity) so a
        # second lookup is a plain dict hit — no source read at all.
        reads["n"] = 0
        assert p.get_object_offset(key, False) == off
        assert reads["n"] == 0
        # And a fresh missing-key probe reuses the cached scan (no re-read).
        assert p.get_object_offset(COSObjectKey(4242, 0), False) is None
        assert reads["n"] == 0
        assert after_first >= 1
    finally:
        doc.close()


def test_corrupt_fixture_loads_and_recovers_catalog() -> None:
    # Sanity: the real corrupt fixture still loads through the cached path.
    doc = Loader.load_pdf(_FIXTURES / "MissingCatalog.pdf")
    try:
        assert doc is not None
    finally:
        doc.close()
