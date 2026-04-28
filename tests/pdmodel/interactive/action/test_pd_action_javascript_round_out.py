"""Round-out tests for :class:`PDActionJavaScript` covering the
``/JS`` accessor for both ``COSString`` and ``COSStream`` source forms.
"""

from __future__ import annotations

from pypdfbox.cos import COSName, COSStream, COSString
from pypdfbox.pdmodel.interactive.action import PDActionJavaScript

_JS: COSName = COSName.get_pdf_name("JS")


def test_default_subtype_is_javascript() -> None:
    action = PDActionJavaScript()
    assert action.get_sub_type() == "JavaScript"


def test_get_action_returns_none_when_js_absent() -> None:
    action = PDActionJavaScript()
    assert action.get_action() is None


def test_set_action_writes_cos_string_round_trip() -> None:
    action = PDActionJavaScript()
    src = "app.alert('hi');"
    action.set_action(src)

    assert action.get_action() == src
    raw = action.get_cos_object().get_dictionary_object(_JS)
    assert isinstance(raw, COSString)


def test_set_action_overwrites_previous_value() -> None:
    action = PDActionJavaScript()
    action.set_action("first();")
    action.set_action("second();")

    assert action.get_action() == "second();"


def test_set_action_none_removes_entry() -> None:
    action = PDActionJavaScript()
    action.set_action("x();")
    assert action.get_cos_object().contains_key(_JS)

    action.set_action(None)
    # Setting None on a string entry strips the key (matches set_string).
    assert not action.get_cos_object().contains_key(_JS)
    assert action.get_action() is None


def test_get_action_decodes_cos_stream_body_as_utf8() -> None:
    """When ``/JS`` is a stream rather than a text string, the decoded
    body is returned as UTF-8."""
    src = "var x = 'unicode ☃ snowman';"
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(src.encode("utf-8"))
    action = PDActionJavaScript()
    action.get_cos_object().set_item(_JS, stream)

    assert action.get_action() == src


def test_get_action_returns_none_for_unexpected_type() -> None:
    """A non-string, non-stream ``/JS`` value (e.g. a name) is treated
    as absent rather than crashing the accessor."""
    action = PDActionJavaScript()
    action.get_cos_object().set_item(_JS, COSName.get_pdf_name("Surprise"))

    assert action.get_action() is None
