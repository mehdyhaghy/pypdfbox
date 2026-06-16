"""PDFormXObject accessor fuzz — behavioural parity with PDFBox 3.0.7.

Wave 1576 agent B. Hammers the form-XObject accessor surface with valid /
wrong-type / missing / malformed / indirect COS shapes and pins each result
to the value Apache PDFBox 3.0.7 returns:

- ``get_b_box`` — PDRectangle from a 4-element array; ``None`` when /BBox is
  absent or non-array; coordinates coerced (missing/non-numeric entries -> 0,
  matching ``COSArray.getFloat`` default; arrays longer than 4 truncate to the
  first four).
- ``get_matrix`` — identity ``[1,0,0,1,0,0]`` when /Matrix is absent, non-array,
  shorter than 6, or has any non-numeric entry (mirrors
  ``Matrix.createMatrix``); the stored 6-tuple otherwise (extra entries beyond
  6 ignored).
- ``get_resources`` — own PDResources for a dict value; ``None`` when absent;
  an EMPTY PDResources when the key is present but not a dict (PDFBOX-4372).
  It does NOT fall back to page resources at this level — that is the
  renderer's job.
- ``get_group`` / ``get_group_attributes`` — raw /Group dict and typed
  attributes; ``None`` when absent or wrong-type; transparency-group
  isolated/knockout default ``False``.
- ``get_form_type`` — default 1 when absent.
- ``get_struct_parents`` — default -1 when absent.
- COSStream-backed: the form IS a stream (``get_cos_object`` is a COSStream).

These are hand-written API-shape assertions; the live differential against the
Apache PDFBox oracle lives in
``oracle/test_form_xobject_dictionary_fuzz_wave1521.py`` and
``oracle/test_form_x_object_fuzz_wave1550.py``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.form.pd_transparency_group_attributes import (
    PDTransparencyGroupAttributes,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources

IDENTITY = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

BBOX = COSName.get_pdf_name("BBox")
MATRIX = COSName.get_pdf_name("Matrix")
RESOURCES = COSName.RESOURCES  # type: ignore[attr-defined]
GROUP = COSName.get_pdf_name("Group")
FORMTYPE = COSName.get_pdf_name("FormType")
STRUCT_PARENTS = COSName.get_pdf_name("StructParents")
TRANSPARENCY = COSName.get_pdf_name("Transparency")
S = COSName.get_pdf_name("S")
I = COSName.get_pdf_name("I")  # noqa: E741 — PDF key name /I
K = COSName.get_pdf_name("K")


def _form() -> PDFormXObject:
    return PDFormXObject(COSStream())


def _arr(*values: float) -> COSArray:
    return COSArray([COSFloat(float(v)) for v in values])


def _indirect(value, number: int = 42) -> COSObject:
    return COSObject(number, resolved=value)


# --------------------------------------------------------------------------
# /BBox
# --------------------------------------------------------------------------


def test_bbox_absent_is_none():
    assert _form().get_b_box() is None
    assert _form().get_bbox() is None
    assert not _form().has_b_box()


def test_bbox_four_element_array():
    form = _form()
    form.get_cos_object().set_item(BBOX, _arr(0, 0, 100, 200))
    bbox = form.get_b_box()
    assert isinstance(bbox, PDRectangle)
    assert bbox.get_lower_left_x() == 0.0
    assert bbox.get_lower_left_y() == 0.0
    assert bbox.get_upper_right_x() == 100.0
    assert bbox.get_upper_right_y() == 200.0
    assert form.has_b_box()


def test_bbox_negative_and_float_coords():
    form = _form()
    form.get_cos_object().set_item(BBOX, _arr(-10.5, -20.25, 30.5, 40.75))
    bbox = form.get_b_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == -10.5
    assert bbox.get_upper_right_y() == 40.75


def test_bbox_non_array_is_none():
    form = _form()
    form.get_cos_object().set_item(BBOX, COSInteger.get(5))
    assert form.get_b_box() is None
    assert not form.has_b_box()


def test_bbox_null_value_is_none():
    form = _form()
    form.get_cos_object().set_item(BBOX, COSNull.NULL)
    assert form.get_b_box() is None


def test_bbox_short_array_pads_missing_with_zero():
    # A 2-element array zero-pads to [1, 2, 0, 0]; PDRectangle.from_cos_array
    # then normalizes lower-left/upper-right via min/max (PDF §7.9.5), so the
    # corners come out as (0,0)-(1,2). Mirrors upstream PDRectangle(COSArray).
    form = _form()
    form.get_cos_object().set_item(BBOX, _arr(1, 2))
    bbox = form.get_b_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == 0.0
    assert bbox.get_lower_left_y() == 0.0
    assert bbox.get_upper_right_x() == 1.0
    assert bbox.get_upper_right_y() == 2.0


def test_bbox_non_numeric_entry_becomes_zero():
    form = _form()
    arr = COSArray([COSInteger.get(1), COSName.get_pdf_name("x"),
                    COSInteger.get(3), COSInteger.get(4)])
    form.get_cos_object().set_item(BBOX, arr)
    bbox = form.get_b_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == 1.0
    assert bbox.get_lower_left_y() == 0.0  # name -> 0
    assert bbox.get_upper_right_x() == 3.0


def test_bbox_long_array_uses_first_four():
    form = _form()
    form.get_cos_object().set_item(BBOX, _arr(0, 0, 5, 5, 99, 99))
    bbox = form.get_b_box()
    assert bbox is not None
    assert bbox.get_upper_right_x() == 5.0
    assert bbox.get_upper_right_y() == 5.0


def test_bbox_indirect_array_resolves():
    form = _form()
    form.get_cos_object().set_item(BBOX, _indirect(_arr(0, 0, 10, 10)))
    bbox = form.get_b_box()
    assert bbox is not None
    assert bbox.get_upper_right_x() == 10.0


# --------------------------------------------------------------------------
# /Matrix
# --------------------------------------------------------------------------


def test_matrix_absent_is_identity():
    assert _form().get_matrix() == IDENTITY
    assert not _form().has_matrix()


def test_matrix_six_values():
    form = _form()
    form.get_cos_object().set_item(MATRIX, _arr(2, 0, 0, 3, 10, 20))
    assert form.get_matrix() == [2.0, 0.0, 0.0, 3.0, 10.0, 20.0]
    assert form.has_matrix()


def test_matrix_integer_entries_become_float():
    form = _form()
    form.get_cos_object().set_item(
        MATRIX,
        COSArray([COSInteger.get(v) for v in (1, 0, 0, 1, 5, 6)]),
    )
    result = form.get_matrix()
    assert result == [1.0, 0.0, 0.0, 1.0, 5.0, 6.0]
    assert all(isinstance(v, float) for v in result)


def test_matrix_non_array_is_identity():
    form = _form()
    form.get_cos_object().set_item(MATRIX, COSString("nope"))
    assert form.get_matrix() == IDENTITY
    assert not form.has_matrix()


def test_matrix_short_array_is_identity():
    form = _form()
    form.get_cos_object().set_item(MATRIX, _arr(1, 0, 0, 1, 0))
    assert form.get_matrix() == IDENTITY
    assert not form.has_matrix()


def test_matrix_empty_array_is_identity():
    form = _form()
    form.get_cos_object().set_item(MATRIX, COSArray([]))
    assert form.get_matrix() == IDENTITY


def test_matrix_non_numeric_entry_is_identity():
    form = _form()
    arr = COSArray([COSFloat(1), COSFloat(0), COSName.get_pdf_name("bad"),
                    COSFloat(1), COSFloat(0), COSFloat(0)])
    form.get_cos_object().set_item(MATRIX, arr)
    assert form.get_matrix() == IDENTITY
    assert not form.has_matrix()


def test_matrix_null_value_is_identity():
    form = _form()
    form.get_cos_object().set_item(MATRIX, COSNull.NULL)
    assert form.get_matrix() == IDENTITY


def test_matrix_long_array_uses_first_six():
    form = _form()
    form.get_cos_object().set_item(MATRIX, _arr(1, 0, 0, 1, 7, 8, 9, 10))
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 7.0, 8.0]


def test_matrix_indirect_array_resolves():
    form = _form()
    form.get_cos_object().set_item(MATRIX, _indirect(_arr(4, 0, 0, 4, 0, 0)))
    assert form.get_matrix() == [4.0, 0.0, 0.0, 4.0, 0.0, 0.0]


# --------------------------------------------------------------------------
# /Resources — no page-level fallback at this layer
# --------------------------------------------------------------------------


def test_resources_absent_is_none():
    assert _form().get_resources() is None
    assert not _form().has_resources()


def test_resources_dict_returns_pdresources():
    form = _form()
    res_dict = COSDictionary()
    form.get_cos_object().set_item(RESOURCES, res_dict)
    res = form.get_resources()
    assert isinstance(res, PDResources)
    assert res.get_cos_object() is res_dict
    assert form.has_resources()


def test_resources_non_dict_returns_empty_pdresources():
    # PDFBOX-4372: key present but not a dict -> empty PDResources, not None.
    form = _form()
    form.get_cos_object().set_item(RESOURCES, COSInteger.get(0))
    res = form.get_resources()
    assert isinstance(res, PDResources)
    # A freshly-built empty resources dict, NOT the bogus integer value.
    assert res.get_cos_object() is not None
    assert form.has_resources()


def test_resources_does_not_autocreate_when_absent():
    form = _form()
    form.get_resources()
    # Accessor must not have written a /Resources key.
    assert not form.get_cos_object().contains_key(RESOURCES)


def test_resources_indirect_dict_resolves():
    form = _form()
    res_dict = COSDictionary()
    form.get_cos_object().set_item(RESOURCES, _indirect(res_dict))
    res = form.get_resources()
    assert isinstance(res, PDResources)
    assert res.get_cos_object() is res_dict


# --------------------------------------------------------------------------
# /Group transparency group
# --------------------------------------------------------------------------


def test_group_absent_is_none():
    assert _form().get_group() is None
    assert _form().get_group_attributes() is None
    assert not _form().has_group()


def test_group_dict_returns_raw_and_typed():
    form = _form()
    grp = COSDictionary()
    grp.set_item(S, TRANSPARENCY)
    form.get_cos_object().set_item(GROUP, grp)
    assert form.get_group() is grp
    attrs = form.get_group_attributes()
    assert isinstance(attrs, PDTransparencyGroupAttributes)
    assert attrs.get_subtype() == "Transparency"
    assert attrs.is_transparency_group()
    assert form.has_group()


def test_group_non_dict_is_none():
    form = _form()
    form.get_cos_object().set_item(GROUP, COSInteger.get(3))
    assert form.get_group() is None
    assert form.get_group_attributes() is None
    assert not form.has_group()


def test_group_isolated_knockout_default_false():
    form = _form()
    grp = COSDictionary()
    grp.set_item(S, TRANSPARENCY)
    form.get_cos_object().set_item(GROUP, grp)
    attrs = form.get_group_attributes()
    assert attrs is not None
    assert attrs.is_isolated() is False
    assert attrs.is_knockout() is False
    assert not attrs.has_isolated()
    assert not attrs.has_knockout()


def test_group_isolated_knockout_true():
    form = _form()
    grp = COSDictionary()
    grp.set_item(S, TRANSPARENCY)
    grp.set_item(I, COSBoolean.TRUE)
    grp.set_item(K, COSBoolean.TRUE)
    form.get_cos_object().set_item(GROUP, grp)
    attrs = form.get_group_attributes()
    assert attrs is not None
    assert attrs.is_isolated() is True
    assert attrs.is_knockout() is True
    assert attrs.has_isolated()
    assert attrs.has_knockout()


def test_group_attributes_cached_identity():
    form = _form()
    grp = COSDictionary()
    grp.set_item(S, TRANSPARENCY)
    form.get_cos_object().set_item(GROUP, grp)
    assert form.get_group_attributes() is form.get_group_attributes()


def test_group_colorspace_absent_is_none():
    form = _form()
    grp = COSDictionary()
    grp.set_item(S, TRANSPARENCY)
    form.get_cos_object().set_item(GROUP, grp)
    attrs = form.get_group_attributes()
    assert attrs is not None
    assert attrs.get_color_space() is None
    assert not attrs.has_color_space()


def test_group_colorspace_devicergb():
    form = _form()
    grp = COSDictionary()
    grp.set_item(S, TRANSPARENCY)
    grp.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceRGB"))
    form.get_cos_object().set_item(GROUP, grp)
    attrs = form.get_group_attributes()
    assert attrs is not None
    assert attrs.has_color_space()
    cs = attrs.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceRGB"


# --------------------------------------------------------------------------
# /FormType
# --------------------------------------------------------------------------


def test_form_type_default_one():
    assert _form().get_form_type() == 1
    assert not _form().has_form_type()


def test_form_type_explicit():
    form = _form()
    form.get_cos_object().set_item(FORMTYPE, COSInteger.get(1))
    assert form.get_form_type() == 1
    assert form.has_form_type()


def test_form_type_non_int_value_falls_back_to_default():
    form = _form()
    form.get_cos_object().set_item(FORMTYPE, COSString("x"))
    assert form.get_form_type() == 1


# --------------------------------------------------------------------------
# /StructParents
# --------------------------------------------------------------------------


def test_struct_parents_default_minus_one():
    assert _form().get_struct_parents() == -1
    assert not _form().has_struct_parents()


def test_struct_parents_explicit():
    form = _form()
    form.get_cos_object().set_item(STRUCT_PARENTS, COSInteger.get(7))
    assert form.get_struct_parents() == 7
    assert form.get_struct_parent() == 7  # singular alias
    assert form.has_struct_parents()


# --------------------------------------------------------------------------
# COSStream-backed nature
# --------------------------------------------------------------------------


def test_form_is_cos_stream_backed():
    form = _form()
    assert isinstance(form.get_cos_object(), COSStream)


def test_form_subtype_is_form():
    form = _form()
    assert form.get_cos_object().get_name(COSName.get_pdf_name("Subtype")) == "Form"


def test_form_subtype_constant():
    assert PDFormXObject.SUBTYPE == "Form"


@pytest.mark.parametrize(
    ("matrix", "expected"),
    [
        (_arr(1, 0, 0, 1, 0, 0), [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]),
        (_arr(0.5, 0, 0, 0.5, 0, 0), [0.5, 0.0, 0.0, 0.5, 0.0, 0.0]),
        (_arr(-1, 0, 0, -1, 100, 100), [-1.0, 0.0, 0.0, -1.0, 100.0, 100.0]),
    ],
    ids=["identity", "scale-half", "flip"],
)
def test_matrix_roundtrip_values(matrix, expected):
    form = _form()
    form.get_cos_object().set_item(MATRIX, matrix)
    assert form.get_matrix() == expected
