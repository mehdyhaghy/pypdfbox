from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_movie import (
    PDAnnotationMovie,
)


def test_movie_subtype_constant() -> None:
    assert PDAnnotationMovie.SUB_TYPE == "Movie"


def test_movie_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationMovie()
    assert ann.get_subtype() == "Movie"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_movie_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Movie")  # type: ignore[attr-defined]
    ann = PDAnnotationMovie(d)
    assert ann.get_subtype() == "Movie"
    assert ann.get_cos_object() is d


def test_movie_title_round_trip() -> None:
    ann = PDAnnotationMovie()
    assert ann.get_title() is None
    ann.set_title("My Movie")
    assert ann.get_title() == "My Movie"
    ann.set_title(None)
    assert ann.get_title() is None


def test_movie_movie_dict_round_trip() -> None:
    ann = PDAnnotationMovie()
    assert ann.get_movie() is None
    movie = COSDictionary()
    movie.set_string(COSName.get_pdf_name("F"), "clip.mov")
    ann.set_movie(movie)
    got = ann.get_movie()
    assert got is movie
    ann.set_movie(None)
    assert ann.get_movie() is None


def test_movie_activation_round_trip() -> None:
    ann = PDAnnotationMovie()
    assert ann.get_activation() is None
    activation = COSDictionary()
    activation.set_name(COSName.get_pdf_name("Mode"), "Once")
    ann.set_activation(activation)
    assert ann.get_activation() is activation
    # Boolean activation form also accepted.
    ann.set_activation(COSBoolean.TRUE)
    assert ann.get_activation() is COSBoolean.TRUE
    ann.set_activation(None)
    assert ann.get_activation() is None


def test_pd_annotation_create_dispatches_movie() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Movie")  # type: ignore[attr-defined]
    result = PDAnnotation.create(d)
    assert isinstance(result, PDAnnotationMovie)
    assert result.get_cos_object() is d
