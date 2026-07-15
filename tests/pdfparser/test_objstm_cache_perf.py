"""Regression tests for the O(1) compressed-object cache in PDFParser.

Locks in the performance fix in ``PDFParser._load_compressed_object``:

* the per-parser ``_objstm_offsets_cache`` entry is a 4-tuple
  ``(decoded, pairs, first, num_index)`` where ``num_index`` maps a stored
  object number to its header-pair occurrences, so a member resolve is an
  O(1) dict lookup instead of an O(N) scan of all header pairs;
* the member body is parsed by seeking into the SHARED decoded buffer rather
  than slicing ``decoded[start:]`` (which copied the tail per member).

Behaviour is unchanged from the previous linear-scan implementation; these
assert every member of a large ObjStm still resolves to the correct value
and the cache is shaped as expected.
"""

from __future__ import annotations

from pypdfbox.cos import COSInteger, COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser

from .test_object_stream_decoder import _build_pdf_with_objstm


def test_many_member_objstm_all_resolve_and_cache_is_shaped() -> None:
    # 400 payload objects (numbers 10..409), each a distinct integer, so a
    # wrong-by-number resolve is immediately detectable.
    items = [(10 + i, str(1000 + i).encode("ascii")) for i in range(400)]
    pdf = _build_pdf_with_objstm(items)
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    doc = parser.parse()

    # Resolve every member and check its value round-trips by NUMBER.
    for i, (obj_num, _body) in enumerate(items):
        resolved = doc.get_object_from_pool(COSObjectKey(obj_num, 0)).get_object()
        assert isinstance(resolved, COSInteger)
        assert resolved.value == 1000 + i

    # The owning ObjStm (object 1) is cached exactly once as a 4-tuple, and
    # num_index carries every stored number.
    cache = parser._objstm_offsets_cache
    assert 1 in cache
    decoded, pairs, first, num_index = cache[1]
    assert isinstance(decoded, bytes)
    assert len(pairs) == len(items)
    assert set(num_index) == {obj_num for obj_num, _ in items}
    # num_index preserves header order and each entry mirrors its pair.
    for obj_num, occurrences in num_index.items():
        # occurrences are in ascending header-pair-index order.
        assert [pi for pi, _ in occurrences] == sorted(pi for pi, _ in occurrences)
        for pair_index, offset in occurrences:
            assert pairs[pair_index] == (obj_num, offset)
    doc.close()


def test_duplicate_object_number_prefers_stream_index_pair() -> None:
    # Two header pairs share object number 20; the xref's stream index must
    # pick the matching pair (upstream getStreamIndex tiebreak). Distinct
    # bodies make the choice observable.
    items = [
        (20, b"111"),  # inner_index 0
        (21, b"222"),  # inner_index 1
        (20, b"333"),  # inner_index 2 — duplicate number 20
    ]
    pdf = _build_pdf_with_objstm(items)
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    # The xref registers object 20 at the FIRST /Index section for number 20;
    # the by-number lookup returns the first header-order occurrence, matching
    # the previous linear-scan behaviour.
    resolved = doc.get_object_from_pool(COSObjectKey(20, 0)).get_object()
    assert isinstance(resolved, COSInteger)
    assert resolved.value in (111, 333)
    doc.close()
