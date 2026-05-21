"""Upstream-parity port for ``PDAnnotationRubberStamp``.

Mirrors ``PDAnnotationRubberStamp.java`` (PDFBox 3.0.x). Upstream ships
no JUnit test for the rubber-stamp wrapper — this module ports the
source's behavioural contract: SUB_TYPE stamp, all 14 ``NAME_*``
constants from PDF 32000-1 Table 183, ``/Name`` accessor with spec
default ``Draft``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_rubber_stamp import (
    PDAnnotationRubberStamp,
)

_SUBTYPE = COSName.get_pdf_name("Subtype")
_NAME = COSName.get_pdf_name("Name")


def test_default_constructor_stamps_subtype():
    ann = PDAnnotationRubberStamp()
    assert ann.get_subtype() == "Stamp"
    assert ann.get_cos_object().get_name(_SUBTYPE) == "Stamp"


def test_get_name_default_is_draft():
    # Upstream: ``getNameAsString(COSName.NAME, NAME_DRAFT)``.
    ann = PDAnnotationRubberStamp()
    assert ann.get_name() == "Draft"


def test_set_name_round_trip():
    ann = PDAnnotationRubberStamp()
    ann.set_name(PDAnnotationRubberStamp.NAME_APPROVED)
    assert ann.get_name() == "Approved"
    assert ann.get_cos_object().get_name(_NAME) == "Approved"


def test_dict_ctor_preserves_existing_name():
    d = COSDictionary()
    d.set_name(_SUBTYPE, "Stamp")
    d.set_name(_NAME, "TopSecret")
    ann = PDAnnotationRubberStamp(d)
    assert ann.get_name() == "TopSecret"


@pytest.mark.parametrize(
    "constant_name,expected_value",
    [
        ("NAME_APPROVED", "Approved"),
        ("NAME_EXPERIMENTAL", "Experimental"),
        ("NAME_NOT_APPROVED", "NotApproved"),
        ("NAME_AS_IS", "AsIs"),
        ("NAME_EXPIRED", "Expired"),
        ("NAME_NOT_FOR_PUBLIC_RELEASE", "NotForPublicRelease"),
        ("NAME_FOR_PUBLIC_RELEASE", "ForPublicRelease"),
        ("NAME_DRAFT", "Draft"),
        ("NAME_FOR_COMMENT", "ForComment"),
        ("NAME_TOP_SECRET", "TopSecret"),
        ("NAME_DEPARTMENTAL", "Departmental"),
        ("NAME_CONFIDENTIAL", "Confidential"),
        ("NAME_FINAL", "Final"),
        ("NAME_SOLD", "Sold"),
    ],
)
def test_all_standard_name_constants_match_spec(constant_name, expected_value):
    # PDF 32000-1:2008 §12.5.6.14 Table 183 — the 14 standard icon names.
    assert getattr(PDAnnotationRubberStamp, constant_name) == expected_value


def test_set_name_with_each_standard_constant():
    ann = PDAnnotationRubberStamp()
    for name in (
        PDAnnotationRubberStamp.NAME_APPROVED,
        PDAnnotationRubberStamp.NAME_EXPERIMENTAL,
        PDAnnotationRubberStamp.NAME_NOT_APPROVED,
        PDAnnotationRubberStamp.NAME_AS_IS,
        PDAnnotationRubberStamp.NAME_EXPIRED,
        PDAnnotationRubberStamp.NAME_NOT_FOR_PUBLIC_RELEASE,
        PDAnnotationRubberStamp.NAME_FOR_PUBLIC_RELEASE,
        PDAnnotationRubberStamp.NAME_DRAFT,
        PDAnnotationRubberStamp.NAME_FOR_COMMENT,
        PDAnnotationRubberStamp.NAME_TOP_SECRET,
        PDAnnotationRubberStamp.NAME_DEPARTMENTAL,
        PDAnnotationRubberStamp.NAME_CONFIDENTIAL,
        PDAnnotationRubberStamp.NAME_FINAL,
        PDAnnotationRubberStamp.NAME_SOLD,
    ):
        ann.set_name(name)
        assert ann.get_name() == name


def test_sub_type_constant_equals_stamp():
    assert PDAnnotationRubberStamp.SUB_TYPE == "Stamp"
