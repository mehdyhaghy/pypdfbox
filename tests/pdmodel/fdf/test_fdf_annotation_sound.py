from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.fdf import FDFAnnotation, FDFAnnotationSound


def test_default_constructor_sets_subtype() -> None:
    annot = FDFAnnotationSound()
    assert annot.get_cos_object().get_name_as_string("Subtype") == "Sound"


def test_is_fdf_annotation_subclass() -> None:
    assert issubclass(FDFAnnotationSound, FDFAnnotation)
    assert isinstance(FDFAnnotationSound(), FDFAnnotation)


def test_type_annot_stamped() -> None:
    annot = FDFAnnotationSound()
    assert annot.get_cos_object().get_name_as_string("Type") == "Annot"


def test_existing_dict_keeps_subtype() -> None:
    src = COSDictionary()
    src.set_name("Subtype", "Sound")
    annot = FDFAnnotationSound(src)
    assert annot.get_cos_object() is src
    assert annot.get_subtype() == "Sound"


def test_create_dispatches_to_sound() -> None:
    src = COSDictionary()
    src.set_name("Subtype", "Sound")
    assert isinstance(FDFAnnotation.create(src), FDFAnnotationSound)
