from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.action.pd_annotation_additional_actions import (
    PDAnnotationAdditionalActions,
)
from pypdfbox.pdmodel.interactive.action.pd_form_field_additional_actions import (
    PDFormFieldAdditionalActions,
)


def _uri(value: str) -> PDActionURI:
    action = PDActionURI()
    action.set_uri(value)
    return action


# ---------- PDFormFieldAdditionalActions ----------


def test_form_field_additional_actions_round_trip_kfvc() -> None:
    aa = PDFormFieldAdditionalActions()

    aa.set_k(_uri("https://example.test/k"))
    aa.set_f(_uri("https://example.test/f"))
    aa.set_v(_uri("https://example.test/v"))
    aa.set_c(_uri("https://example.test/c"))

    k = aa.get_k()
    f = aa.get_f()
    v = aa.get_v()
    c = aa.get_c()

    assert isinstance(k, PDActionURI) and k.get_uri() == "https://example.test/k"
    assert isinstance(f, PDActionURI) and f.get_uri() == "https://example.test/f"
    assert isinstance(v, PDActionURI) and v.get_uri() == "https://example.test/v"
    assert isinstance(c, PDActionURI) and c.get_uri() == "https://example.test/c"


def test_form_field_additional_actions_set_none_removes_entry() -> None:
    aa = PDFormFieldAdditionalActions()
    cos = aa.get_cos_object()

    for setter, key in (
        (aa.set_k, COSName.get_pdf_name("K")),
        (aa.set_f, COSName.get_pdf_name("F")),
        (aa.set_v, COSName.get_pdf_name("V")),
        (aa.set_c, COSName.get_pdf_name("C")),
    ):
        setter(_uri("https://example.test"))
        assert cos.get_dictionary_object(key) is not None
        setter(None)
        assert cos.get_dictionary_object(key) is None


def test_form_field_additional_actions_default_dict_is_empty() -> None:
    aa = PDFormFieldAdditionalActions()
    assert aa.get_k() is None
    assert aa.get_f() is None
    assert aa.get_v() is None
    assert aa.get_c() is None


# ---------- PDAnnotationAdditionalActions ----------


_ANN_TRIGGERS = [
    ("e", "E"),
    ("x", "X"),
    ("d", "D"),
    ("u", "U"),
    ("fo", "Fo"),
    ("bl", "Bl"),
    ("po", "PO"),
    ("pc", "PC"),
    ("pv", "PV"),
    ("pi", "PI"),
]


def test_annotation_additional_actions_round_trip_all_triggers() -> None:
    aa = PDAnnotationAdditionalActions()

    for attr, _ in _ANN_TRIGGERS:
        getattr(aa, f"set_{attr}")(_uri(f"https://example.test/{attr}"))

    for attr, _ in _ANN_TRIGGERS:
        action = getattr(aa, f"get_{attr}")()
        assert isinstance(action, PDActionURI)
        assert action.get_uri() == f"https://example.test/{attr}"


def test_annotation_additional_actions_set_none_removes_each_entry() -> None:
    aa = PDAnnotationAdditionalActions()
    cos = aa.get_cos_object()

    for attr, key_str in _ANN_TRIGGERS:
        key = COSName.get_pdf_name(key_str)
        getattr(aa, f"set_{attr}")(_uri("https://example.test"))
        assert cos.get_dictionary_object(key) is not None
        getattr(aa, f"set_{attr}")(None)
        assert cos.get_dictionary_object(key) is None


def test_annotation_additional_actions_default_dict_is_empty() -> None:
    aa = PDAnnotationAdditionalActions()
    for attr, _ in _ANN_TRIGGERS:
        assert getattr(aa, f"get_{attr}")() is None


def test_annotation_additional_actions_wraps_existing_dict() -> None:
    seed = PDAnnotationAdditionalActions()
    seed.set_e(_uri("https://example.test/seed"))

    wrapper = PDAnnotationAdditionalActions(seed.get_cos_object())
    e = wrapper.get_e()
    assert isinstance(e, PDActionURI)
    assert e.get_uri() == "https://example.test/seed"
    assert wrapper.get_cos_object() is seed.get_cos_object()
