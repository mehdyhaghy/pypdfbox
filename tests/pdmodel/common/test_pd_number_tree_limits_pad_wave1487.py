"""Wave 1487: half-populated ``/Limits`` padding parity.

Surface: ``PDNumberTreeNode._ensure_limits_array`` (and the identical helper on
``PDNameTreeNode``) pads a freshly-created two-slot ``/Limits`` array with
``COSNull.NULL`` while upstream PDFBox pads with a Java ``null`` list element
(``arr.add(null); arr.add(null)``). When only ONE limit is later set
(``set_lower_limit`` / ``set_upper_limit`` with the other slot left untouched),
the not-yet-set slot retains the padding value.

The live oracle (``NumberTreeLimitsPadProbe`` / the
``test_*_limits_pad_oracle`` modules) confirmed this is a NON-observable
representation difference:

  - ``COSArray.get_object(i)`` resolves a ``COSNull.NULL`` slot to ``None``,
    exactly matching upstream ``getObject`` (which resolves ``COSNull`` -> Java
    ``null``) AND a literal Java-null slot (also ``null``). Both sides return
    ``None`` from the documented resolving accessor.
  - ``COSWriter.visit_from_array`` serializes a ``COSNull.NULL`` slot via its
    ``else`` branch (``current.accept(self)`` -> COSNull -> the token ``null``);
    upstream serializes a Java-null slot via its ``current == null`` branch
    (``COSNull.NULL.accept(this)`` -> the same token ``null``). The bytes are
    identical: ``[5 null]`` / ``[null 9]``.

The only difference is the raw, non-resolving ``get(i)`` element type
(``COSNull.NULL`` vs Java ``null``), which is never written to disk and never
surfaces through the resolving accessor. Parity is therefore byte-for-byte;
this module pins the serialized bytes so the representation choice cannot drift
into an observable divergence.
"""

from __future__ import annotations

import io

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
)
from pypdfbox.pdfwriter.cos_writer import COSWriter
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode
from pypdfbox.pdmodel.common.pd_number_tree_node import PDNumberTreeNode

_LIMITS = COSName.get_pdf_name("Limits")


class _IntNode(PDNumberTreeNode[int]):
    def convert_cos_to_value(self, base: COSBase) -> int:
        assert isinstance(base, COSInteger)
        return int(base.value)

    def convert_value_to_cos(self, value: int) -> COSBase:
        return COSInteger.get(value)

    def create_child_node(self, dic: COSDictionary) -> _IntNode:
        return _IntNode(dic)


class _StrNode(PDNameTreeNode[str]):
    def convert_cos_to_value(self, base: COSBase) -> str:
        return str(base)

    def convert_value_to_cos(self, value: str) -> COSBase:
        return COSInteger.get(0)  # value side irrelevant for /Limits padding

    def create_child_node(self, dic: COSDictionary) -> _StrNode:
        return _StrNode(dic)


def _limits(node: PDNumberTreeNode | PDNameTreeNode) -> COSArray:
    arr = node.get_cos_object().get_dictionary_object(_LIMITS)
    assert isinstance(arr, COSArray)
    return arr


def _serialize_array(arr: COSArray) -> bytes:
    arr.set_direct(True)
    buf = io.BytesIO()
    arr.accept(COSWriter(buf))
    return buf.getvalue()


# ---------------- number tree ----------------


def test_number_lower_only_pads_unset_slot() -> None:
    node = _IntNode()
    node.set_lower_limit(5)
    arr = _limits(node)
    assert arr.size() == 2
    # Raw slot holds COSNull.NULL (pypdfbox representation choice).
    assert arr.get(1) is COSNull.NULL
    # Resolving accessor matches upstream getObject -> None.
    assert arr.get_object(0) == COSInteger.get(5)
    assert arr.get_object(1) is None
    assert node.get_lower_limit() == 5
    assert node.get_upper_limit() is None


def test_number_upper_only_pads_unset_slot() -> None:
    node = _IntNode()
    node.set_upper_limit(9)
    arr = _limits(node)
    assert arr.get(0) is COSNull.NULL
    assert arr.get_object(0) is None
    assert arr.get_object(1) == COSInteger.get(9)
    assert node.get_lower_limit() is None
    assert node.get_upper_limit() == 9


def test_number_half_populated_serializes_to_null_token() -> None:
    # Oracle-pinned bytes: PDFBox emits "[5 null]" / "[null 9]" / "[5 9]".
    lower = _IntNode()
    lower.set_lower_limit(5)
    assert _serialize_array(_limits(lower)) == b"[5 null]\n"

    upper = _IntNode()
    upper.set_upper_limit(9)
    assert _serialize_array(_limits(upper)) == b"[null 9]\n"

    both = _IntNode()
    both.set_lower_limit(5)
    both.set_upper_limit(9)
    assert _serialize_array(_limits(both)) == b"[5 9]\n"


def test_number_set_then_clear_limit_restores_null_token() -> None:
    node = _IntNode()
    node.set_lower_limit(5)
    node.set_upper_limit(9)
    node.set_upper_limit(None)
    arr = _limits(node)
    assert arr.get(1) is COSNull.NULL
    assert arr.get_object(1) is None
    assert _serialize_array(arr) == b"[5 null]\n"


# ---------------- name tree (shares the helper) ----------------


def test_name_lower_only_pads_unset_slot() -> None:
    node = _StrNode()
    node.set_lower_limit("alpha")
    arr = _limits(node)
    assert arr.size() == 2
    assert arr.get(1) is COSNull.NULL
    assert arr.get_object(1) is None
    assert node.get_lower_limit() == "alpha"
    assert node.get_upper_limit() is None


def test_name_half_populated_serializes_with_null_token() -> None:
    node = _StrNode()
    node.set_lower_limit("a")
    assert _serialize_array(_limits(node)) == b"[(a) null]\n"
