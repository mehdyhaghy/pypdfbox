from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.interactive.action import PDActionJavaScript, PDActionNamed

_N: COSName = COSName.get_pdf_name("N")
_JS: COSName = COSName.get_pdf_name("JS")


# ---------- PDActionNamed ----------


@pytest.mark.parametrize(
    "constant",
    [
        PDActionNamed.NAMED_ACTION_NEXT_PAGE,
        PDActionNamed.NAMED_ACTION_PREV_PAGE,
        PDActionNamed.NAMED_ACTION_FIRST_PAGE,
        PDActionNamed.NAMED_ACTION_LAST_PAGE,
    ],
)
def test_named_set_n_round_trips_each_standard_constant(constant: str) -> None:
    """Each of the four standard PDF 32000-1 §12.6.4.11 constants survives
    a ``set_n``/``get_n`` round-trip and lands as a ``/N`` ``COSName``."""
    action = PDActionNamed()
    action.set_n(constant)

    assert action.get_n() == constant
    raw = action.get_cos_object().get_dictionary_object(_N)
    assert isinstance(raw, COSName)
    assert raw.name == constant


def test_named_constants_match_spec_strings() -> None:
    """The constants are spelled exactly as the PDF spec defines them —
    PDF readers do exact ``/N`` name matching."""
    assert PDActionNamed.NAMED_ACTION_NEXT_PAGE == "NextPage"
    assert PDActionNamed.NAMED_ACTION_PREV_PAGE == "PrevPage"
    assert PDActionNamed.NAMED_ACTION_FIRST_PAGE == "FirstPage"
    assert PDActionNamed.NAMED_ACTION_LAST_PAGE == "LastPage"


def test_named_set_n_none_clears_entry() -> None:
    """Passing ``None`` removes ``/N`` entirely."""
    action = PDActionNamed()
    action.set_n(PDActionNamed.NAMED_ACTION_NEXT_PAGE)
    assert action.get_cos_object().contains_key(_N)

    action.set_n(None)
    assert not action.get_cos_object().contains_key(_N)
    assert action.get_n() is None


# ---------- PDActionJavaScript ----------


def test_javascript_get_action_reads_cos_string_form() -> None:
    """``/JS`` written as a ``COSString`` (the simple text-string form)
    is returned verbatim."""
    action = PDActionJavaScript()
    action.get_cos_object().set_item(_JS, COSString("app.alert('hi');"))

    assert action.get_action() == "app.alert('hi');"


def test_javascript_get_action_reads_cos_stream_form() -> None:
    """``/JS`` may also be a ``COSStream`` (PDF 32000-1 §12.6.4.16); the
    decoded body is interpreted as UTF-8 source text."""
    source = "var x = 1 + 2;\nconsole.println(x);"
    js_stream = COSStream()
    js_stream.set_raw_data(source.encode("utf-8"))

    action = PDActionJavaScript()
    action.get_cos_object().set_item(_JS, js_stream)

    assert action.get_action() == source


def test_javascript_set_action_round_trips_through_cos_string() -> None:
    """``set_action`` writes a ``COSString`` and ``get_action`` reads it
    back unchanged."""
    action = PDActionJavaScript()
    action.set_action("this.print({bUI: true});")

    raw = action.get_cos_object().get_dictionary_object(_JS)
    assert isinstance(raw, COSString)
    assert raw.get_string() == "this.print({bUI: true});"
    assert action.get_action() == "this.print({bUI: true});"


def test_javascript_set_action_none_clears_entry() -> None:
    """``set_action(None)`` removes ``/JS`` and subsequent reads yield
    ``None``."""
    action = PDActionJavaScript()
    action.set_action("noop();")
    assert action.get_cos_object().contains_key(_JS)

    action.set_action(None)
    assert not action.get_cos_object().contains_key(_JS)
    assert action.get_action() is None


def test_javascript_get_action_missing_returns_none() -> None:
    """No ``/JS`` entry → ``get_action`` returns ``None``."""
    action = PDActionJavaScript()
    assert action.get_action() is None


def test_javascript_get_action_existing_dict_with_stream() -> None:
    """When wrapping a pre-existing dictionary whose ``/JS`` is a stream
    (the parsed-from-disk shape), ``get_action`` still decodes correctly."""
    src = "// long script body\nvar n = 42;"
    js_stream = COSStream()
    js_stream.set_raw_data(src.encode("utf-8"))

    raw_dict = COSDictionary()
    raw_dict.set_name("S", "JavaScript")
    raw_dict.set_item(_JS, js_stream)

    action = PDActionJavaScript(raw_dict)
    assert action.get_action() == src
