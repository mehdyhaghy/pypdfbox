"""Wave 1347 coverage boost for
``pypdfbox.pdfparser.xref.normal_x_reference``.

Targets the residual branches not exercised by
``test_xref_entries_wave1281``:

- ``_is_object_stream`` returning ``False`` when the wrapped object is
  not a ``COSStream`` (line 48 fall-through).
- ``__repr__`` (lines 95-96) with the ``ObjectStreamParent`` prefix when
  ``is_object_stream()`` is true.
- ``to_string`` Java-name parity alias (line 109).
- ``_is_object_stream`` via a ``COSObject`` wrapper, exercising the
  ``obj.get_object()`` resolution path.

Pre-wave the module sat at 89.7 % (4 missing); this set takes it to
100 %.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSObject, COSObjectKey, COSStream
from pypdfbox.pdfparser.xref import NormalXReference, XReferenceType


def test_is_object_stream_false_for_non_stream() -> None:
    """``COSDictionary`` is not a ``COSStream`` — line 48 returns ``False``."""
    key = COSObjectKey(7, 0)
    obj = COSDictionary()
    ref = NormalXReference(0x100, key, obj)
    assert ref.is_object_stream() is False
    assert ref.get_object() is obj
    assert ref.get_type() is XReferenceType.NORMAL


def test_repr_for_object_stream_uses_object_stream_parent_prefix() -> None:
    """Lines 95-96: when ``is_object_stream()`` is true the repr uses
    the ``ObjectStreamParent{`` prefix."""
    key = COSObjectKey(9, 0)
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.OBJ_STM)
    ref = NormalXReference(4096, key, stream)
    assert ref.is_object_stream() is True
    text = repr(ref)
    assert text.startswith("ObjectStreamParent{")
    assert "byteOffset=4096" in text
    assert "key=" in text
    # ``__str__`` mirrors ``__repr__`` per the source contract.
    assert str(ref) == text


def test_repr_for_non_object_stream_uses_normal_reference_prefix() -> None:
    """Confirm the ``NormalReference{`` prefix is still selected when
    the referenced object is not an object stream."""
    key = COSObjectKey(3, 0)
    ref = NormalXReference(99, key, COSDictionary())
    text = repr(ref)
    assert text.startswith("NormalReference{")
    assert "byteOffset=99" in text


def test_to_string_parity_alias_returns_repr() -> None:
    """Line 109: ``to_string`` Java-parity alias delegates to ``__str__``."""
    key = COSObjectKey(4, 1)
    ref = NormalXReference(17, key, COSDictionary())
    assert ref.to_string() == str(ref)


def test_is_object_stream_via_cos_object_wrapper_resolves_inner() -> None:
    """``_is_object_stream`` unwraps a ``COSObject`` before checking
    the ``/Type`` entry. Confirms the ``isinstance(obj, COSObject)``
    branch resolves to the underlying stream."""
    key = COSObjectKey(11, 0)
    inner = COSStream()
    inner.set_item(COSName.TYPE, COSName.OBJ_STM)
    wrapper = COSObject(11, 0, resolved=inner)
    ref = NormalXReference(2048, key, wrapper)
    assert ref.is_object_stream() is True


def test_columns_match_byte_offset_and_generation() -> None:
    """Re-assert column accessors round-trip identical values across
    the simple non-stream branch — guards the ``get_*_column_value``
    docstring contracts referenced by upstream Java line numbers."""
    key = COSObjectKey(5, 2)
    ref = NormalXReference(31415, key, COSDictionary())
    assert ref.get_second_column_value() == 31415
    assert ref.get_third_column_value() == 2
    assert ref.get_first_column_value() == 1
    assert ref.get_byte_offset() == 31415
    assert ref.get_referenced_key() is key
