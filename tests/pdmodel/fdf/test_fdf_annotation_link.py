from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.fdf import FDFAnnotation, FDFAnnotationLink
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI


def test_default_constructor_sets_subtype() -> None:
    annot = FDFAnnotationLink()
    assert annot.get_cos_object().get_name_as_string("Subtype") == "Link"


def test_is_fdf_annotation_subclass() -> None:
    assert issubclass(FDFAnnotationLink, FDFAnnotation)
    assert isinstance(FDFAnnotationLink(), FDFAnnotation)


def test_init_action_uri_stores_a_entry() -> None:
    annot = FDFAnnotationLink()
    annot.init_action_uri("https://example.com/")
    a = annot.get_cos_object().get_cos_dictionary("A")
    assert a is not None
    action = PDActionURI(a)
    assert action.get_uri() == "https://example.com/"


def test_init_action_uri_none_is_no_op() -> None:
    annot = FDFAnnotationLink()
    annot.init_action_uri(None)
    assert annot.get_cos_object().get_dictionary_object("A") is None


def test_existing_dict_keeps_subtype() -> None:
    src = COSDictionary()
    src.set_name("Subtype", "Link")
    annot = FDFAnnotationLink(src)
    assert annot.get_cos_object() is src
    assert annot.get_subtype() == "Link"


def test_create_dispatches_to_link() -> None:
    src = COSDictionary()
    src.set_name("Subtype", "Link")
    assert isinstance(FDFAnnotation.create(src), FDFAnnotationLink)
