from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_movie import PDActionMovie
from pypdfbox.pdmodel.interactive.action.pd_action_rendition import PDActionRendition
from pypdfbox.pdmodel.interactive.action.pd_action_sound import PDActionSound
from pypdfbox.pdmodel.interactive.action.pd_action_transition import PDActionTransition
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.pagenavigation.pd_transition import PDTransition
from pypdfbox.pdmodel.interactive.pagenavigation.pd_transition_style import (
    PDTransitionStyle,
)


_S: COSName = COSName.get_pdf_name("S")


def _sub_type(action: object) -> str | None:
    return action.get_cos_object().get_name(_S)  # type: ignore[attr-defined]


def test_pd_action_sound_round_trip() -> None:
    sound_stream = COSStream()
    action = PDActionSound()
    assert _sub_type(action) == "Sound"

    action.set_sound(sound_stream)
    action.set_volume(0.5)
    action.set_synchronous(True)
    action.set_repeat(True)
    action.set_mix(True)

    assert action.get_sound() is sound_stream
    assert action.get_volume() == 0.5
    assert action.is_synchronous() is True
    assert action.is_repeat() is True
    assert action.is_mix() is True

    # Defaults when entries are absent.
    fresh = PDActionSound()
    assert fresh.get_volume() == 1.0
    assert fresh.is_synchronous() is False
    assert fresh.is_repeat() is False
    assert fresh.is_mix() is False
    assert fresh.get_sound() is None


def test_pd_action_movie_round_trip() -> None:
    action = PDActionMovie()
    assert _sub_type(action) == "Movie"

    action.set_t("Intro Clip")
    action.set_operation("Play")
    annotation = COSDictionary()
    action.set_annotation(annotation)

    assert action.get_t() == "Intro Clip"
    assert action.get_operation() == "Play"
    assert action.get_annotation() is annotation

    action.set_annotation(None)
    action.set_operation(None)
    action.set_t(None)
    assert action.get_annotation() is None
    assert action.get_operation() is None
    assert action.get_t() is None


def test_pd_action_rendition_round_trip() -> None:
    action = PDActionRendition()
    assert _sub_type(action) == "Rendition"

    action.set_op(2)
    action.set_js("app.alert('x')")
    rendition = COSDictionary()
    widget = COSDictionary()
    action.set_r(rendition)
    action.set_an(widget)

    assert action.get_op() == 2
    assert action.get_js() == "app.alert('x')"
    assert action.get_r() is rendition
    assert action.get_an() is widget

    action.set_r(None)
    action.set_an(None)
    assert action.get_r() is None
    assert action.get_an() is None


def test_pd_action_transition_round_trip() -> None:
    action = PDActionTransition()
    assert _sub_type(action) == "Trans"

    trans = PDTransition(style=PDTransitionStyle.SPLIT)
    action.set_trans(trans)

    resolved = action.get_trans()
    assert isinstance(resolved, PDTransition)
    assert resolved.get_style() == PDTransitionStyle.SPLIT

    action.set_trans(None)
    assert action.get_trans() is None


def test_pd_action_embedded_go_to_round_trips_file_dest_window_target() -> None:
    action = PDActionEmbeddedGoTo()
    assert _sub_type(action) == "GoToE"

    fs = PDSimpleFileSpecification()
    fs.set_file("foo.pdf")
    action.set_file(fs)

    resolved_fs = action.get_file()
    assert isinstance(resolved_fs, PDSimpleFileSpecification)
    assert resolved_fs.get_file() == "foo.pdf"

    dest = PDPageXYZDestination()
    dest.set_page_number(0)
    action.set_d(dest)
    resolved_dest = action.get_d()
    assert isinstance(resolved_dest, PDPageXYZDestination)
    assert resolved_dest.get_page_number() == 0

    action.set_new_window(True)
    assert action.is_new_window() is True
    action.set_new_window(False)
    assert action.is_new_window() is False

    from pypdfbox.pdmodel.interactive.action import PDTargetDirectory

    target = COSDictionary()
    action.set_target(target)
    resolved_target = action.get_target()
    assert isinstance(resolved_target, PDTargetDirectory)
    assert resolved_target.get_cos_object() is target

    action.set_file(None)
    action.set_d(None)
    action.set_target(None)
    assert action.get_file() is None
    assert action.get_d() is None
    assert action.get_target() is None
