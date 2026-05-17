"""Coverage-boost tests for ``ObjectStreamXReference`` (wave 1323).

Targets the residual missing branches in
``pypdfbox.pdfparser.xref.object_stream_x_reference``: the
``get_referenced_key`` / ``get_object`` accessors and the ``__repr__`` /
``to_string`` formatting paths.
"""

from __future__ import annotations

from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdfparser.xref.abstract_x_reference import AbstractXReference
from pypdfbox.pdfparser.xref.object_stream_x_reference import (
    ObjectStreamXReference,
)
from pypdfbox.pdfparser.xref.x_reference_type import XReferenceType


def _make_ref(
    index: int = 2,
    key_num: int = 5,
    parent_num: int = 10,
    obj: object | None = None,
) -> ObjectStreamXReference:
    key = COSObjectKey(key_num, 0)
    parent_key = COSObjectKey(parent_num, 0)
    return ObjectStreamXReference(
        index, key, obj if obj is not None else COSString("payload"), parent_key
    )


def test_inherits_from_abstract_x_reference() -> None:
    """Confirms the inheritance hierarchy matches upstream
    ``AbstractXReference → ObjectStreamXReference`` (PDFBox 3.x).
    Mirrors CLAUDE.md's "preserve inheritance hierarchies" rule."""
    ref = _make_ref()
    assert isinstance(ref, AbstractXReference)


def test_type_is_object_stream_entry() -> None:
    ref = _make_ref()
    assert ref.get_type() is XReferenceType.OBJECT_STREAM_ENTRY


def test_get_referenced_key_returns_target_object_key() -> None:
    """``get_referenced_key`` returns the wrapped object's own
    ``COSObjectKey`` (Java line 73)."""
    ref = _make_ref(key_num=42)
    referenced = ref.get_referenced_key()
    assert referenced.get_number() == 42
    assert referenced.get_generation() == 0


def test_get_object_returns_wrapped_cos_base() -> None:
    """``get_object`` exposes the resolved ``COSBase`` stored inside the
    object stream (Java line 82)."""
    payload = COSString("hello")
    ref = _make_ref(obj=payload)
    assert ref.get_object() is payload


def test_get_parent_key_returns_object_stream_key() -> None:
    """``get_parent_key`` returns the ``COSObjectKey`` of the containing
    object stream (Java line 92)."""
    ref = _make_ref(parent_num=99)
    parent = ref.get_parent_key()
    assert parent.get_number() == 99


def test_get_object_stream_index_returns_position() -> None:
    """``get_object_stream_index`` returns the slot within the object
    stream (Java line 61)."""
    ref = _make_ref(index=7)
    assert ref.get_object_stream_index() == 7


def test_get_second_column_value_is_parent_object_number() -> None:
    """``getSecondColumnValue`` returns the parent object stream's
    object number per ISO 32000-1 §7.5.8.3 (Java line 105)."""
    ref = _make_ref(parent_num=42)
    assert ref.get_second_column_value() == 42


def test_get_third_column_value_is_index_within_stream() -> None:
    """``getThirdColumnValue`` returns the in-stream slot (Java line 117)."""
    ref = _make_ref(index=11)
    assert ref.get_third_column_value() == 11


def test_repr_carries_key_type_index_and_parent() -> None:
    """``__repr__`` mirrors upstream ``toString()`` — opens with
    ``ObjectStreamEntry{ key=…, type=2, objectStreamIndex=…, parent=… }``.
    Type code 2 is the numeric value of ``OBJECT_STREAM_ENTRY``."""
    ref = _make_ref(index=4, key_num=8, parent_num=17)
    text = repr(ref)
    assert text.startswith("ObjectStreamEntry{")
    assert "key=8 0 R" in text
    assert "type=2" in text
    assert "objectStreamIndex=4" in text
    assert "parent=17 0 R" in text
    assert text.endswith(" }")


def test_str_dunder_mirrors_repr() -> None:
    """The class assigns ``__str__ = __repr__`` so both produce the same
    upstream-shaped descriptor string."""
    ref = _make_ref()
    assert str(ref) == repr(ref)


def test_to_string_is_alias_for_str() -> None:
    """``to_string`` mirrors upstream ``ObjectStreamXReference.toString``
    (Java line 128); identical to ``str(ref)``."""
    ref = _make_ref(index=2, key_num=5, parent_num=10)
    assert ref.to_string() == str(ref)
    assert ref.to_string() == repr(ref)


def test_to_string_carries_provided_values() -> None:
    ref = _make_ref(index=99, key_num=123, parent_num=456)
    text = ref.to_string()
    assert "key=123 0 R" in text
    assert "objectStreamIndex=99" in text
    assert "parent=456 0 R" in text
