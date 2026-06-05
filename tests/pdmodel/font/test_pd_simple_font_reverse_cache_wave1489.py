"""Wave 1489 regression tests for the unicode->code reverse cache in
``pypdfbox.pdmodel.font.pd_simple_font``.

The cache (``_REVERSE_CACHE``) was originally keyed by ``id(encoding)``. That
is unsafe: CPython recycles ``id()`` values once an object is
garbage-collected, so a GC'd encoding whose address is reused by a *new*
encoding would return the stale reverse map. The cache is now a
``weakref.WeakKeyDictionary`` keyed by the encoding instance itself, which:

* auto-evicts the entry when the encoding is collected (no stale-id risk), and
* keeps two distinct live encodings with identical content on independent
  entries (default identity equality => distinct keys).
"""

from __future__ import annotations

import gc
import weakref

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.font.encoding import DictionaryEncoding
from pypdfbox.pdmodel.font.pd_simple_font import (
    _REVERSE_CACHE,
    _unicode_to_code_map,
)


def _make_dictionary_encoding() -> DictionaryEncoding:
    """A standalone /Differences encoding mapping code 65 -> 'A'."""
    enc_dict = COSDictionary()
    enc_dict.set_item(COSName.get_pdf_name("BaseEncoding"), COSName.WIN_ANSI_ENCODING)
    differences = COSArray()
    differences.add(COSInteger.get(65))
    differences.add(COSName.get_pdf_name("A"))
    enc_dict.set_item(COSName.get_pdf_name("Differences"), differences)
    return DictionaryEncoding(font_encoding=enc_dict, is_non_symbolic=True)


def test_cache_auto_evicts_dead_encoding() -> None:
    """A GC'd encoding leaves no entry in the WeakKeyDictionary."""
    encoding = _make_dictionary_encoding()
    ref = weakref.ref(encoding)

    _unicode_to_code_map(encoding)
    assert encoding in _REVERSE_CACHE
    len_with_entry = len(_REVERSE_CACHE)
    assert len_with_entry >= 1

    del encoding
    gc.collect()

    # The encoding is gone, so its weakref is dead and the cache entry must
    # have been auto-evicted (no stale-id map survives).
    assert ref() is None
    assert len(_REVERSE_CACHE) == len_with_entry - 1


def test_two_distinct_live_encodings_get_independent_maps() -> None:
    """Two distinct encodings with identical content keep separate entries."""
    enc_a = _make_dictionary_encoding()
    enc_b = _make_dictionary_encoding()
    assert enc_a is not enc_b

    map_a = _unicode_to_code_map(enc_a)
    map_b = _unicode_to_code_map(enc_b)

    # Identical content => equal maps, but distinct cache objects (no
    # cross-contamination from id() collision / accidental sharing).
    assert map_a == map_b
    assert map_a is not map_b
    assert enc_a in _REVERSE_CACHE
    assert enc_b in _REVERSE_CACHE
    assert _REVERSE_CACHE[enc_a] is map_a
    assert _REVERSE_CACHE[enc_b] is map_b

    # The reverse map round-trips: 'A' -> code 65.
    assert map_a.get("A") == 65


def test_repeated_lookup_returns_same_cached_object() -> None:
    """A second lookup for the same live encoding returns the cached map."""
    encoding = _make_dictionary_encoding()
    first = _unicode_to_code_map(encoding)
    second = _unicode_to_code_map(encoding)
    assert first is second
