from __future__ import annotations

import datetime as dt
import io

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common.filespecification import PDEmbeddedFile
from pypdfbox.pdmodel.common.function import PDFunctionType4
from pypdfbox.pdmodel.common.function import pd_function_type4 as type4
from pypdfbox.pdmodel.common.pd_number_tree_node import PDNumberTreeNode
from pypdfbox.pdmodel.common.pd_stream import PDStream

_DECODE_PARMS = COSName.get_pdf_name("DecodeParms")
_FDECODE_PARMS = COSName.get_pdf_name("FDecodeParms")
_FFILTER = COSName.get_pdf_name("FFilter")
_FILTER = COSName.get_pdf_name("Filter")
_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_LENGTH = COSName.LENGTH  # type: ignore[attr-defined]
_MAC = COSName.get_pdf_name("Mac")
_NUMS = COSName.get_pdf_name("Nums")
_PARAMS = COSName.get_pdf_name("Params")


class _NullableNumberTreeNode(PDNumberTreeNode[int | None]):
    def convert_cos_to_value(self, base: COSBase) -> int | None:
        if base is None or isinstance(base, COSNull):
            return None
        if not isinstance(base, COSInteger):
            raise OSError(f"Expected COSInteger, got {type(base).__name__}")
        return int(base.value)

    def convert_value_to_cos(self, value: int | None) -> COSBase:
        return COSNull.NULL if value is None else COSInteger.get(value)

    def create_child_node(self, dic: COSDictionary) -> _NullableNumberTreeNode:
        return _NullableNumberTreeNode(dic)


def test_wave727_pd_stream_defensive_error_paths_and_empty_raw_copy() -> None:
    with pytest.raises(TypeError, match="PDStream expected"):
        PDStream(object())  # type: ignore[arg-type]

    stream = PDStream()
    stream.get_cos_object().set_item(_LENGTH, COSName.get_pdf_name("BadLength"))
    assert stream.get_length() == 0

    # Wave 1529: filter / decode-parms accessors mirror Apache PDFBox
    # 3.0.7's lenient normalisation — a /Filter that is neither a COSName
    # nor a COSArray (here a COSDictionary) yields an empty list, a
    # non-dict/non-array /DecodeParms yields None, and a /FDecodeParms
    # array carrying a non-dict element drops it (empty but non-None list).
    stream.get_cos_object().set_item(_FILTER, COSDictionary())
    assert stream.get_filters() == []

    stream.get_cos_object().set_item(_DECODE_PARMS, COSString("bad"))
    assert stream.get_decode_parms() is None

    stream.get_cos_object().set_item(_FFILTER, COSDictionary())
    assert stream.get_file_filters() == []

    stream.get_cos_object().set_item(_FDECODE_PARMS, COSArray([COSString("bad")]))
    assert stream.get_file_decode_parms() == []

    empty = PDStream()
    sink = io.BytesIO()
    assert empty.copy_raw_to(sink) == 0
    assert sink.getvalue() == b""


def test_wave727_number_tree_malformed_kids_nums_and_null_values() -> None:
    root_dict = COSDictionary()
    root_dict.set_item(_KIDS, COSArray([COSInteger.get(7)]))
    root = _NullableNumberTreeNode(root_dict)

    kids = root.get_kids()
    assert kids is not None
    assert len(kids) == 1
    assert kids[0].get_parent() is root
    assert kids[0].get_cos_object().size() == 0

    bad_leaf = COSDictionary()
    bad_nums = COSArray([COSName.get_pdf_name("Nope"), COSInteger.get(1)])
    bad_leaf.set_item(_NUMS, bad_nums)
    root_dict.set_item(_KIDS, COSArray([bad_leaf]))
    assert root.get_numbers() == {}

    tree = _NullableNumberTreeNode()
    tree.set_numbers({3: None})
    nums = tree.get_cos_object().get_dictionary_object(_NUMS)
    assert isinstance(nums, COSArray)
    assert nums.get(1) is COSNull.NULL
    assert nums.get_object(1) is None
    assert tree.get_numbers() == {3: None}

    odd = COSArray([COSInteger.get(5)])
    tree.get_cos_object().set_item(_NUMS, odd)
    assert tree.get_numbers() == {}

    empty = _NullableNumberTreeNode()
    assert empty.get_value(99) is None


def test_wave727_type4_private_error_and_operator_paths() -> None:
    fn = PDFunctionType4(COSStream())
    fn._function_stream = PDStream()  # type: ignore[assignment]
    fn._function_stream.get_cos_object = lambda: COSDictionary()  # type: ignore[method-assign]
    assert fn.get_instructions() == []

    # _pop_bool was folded into _op_if's inline boolean check by the
    # wave-1511 int/float type-discipline rewrite; the non-boolean-condition
    # error contract survives on the operator itself.
    with pytest.raises(OSError, match="boolean condition"):
        type4._op_if([1.0, [1]])

    with pytest.raises(OSError, match="roll rangecheck"):
        type4._op_roll([1.0, -1.0, 1.0])

    stack = [1.0, 2.0, 0.0, 0.0]
    type4._op_roll(stack)
    assert stack == [1.0, 2.0]

    truthy: list[object] = []
    type4.get_operator("true")(truthy)  # type: ignore[misc]
    type4.get_operator("false")(truthy)  # type: ignore[misc]
    assert truthy == [True, False]


def test_wave727_embedded_file_missing_and_empty_metadata_paths() -> None:
    embedded = PDEmbeddedFile()

    assert embedded.get_creation_date() is None
    assert embedded.get_mod_date() is None
    assert embedded.get_check_sum() is None
    assert embedded.has_mac_subtype() is False
    assert embedded.has_mac_creator() is False

    params = COSDictionary()
    params.set_string(COSName.get_pdf_name("CreationDate"), "")
    params.set_string(COSName.get_pdf_name("ModDate"), "D:20260509010203-05'30'")
    embedded.get_cos_object().set_item(_PARAMS, params)

    assert embedded.get_creation_date() is None
    assert embedded.get_mod_date() == dt.datetime(
        2026,
        5,
        9,
        1,
        2,
        3,
        tzinfo=dt.timezone(dt.timedelta(hours=-5, minutes=-30)),
    )

    params.set_item(_MAC, COSDictionary())
    assert embedded.has_mac_subtype() is False
    assert embedded.has_mac_creator() is False
