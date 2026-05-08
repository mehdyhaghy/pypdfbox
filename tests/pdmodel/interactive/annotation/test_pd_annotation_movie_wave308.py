from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_movie import PDAnnotationMovie
from pypdfbox.pdmodel.interactive.annotation.pd_movie_activation import PDMovieActivation

_A = COSName.get_pdf_name("A")


def test_movie_effective_activation_defaults_true_when_absent() -> None:
    annotation = PDAnnotationMovie()

    assert annotation.get_activation() is None
    assert annotation.has_activation() is False
    assert annotation.get_effective_activation() is True


def test_movie_effective_activation_preserves_explicit_false() -> None:
    annotation = PDAnnotationMovie()

    annotation.set_activation(False)

    assert annotation.has_activation() is True
    assert annotation.get_activation() is False
    assert annotation.get_effective_activation() is False


def test_movie_effective_activation_wraps_activation_dictionary() -> None:
    annotation = PDAnnotationMovie()
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("Mode"), PDMovieActivation.MODE_REPEAT)

    annotation.set_activation(raw)

    effective = annotation.get_effective_activation()
    assert isinstance(effective, PDMovieActivation)
    assert effective.get_cos_object() is raw
    assert effective.get_mode() == PDMovieActivation.MODE_REPEAT


def test_movie_clear_activation_restores_absent_default() -> None:
    annotation = PDAnnotationMovie()
    annotation.set_activation(COSBoolean.FALSE)
    assert annotation.has_activation() is True

    annotation.clear_activation()

    assert annotation.has_activation() is False
    assert annotation.get_activation_entry() is None
    assert annotation.get_effective_activation() is True


def test_movie_effective_activation_returns_none_for_malformed_entry() -> None:
    annotation = PDAnnotationMovie()
    annotation.get_cos_object().set_item(_A, COSName.get_pdf_name("Malformed"))

    assert annotation.has_activation() is True
    assert annotation.get_activation() is None
    assert annotation.get_effective_activation() is None
