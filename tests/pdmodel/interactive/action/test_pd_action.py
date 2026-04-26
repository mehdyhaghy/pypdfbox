from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import (
    PDAction,
    PDActionGoTo,
    PDActionJavaScript,
    PDActionLaunch,
    PDActionNamed,
    PDActionRemoteGoTo,
    PDActionUnknown,
    PDActionURI,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageXYZDestination,
)


def test_action_factory_dispatches_common_subtypes() -> None:
    expected = {
        "GoTo": PDActionGoTo,
        "URI": PDActionURI,
        "Named": PDActionNamed,
        "Launch": PDActionLaunch,
        "GoToR": PDActionRemoteGoTo,
        "JavaScript": PDActionJavaScript,
    }
    for sub_type, cls in expected.items():
        raw = COSDictionary()
        raw.set_name(COSName.get_pdf_name("S"), sub_type)
        assert isinstance(PDAction.create(raw), cls)


def test_action_factory_preserves_unknown_subtype() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("S"), "Movie")
    action = PDAction.create(raw)
    assert isinstance(action, PDActionUnknown)
    assert action.get_cos_object() is raw


def test_goto_destination_round_trip() -> None:
    action = PDActionGoTo()
    dest = PDPageXYZDestination()
    dest.set_page_number(3)
    action.set_destination(dest)

    resolved = action.get_destination()
    assert isinstance(resolved, PDPageXYZDestination)
    assert resolved.get_page_number() == 3


def test_uri_named_launch_remote_and_javascript_accessors() -> None:
    uri = PDActionURI()
    uri.set_uri("https://example.test")
    assert uri.get_uri() == "https://example.test"

    named = PDActionNamed()
    named.set_n("NextPage")
    assert named.get_n() == "NextPage"

    launch = PDActionLaunch()
    launch.set_file("open-me.pdf")
    assert launch.get_file() == "open-me.pdf"

    remote = PDActionRemoteGoTo()
    remote.set_file("other.pdf")
    assert remote.get_file() == "other.pdf"

    js = PDActionJavaScript()
    js.set_action("app.alert('x')")
    assert js.get_action() == "app.alert('x')"
