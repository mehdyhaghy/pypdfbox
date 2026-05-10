from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream, COSString
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
    TargetStep,
)
from pypdfbox.pdmodel.interactive.action.pd_action_movie import PDActionMovie
from pypdfbox.pdmodel.interactive.action.pd_action_remote_go_to import (
    PDActionRemoteGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_rendition import PDActionRendition
from pypdfbox.pdmodel.interactive.action.pd_action_sound import PDActionSound
from pypdfbox.pdmodel.interactive.action.pd_action_transition import PDActionTransition
from pypdfbox.pdmodel.interactive.action.pd_target_directory import PDTargetDirectory
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)
from pypdfbox.pdmodel.interactive.pagenavigation.pd_transition import PDTransition
from pypdfbox.pdmodel.interactive.pagenavigation.pd_transition_style import (
    PDTransitionStyle,
)
from pypdfbox.pdmodel.interactive.sound.pd_sound_stream import PDSoundStream

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

    resolved = action.get_sound()
    assert isinstance(resolved, PDSoundStream)
    assert resolved.get_cos_object() is sound_stream
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
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_movie import (
        PDAnnotationMovie,
    )

    action = PDActionMovie()
    assert _sub_type(action) == "Movie"

    action.set_t("Intro Clip")
    action.set_operation("Play")
    annotation = COSDictionary()
    action.set_annotation(annotation)

    assert action.get_t() == "Intro Clip"
    assert action.get_operation() == "Play"
    # Raw back-compat accessor returns the dict that was stored.
    assert action.get_annotation_dictionary() is annotation
    # Typed accessor wraps it.
    typed = action.get_annotation()
    assert isinstance(typed, PDAnnotationMovie)
    assert typed.get_cos_object() is annotation

    # Round-trip via the typed wrapper directly.
    typed_in = PDAnnotationMovie()
    action.set_annotation(typed_in)
    assert action.get_annotation_dictionary() is typed_in.get_cos_object()

    action.set_annotation(None)
    action.set_operation(None)
    action.set_t(None)
    assert action.get_annotation() is None
    assert action.get_annotation_dictionary() is None
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


def test_walk_to_target_returns_each_chained_hop() -> None:
    """A 2-step ``/T`` chain (parent + child) yields two ``TargetStep``
    entries in root-first order with their accessor data flattened."""
    action = PDActionEmbeddedGoTo()

    parent = PDTargetDirectory()
    parent.set_relationship("P")
    parent.set_target_filename("parent.pdf")
    parent.set_page_number(2)
    parent.set_annotation_number(7)

    child = PDTargetDirectory()
    child.set_relationship("C")
    child.set_target_filename("child.pdf")
    child.set_named_destination("Section1")

    parent.set_target(child)
    action.set_target(parent)

    steps = action.walk_to_target()

    assert len(steps) == 2
    assert steps[0] == TargetStep(
        relationship="P",
        target_filename="parent.pdf",
        page_number=2,
        named_destination=None,
        annotation_number=7,
    )
    assert steps[1] == TargetStep(
        relationship="C",
        target_filename="child.pdf",
        page_number=None,
        named_destination="Section1",
        annotation_number=None,
    )


def test_walk_to_target_empty_when_no_chain() -> None:
    """An action without ``/T`` walks to an empty list."""
    action = PDActionEmbeddedGoTo()
    assert action.walk_to_target() == []


def test_walk_to_target_breaks_on_cycle() -> None:
    """A malformed ``/T`` chain that loops back to an already-visited
    ``COSDictionary`` terminates after recording the visited steps rather
    than spinning forever."""
    action = PDActionEmbeddedGoTo()

    parent = PDTargetDirectory()
    parent.set_relationship("P")
    parent.set_target_filename("parent.pdf")

    child = PDTargetDirectory()
    child.set_relationship("C")
    child.set_target_filename("child.pdf")

    # Build a 2-step chain, then point step 2's /T back at step 1's
    # underlying COSDictionary to form a cycle.
    parent.set_target(child)
    child.get_cos_object().set_item(
        COSName.get_pdf_name("T"), parent.get_cos_object()
    )
    action.set_target(parent)

    steps = action.walk_to_target()

    assert len(steps) == 2
    assert steps[0].target_filename == "parent.pdf"
    assert steps[1].target_filename == "child.pdf"


def test_get_destination_array_returns_pd_destination() -> None:
    """``/D`` as an explicit page-target ``COSArray`` dispatches to a
    concrete ``PDDestination`` subclass."""
    action = PDActionRemoteGoTo()
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("XYZ")])
    action.set_d(arr)

    resolved = action.get_destination()
    assert isinstance(resolved, PDDestination)
    assert isinstance(resolved, PDPageXYZDestination)


def test_get_destination_string_returns_str() -> None:
    """``/D`` as a ``COSString`` named destination is returned as ``str``."""
    action = PDActionRemoteGoTo()
    action.set_d(COSString("Chapter1"))

    assert action.get_destination() == "Chapter1"


def test_get_destination_none_when_absent() -> None:
    """``/D`` absent yields ``None`` from the typed dispatch."""
    action = PDActionRemoteGoTo()
    assert action.get_destination() is None
