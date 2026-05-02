from __future__ import annotations

from pypdfbox.cos import COSBoolean, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_movie import (
    PDAnnotationMovie,
)
from pypdfbox.pdmodel.interactive.annotation.pd_movie import PDMovie
from pypdfbox.pdmodel.interactive.annotation.pd_movie_activation import (
    PDMovieActivation,
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


def test_movie_pdfbox_camelcase_title_aliases() -> None:
    ann = PDAnnotationMovie()
    ann.setTitle("Clip")
    assert ann.getTitle() == "Clip"
    ann.setTitle(None)
    assert ann.getTitle() is None


def test_movie_movie_dict_round_trip() -> None:
    ann = PDAnnotationMovie()
    assert ann.get_movie() is None
    movie = COSDictionary()
    movie.set_string(COSName.get_pdf_name("F"), "clip.mov")
    ann.set_movie(movie)
    got = ann.get_movie()
    assert isinstance(got, PDMovie)
    assert got.get_cos_object() is movie
    assert ann.get_movie_dictionary() is movie
    ann.set_movie(None)
    assert ann.get_movie() is None


def test_movie_pdfbox_camelcase_movie_aliases() -> None:
    ann = PDAnnotationMovie()
    movie = PDMovie()

    ann.setMovie(movie)

    assert ann.getMovie() is not None
    assert ann.getMovie().get_cos_object() is movie.get_cos_object()  # type: ignore[union-attr]


def test_movie_activation_round_trip() -> None:
    ann = PDAnnotationMovie()
    assert ann.get_activation() is None
    activation = COSDictionary()
    activation.set_name(COSName.get_pdf_name("Mode"), "Once")
    ann.set_activation(activation)
    got = ann.get_activation()
    assert isinstance(got, PDMovieActivation)
    assert got.get_cos_object() is activation
    assert ann.get_activation_entry() is activation
    # Boolean activation form also accepted.
    ann.set_activation(COSBoolean.TRUE)
    assert ann.get_activation() is True
    assert ann.get_activation_entry() is COSBoolean.TRUE
    ann.set_activation(None)
    assert ann.get_activation() is None


def test_movie_pdfbox_camelcase_activation_aliases() -> None:
    ann = PDAnnotationMovie()
    activation = PDMovieActivation()

    ann.setActivation(activation)

    assert isinstance(ann.getActivation(), PDMovieActivation)
    ann.setActivation(False)
    assert ann.getActivation() is False


def test_pd_annotation_create_dispatches_movie() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Movie")  # type: ignore[attr-defined]
    result = PDAnnotation.create(d)
    assert isinstance(result, PDAnnotationMovie)
    assert result.get_cos_object() is d


def test_movie_typed_payload_accessors_round_trip() -> None:
    movie = PDMovie()
    file_spec = PDSimpleFileSpecification()
    file_spec.set_file("intro.mov")
    movie.set_file(file_spec)
    movie.set_aspect(640, 480)
    movie.set_rotation(90)

    poster = COSStream()
    movie.set_poster(poster)

    assert movie.get_file() is not None
    assert movie.get_file().get_file() == "intro.mov"  # type: ignore[union-attr]
    assert movie.get_aspect() == (640, 480)
    assert movie.get_rotation() == 90
    assert movie.get_poster() is poster

    ann = PDAnnotationMovie()
    ann.set_movie(movie)
    assert ann.get_movie_dictionary() is movie.get_cos_object()
    assert ann.get_movie().get_file().get_file() == "intro.mov"  # type: ignore[union-attr]

    movie.set_file("fallback.mov")
    assert movie.get_file().get_file() == "fallback.mov"  # type: ignore[union-attr]
    movie.set_poster(False)
    assert movie.get_poster() is False
    movie.set_aspect(None)
    movie.set_rotation(None)
    assert movie.get_aspect() is None
    assert movie.get_rotation() == 0


def test_movie_activation_mode_constants() -> None:
    assert PDMovieActivation.MODE_ONCE == "Once"
    assert PDMovieActivation.MODE_OPEN == "Open"
    assert PDMovieActivation.MODE_REPEAT == "Repeat"
    assert PDMovieActivation.MODE_PALINDROME == "Palindrome"


def test_movie_activation_mode_constants_round_trip() -> None:
    activation = PDMovieActivation()
    activation.set_mode(PDMovieActivation.MODE_PALINDROME)
    assert activation.get_mode() == "Palindrome"
    activation.set_mode(PDMovieActivation.MODE_ONCE)
    assert activation.get_mode() == "Once"


def test_movie_set_aspect_accepts_tuple_single_arg() -> None:
    movie = PDMovie()
    movie.set_aspect((1280, 720))
    assert movie.get_aspect() == (1280, 720)


def test_movie_set_aspect_accepts_list_single_arg() -> None:
    movie = PDMovie()
    movie.set_aspect([800, 600])
    assert movie.get_aspect() == (800, 600)


def test_movie_set_aspect_short_sequence_clears() -> None:
    movie = PDMovie()
    movie.set_aspect(640, 480)
    movie.set_aspect([])
    assert movie.get_aspect() is None


def test_movie_activation_typed_accessors_round_trip() -> None:
    activation = PDMovieActivation()
    start = COSFloat(1.25)
    duration = COSFloat(3.5)
    activation.set_start(start)
    activation.set_duration(duration)
    activation.set_rate(1.5)
    activation.set_volume(0.25)
    activation.set_show_controls(True)
    activation.set_mode("Repeat")

    assert activation.get_start() is start
    assert activation.get_duration() is duration
    assert activation.get_rate() == 1.5
    assert activation.get_volume() == 0.25
    assert activation.show_controls() is True
    assert activation.get_mode() == "Repeat"

    ann = PDAnnotationMovie()
    ann.set_activation(activation)
    assert ann.get_activation_entry() is activation.get_cos_object()
    assert isinstance(ann.get_activation(), PDMovieActivation)

    activation.set_start(None)
    activation.set_duration(None)
    activation.set_rate(None)
    activation.set_volume(None)
    activation.set_show_controls(None)
    activation.set_mode(None)
    assert activation.get_start() is None
    assert activation.get_duration() is None
    assert activation.get_rate() == 1.0
    assert activation.get_volume() == 1.0
    assert activation.show_controls() is False
    assert activation.get_mode() is None
