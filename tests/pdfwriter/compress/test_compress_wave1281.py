"""Hand-written tests for the new ``pdfwriter.compress`` ports."""

from __future__ import annotations

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.pdfwriter.compress.cos_object_pool import COSObjectPool
from pypdfbox.pdfwriter.compress.direct_access_byte_array_output_stream import (
    DirectAccessByteArrayOutputStream,
)


def test_direct_access_byte_array_output_stream_round_trip() -> None:
    stream = DirectAccessByteArrayOutputStream()
    stream.write(b"abc")
    stream.write(b"defg")
    assert stream.size() == 7
    assert stream.get_raw_data() == b"abcdefg"


def test_cos_object_pool_assigns_new_key() -> None:
    pool = COSObjectPool(0)
    base = COSInteger(42)
    key = pool.put(None, base)
    assert key is not None
    assert key.get_number() == 1
    assert pool.contains_key(key)
    assert pool.contains_object(base)
    assert pool.get_object(key) is base
    assert pool.get_highest_xref_object_number() == 1


def test_cos_object_pool_respects_given_key() -> None:
    pool = COSObjectPool(0)
    dict_ = COSDictionary()
    key = COSObjectKey(5, 0)
    assigned = pool.put(key, dict_)
    assert assigned == key
    assert pool.get_highest_xref_object_number() == 5


def test_cos_object_pool_skips_duplicate_put() -> None:
    pool = COSObjectPool(0)
    dict_ = COSDictionary()
    first = pool.put(None, dict_)
    second = pool.put(first, dict_)
    assert second is None
