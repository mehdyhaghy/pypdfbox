from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_trap_net import (
    PDAnnotationTrapNet,
)


def test_wave363_default_constructor_sets_trap_net_subtype() -> None:
    annotation = PDAnnotationTrapNet()
    cos = annotation.get_cos_object()

    assert annotation.get_subtype() == PDAnnotationTrapNet.SUB_TYPE
    assert cos.get_name(COSName.SUBTYPE) == "TrapNet"  # type: ignore[attr-defined]


def test_wave363_existing_dictionary_is_not_clobbered() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "TrapNet")
    raw.set_string(COSName.get_pdf_name("LastModified"), "D:20260508000000Z")

    annotation = PDAnnotationTrapNet(raw)

    assert annotation.get_cos_object() is raw
    assert annotation.get_subtype() == "TrapNet"
    assert annotation.get_last_modified() == "D:20260508000000Z"


def test_wave363_last_modified_round_trip_and_clear() -> None:
    annotation = PDAnnotationTrapNet()
    key = COSName.get_pdf_name("LastModified")

    annotation.set_last_modified("D:20260508123456Z")
    assert annotation.get_last_modified() == "D:20260508123456Z"

    annotation.set_last_modified(None)
    assert annotation.get_last_modified() is None
    assert not annotation.get_cos_object().contains_key(key)


def test_wave363_array_fields_round_trip_and_clear_raw_arrays() -> None:
    annotation = PDAnnotationTrapNet()
    version = COSArray([COSName.get_pdf_name("TrapTool"), COSInteger.get(2)])
    states = COSArray([COSName.get_pdf_name("On"), COSName.get_pdf_name("Off")])
    fauxing = COSArray([COSDictionary()])

    annotation.set_version(version)
    annotation.set_annot_states(states)
    annotation.set_font_fauxing(fauxing)

    assert annotation.get_version() is version
    assert annotation.get_annot_states() is states
    assert annotation.get_font_fauxing() is fauxing

    annotation.set_version(None)
    annotation.set_annot_states(None)
    annotation.set_font_fauxing(None)

    assert annotation.get_version() is None
    assert annotation.get_annot_states() is None
    assert annotation.get_font_fauxing() is None
    cos = annotation.get_cos_object()
    assert not cos.contains_key(COSName.get_pdf_name("Version"))
    assert not cos.contains_key(COSName.get_pdf_name("AnnotStates"))
    assert not cos.contains_key(COSName.get_pdf_name("FontFauxing"))


def test_wave363_array_getters_ignore_wrong_cos_types() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("Version"), COSString("not an array"))
    raw.set_item(COSName.get_pdf_name("AnnotStates"), COSName.get_pdf_name("On"))
    raw.set_item(COSName.get_pdf_name("FontFauxing"), COSDictionary())

    annotation = PDAnnotationTrapNet(raw)

    assert annotation.get_version() is None
    assert annotation.get_annot_states() is None
    assert annotation.get_font_fauxing() is None
