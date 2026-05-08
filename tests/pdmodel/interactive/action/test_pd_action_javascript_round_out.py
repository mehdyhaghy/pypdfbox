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


def test_get_action_decodes_cos_stream_body_with_utf8_bom() -> None:
    """When ``/JS`` is a stream rather than a text string, UTF-8 bytes are
    honored when the PDF 2.0 UTF-8 BOM is present."""
    src = "var x = 'unicode ☃ snowman';"
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"\xef\xbb\xbf" + src.encode("utf-8"))
    action = PDActionJavaScript()
    action.get_cos_object().set_item(_JS, stream)

    assert action.get_action() == src


def test_get_action_decodes_cos_stream_body_as_pdf_text_string() -> None:
    """PDFBox reads stream-form ``/JS`` through ``COSStream.toTextString``.

    Non-BOM stream bytes therefore fall back to PDFDocEncoding, not strict
    UTF-8.
    """
    stream = COSStream()
    stream.set_raw_data(b"app.alert('caf\xe9');")
    action = PDActionJavaScript()
    action.get_cos_object().set_item(_JS, stream)

    assert action.get_action() == "app.alert('café');"


def test_get_action_returns_none_for_unexpected_type() -> None:
    """A non-string, non-stream ``/JS`` value (e.g. a name) is treated
    as absent rather than crashing the accessor."""
    action = PDActionJavaScript()
    action.get_cos_object().set_item(_JS, COSName.get_pdf_name("Surprise"))

    assert action.get_action() is None
