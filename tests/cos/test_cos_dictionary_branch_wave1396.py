"""Wave 1396 branch-coverage tests for ``COSDictionary``.

Closes False-branch arrows:

* 159->147 — ``_array_get_indirect_object_keys`` falls through when
  child is neither a COSDictionary, COSArray, nor an indirect-key holder
* 179->167 — same shape inside ``_array_reset_object_keys``
* 338->exit — ``clear()`` no-op when items is already empty
* 418->exit — ``set_embedded_string`` no-op when value is None and
  dictionary doesn't exist yet
* 785->771, 827->818 — graph-walk fall-through for direct simple values
  inside the get_indirect_object_keys / reset_object_keys recursion
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
)
from pypdfbox.cos.cos_dictionary import (
    _array_get_indirect_object_keys,
    _array_reset_object_keys,
)


def test_clear_when_already_empty_short_circuits() -> None:
    """``clear()`` does not re-fire the update channel when items is empty.

    Closes False arm at line 338.
    """
    d = COSDictionary()
    # Already empty.
    assert d.is_empty()
    d.clear()  # must not raise
    assert d.is_empty()


def test_set_embedded_string_no_op_when_dict_missing_and_value_none() -> None:
    """``set_embedded_string`` is a no-op when value is None and the
    embedded dict doesn't already exist.

    Closes False arm at line 418.
    """
    d = COSDictionary()
    # /Foo dict doesn't exist; passing None leaves the parent unchanged.
    d.set_embedded_string("Foo", "Key", None)
    assert d.get_dictionary_object(COSName.get_pdf_name("Foo")) is None


def test_array_get_indirect_object_keys_skips_simple_values() -> None:
    """Simple (non-dict/array/object) values are ignored.

    Closes False arm at line 159.
    """
    arr = COSArray()
    arr.add(COSInteger.get(7))  # simple scalar; no indirect key
    keys: set = set()
    _array_get_indirect_object_keys(arr, keys)
    assert keys == set()


def test_array_reset_object_keys_skips_simple_values() -> None:
    """Simple values short-circuit in the array reset walker.

    Closes False arm at line 179.
    """
    arr = COSArray()
    arr.add(COSInteger.get(7))
    keys: set = set()
    _array_reset_object_keys(arr, keys)
    assert keys == set()


def test_get_indirect_object_keys_skips_simple_direct_values() -> None:
    """Dictionaries whose values are direct simple types do not
    contribute indirect-object keys.

    Closes False arm at line 785 (``elif indirect_key is not None``)
    inside the recursive walk.
    """
    d = COSDictionary()
    d.set_item("Foo", COSInteger.get(7))  # direct simple value, no /Parent
    keys: set = set()
    d.get_indirect_object_keys(keys)
    assert keys == set()


def test_reset_object_keys_skips_simple_direct_values() -> None:
    """Same shape in reset_object_keys: simple values short-circuit.

    Closes False arm at line 827.
    """
    d = COSDictionary()
    d.set_item("Foo", COSInteger.get(7))
    seen: set = set()
    d.reset_object_keys(seen)
    assert seen == set()


def test_reset_object_keys_with_none_collection_returns_none() -> None:
    """Passing ``None`` for the collection returns ``None`` immediately.

    Sanity baseline for the line-815 early-exit branch.
    """
    d = COSDictionary()
    assert d.reset_object_keys(None) is None
