"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/COSObjectKeyTest.java
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSObjectKey


def test_input_values() -> None:
    with pytest.raises(ValueError):
        COSObjectKey(-1, 0)
    with pytest.raises(ValueError):
        COSObjectKey(1, -1)


def _cmp(a: COSObjectKey, b: COSObjectKey) -> int:
    if a == b:
        return 0
    return -1 if a < b else 1


def test_compare_to_input_not_null_output_zero() -> None:
    object_under_test = COSObjectKey(1, 0)
    other = COSObjectKey(1, 0)
    assert _cmp(object_under_test, other) == 0


def test_compare_to_input_not_null_output_not_null() -> None:
    object_under_test = COSObjectKey(1, 0)
    other = COSObjectKey(9_999_999, 0)
    assert _cmp(object_under_test, other) == -1
    assert _cmp(other, object_under_test) == 1


def test_equals() -> None:
    assert COSObjectKey(100, 0) == COSObjectKey(100, 0)
    assert COSObjectKey(100, 0) != COSObjectKey(101, 0)


def test_internal_representation() -> None:
    key = COSObjectKey(100, 0)
    assert key.object_number == 100
    assert key.generation_number == 0

    key = COSObjectKey(200, 4)
    assert key.object_number == 200
    assert key.generation_number == 4

    key = COSObjectKey(200000, 0)
    assert key.object_number == 200000
    assert key.generation_number == 0

    key = COSObjectKey(87654321, 123)
    assert key.object_number == 87654321
    assert key.generation_number == 123


def test_sorting_order() -> None:
    # Comparison is done on the object number first, then the generation.
    key40 = COSObjectKey(4, 0)
    key41 = COSObjectKey(4, 1)
    key50 = COSObjectKey(5, 0)

    assert _cmp(key40, key40) == 0
    assert _cmp(key41, key41) == 0
    assert _cmp(key40, key41) == -1
    assert _cmp(key40, key50) == -1
    assert _cmp(key41, key50) == -1


def test_check_hash_code() -> None:
    # Same numbers => same hash.
    assert hash(COSObjectKey(100, 0)) == hash(COSObjectKey(100, 0))
    # Different object numbers / same generation => different hash.
    assert hash(COSObjectKey(100, 0)) != hash(COSObjectKey(200, 0))
    # Same arithmetic sum but different (number, generation) => different hash.
    assert hash(COSObjectKey(100, 0)) != hash(COSObjectKey(99, 1))


# Upstream: testPDFBox5742 — Splitter + PDFRenderer are ported; the
# blocker is the PDFBOX-5742.pdf binary fixture which lives in the
# upstream Jira attachment cache and is not bundled in pypdfbox's
# ``corpus/`` set yet.
@pytest.mark.skip(
    reason="PDFBOX-5742.pdf fixture not bundled; Splitter/PDFRenderer ports are ready"
)
def test_pdfbox5742() -> None:
    pass
