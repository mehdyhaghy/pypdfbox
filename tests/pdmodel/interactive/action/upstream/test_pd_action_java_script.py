"""Upstream-parity port for ``PDActionJavaScript``.

PDFBox 3.0.x ships no JUnit test for the JS action wrapper. This module
ports the upstream Java source's behavioural contract: the four
constructors, the COSString/COSStream dispatch on ``/JS``, and the
sub-type stamp.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_java_script import PDActionJavaScript

_S = COSName.get_pdf_name("S")
_JS = COSName.get_pdf_name("JS")


def test_default_constructor_stamps_subtype():
    # Upstream: ``setSubType( SUB_TYPE )`` lands /S = /JavaScript.
    action = PDActionJavaScript()
    assert action.get_sub_type() == "JavaScript"
    assert action.get_cos_object().get_name(_S) == "JavaScript"


def test_string_constructor_stamps_subtype_and_writes_js():
    # Upstream's ``PDActionJavaScript(String js)`` calls the no-arg ctor
    # then setAction(js).
    action = PDActionJavaScript("app.alert('hi');")
    assert action.get_sub_type() == "JavaScript"
    assert action.get_action() == "app.alert('hi');"


def test_cos_dictionary_constructor_does_not_overwrite_subtype():
    # Upstream's ``PDActionJavaScript(COSDictionary)`` calls super(a) only
    # — no setSubType. A handcrafted dict with a different /S survives.
    d = COSDictionary()
    d.set_name(_S, "JavaScript")
    d.set_string(_JS, "console.log(1);")
    action = PDActionJavaScript(d)
    assert action.get_sub_type() == "JavaScript"
    assert action.get_action() == "console.log(1);"


def test_set_action_writes_cos_string():
    action = PDActionJavaScript()
    action.set_action("var x = 1;")
    assert isinstance(action.get_cos_object().get_dictionary_object(_JS), COSString)
    assert action.get_action() == "var x = 1;"


def test_get_action_decodes_cos_stream_payload():
    # Upstream supports both COSString and COSStream payloads for /JS,
    # decoding the stream via ``toTextString()``.
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"app.alert('stream');")
    d = COSDictionary()
    d.set_name(_S, "JavaScript")
    d.set_item(_JS, stream)
    action = PDActionJavaScript(d)
    assert action.get_action() == "app.alert('stream');"
    stream.close()


def test_get_action_returns_none_for_missing_js():
    # Upstream returns null when /JS is absent (none of the instanceof
    # branches match).
    d = COSDictionary()
    d.set_name(_S, "JavaScript")
    action = PDActionJavaScript(d)
    assert action.get_action() is None


def test_get_action_returns_none_for_unexpected_type():
    # /JS as a /Name (COSName) — neither string nor stream — upstream
    # falls through to the else branch and returns null.
    d = COSDictionary()
    d.set_name(_S, "JavaScript")
    d.set_name(_JS, "Whatever")
    action = PDActionJavaScript(d)
    assert action.get_action() is None


def test_sub_type_constant_equals_javascript():
    assert PDActionJavaScript.SUB_TYPE == "JavaScript"
