"""The object pool is stored by packed ``num << 16 | gen``; the public
key-based API must behave exactly as a ``COSObjectKey``-keyed dict."""

from pypdfbox.cos import COSDictionary, COSInteger, COSObjectKey
from pypdfbox.cos.cos_document import COSDocument


def test_lookup_with_equal_fresh_key_returns_same_object() -> None:
    with COSDocument() as doc:
        first = doc.get_object_from_pool(COSObjectKey(5, 2))
        assert doc.get_object_from_pool(COSObjectKey(5, 2)) is first
        assert doc.get_object(COSObjectKey(5, 2)) is first
        assert doc.has_object(COSObjectKey(5, 2))
        assert not doc.has_object(COSObjectKey(5, 3))
        assert doc.get_object(COSObjectKey(6, 2)) is None


def test_by_number_path_shares_pool_entries() -> None:
    with COSDocument() as doc:
        via_key = doc.get_object_from_pool(COSObjectKey(9, 0))
        assert doc._get_object_from_pool_by_number(9, 0) is via_key
        via_number = doc._get_object_from_pool_by_number(10, 1)
        assert doc.get_object_from_pool(COSObjectKey(10, 1)) is via_number
        assert via_number.object_number == 10
        assert via_number.generation_number == 1
        assert doc.get_object_keys() == [COSObjectKey(9, 0), COSObjectKey(10, 1)]


def test_keys_keep_first_instance_and_insertion_order() -> None:
    with COSDocument() as doc:
        k3 = COSObjectKey(3, 0, 7)
        k1 = COSObjectKey(1, 0)
        doc.get_object_from_pool(k3)
        doc.get_object_from_pool(k1)
        doc.get_object_from_pool(COSObjectKey(3, 0))  # equal key: no new entry
        keys = doc.get_object_keys()
        assert keys == [k3, k1]
        assert keys[0] is k3
        assert keys[0].get_stream_index() == 7
        assert [o.object_number for o in doc.get_objects()] == [3, 1]


def test_remove_then_recreate_appends_at_end() -> None:
    with COSDocument() as doc:
        a = doc.get_object_from_pool(COSObjectKey(1, 0))
        doc.get_object_from_pool(COSObjectKey(2, 0))
        assert doc.remove_object(COSObjectKey(1, 0)) is a
        assert doc.remove_object(COSObjectKey(1, 0)) is None
        assert not doc.has_object(COSObjectKey(1, 0))
        again = doc.get_object_from_pool(COSObjectKey(1, 0))
        assert again is not a
        assert doc.get_object_keys() == [COSObjectKey(2, 0), COSObjectKey(1, 0)]


def test_get_key_returns_stored_key_instance() -> None:
    with COSDocument() as doc:
        key = COSObjectKey(4, 0)
        holder = doc.get_object_from_pool(key)
        body = COSDictionary()
        holder.set_object(body)
        assert doc.get_key(body) is key
        assert doc.get_key(holder) is key
        assert doc.get_key(COSDictionary()) is None


def test_non_key_arguments_behave_like_missing_keys() -> None:
    with COSDocument() as doc:
        assert doc.get_object_from_pool(None) is None  # type: ignore[arg-type]
        assert doc.get_object(None) is None  # type: ignore[arg-type]
        assert not doc.has_object(None)  # type: ignore[arg-type]
        assert doc.remove_object(None) is None  # type: ignore[arg-type]
        assert not doc.has_object(COSInteger.get(1))  # type: ignore[arg-type]


def test_add_xref_table_pools_keys_and_keeps_order() -> None:
    with COSDocument() as doc:
        k2, k1 = COSObjectKey(2, 0), COSObjectKey(1, 0)
        doc.get_object_from_pool(COSObjectKey(1, 0))
        doc.add_xref_table({k2: 200, k1: 100})
        assert list(doc.get_xref_table().items()) == [(k2, 200), (k1, 100)]
        assert doc.get_object_keys() == [COSObjectKey(1, 0), k2]
        doc.add_xref_table({None: 5, COSObjectKey(3, 0): -4})  # type: ignore[dict-item]
        assert None not in doc.get_xref_table()
        assert doc.get_xref_table()[COSObjectKey(3, 0)] == -4
        assert doc.has_object(COSObjectKey(3, 0))


def test_close_empties_pool() -> None:
    doc = COSDocument()
    doc.get_object_from_pool(COSObjectKey(1, 0))
    doc.close()
    assert doc.get_objects() == []
    assert doc.get_object_keys() == []
