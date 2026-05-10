"""Wave 265 round-out tests for :class:`PDActionJavaScript` — predicate
helpers, payload-form classification, and clear-action surface."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.action import PDActionJavaScript

_JS: COSName = COSName.get_pdf_name("JS")
_S: COSName = COSName.get_pdf_name("S")


# ---------- SUB_TYPE constant ----------


def test_sub_type_constant_matches_spec() -> None:
    """The class-level ``SUB_TYPE`` constant is the spec name from PDF
    32000-1 §12.6.4.16 Table 217 — readers do exact ``/S`` name matching."""
    assert PDActionJavaScript.SUB_TYPE == "JavaScript"


def test_no_arg_constructor_writes_subtype_to_cos() -> None:
    """A no-arg construction lands ``/S = JavaScript`` on the underlying
    COS dictionary (the entry the spec uses to identify the action)."""
    action = PDActionJavaScript()

    raw = action.get_cos_object().get_dictionary_object(_S)
    assert isinstance(raw, COSName)
    assert raw.get_name() == "JavaScript"


def test_no_arg_constructor_writes_type_action() -> None:
    """The base ``PDAction.__init__`` chain seeds ``/Type = /Action`` for
    a freshly-constructed JavaScript action."""
    action = PDActionJavaScript()
    assert action.get_type() == "Action"


# ---------- string-payload constructor ----------


def test_string_constructor_seeds_subtype_and_payload() -> None:
    """``PDActionJavaScript(js: str)`` matches upstream's two-step
    constructor — first sets ``/S = JavaScript``, then writes the JS
    source to ``/JS``."""
    src = "app.alert('greetings');"
    action = PDActionJavaScript(src)

    assert action.get_sub_type() == "JavaScript"
    assert action.get_action() == src


def test_string_constructor_with_empty_source_still_writes_entry() -> None:
    """An empty ``str`` is still a valid payload — the COS entry exists
    but the decoded source is empty."""
    action = PDActionJavaScript("")

    assert action.has_action()
    assert action.get_action() == ""


# ---------- has_action / clear_action / is_empty ----------


def test_has_action_false_on_fresh_action() -> None:
    action = PDActionJavaScript()
    assert action.has_action() is False


def test_has_action_true_when_string_set() -> None:
    action = PDActionJavaScript()
    action.set_action("var x = 1;")
    assert action.has_action() is True


def test_has_action_true_when_stream_set() -> None:
    """``has_action`` reports presence regardless of whether ``/JS`` is a
    string or a stream — it does not decode."""
    action = PDActionJavaScript()
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"console.log(1);")
    action.get_cos_object().set_item(_JS, stream)

    assert action.has_action() is True


def test_has_action_false_when_payload_unexpected_type_but_present() -> None:
    """A non-string, non-stream ``/JS`` entry still counts as present —
    the spec only sanctions string/stream forms but ``has_action`` is a
    raw entry-presence check (use :meth:`is_string_payload` /
    :meth:`is_stream_payload` to discriminate by type)."""
    action = PDActionJavaScript()
    action.get_cos_object().set_item(_JS, COSName.get_pdf_name("Bogus"))
    assert action.has_action() is True


def test_clear_action_removes_string_entry() -> None:
    action = PDActionJavaScript()
    action.set_action("a();")
    assert action.has_action()

    action.clear_action()
    assert action.has_action() is False
    assert action.get_action() is None


def test_clear_action_removes_stream_entry() -> None:
    action = PDActionJavaScript()
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"x();")
    action.get_cos_object().set_item(_JS, stream)
    assert action.has_action()

    action.clear_action()
    assert action.has_action() is False


def test_clear_action_idempotent_when_already_absent() -> None:
    """Calling :meth:`clear_action` on a fresh action is a no-op rather
    than an error."""
    action = PDActionJavaScript()
    action.clear_action()
    action.clear_action()
    assert action.has_action() is False


def test_is_empty_true_when_js_absent() -> None:
    action = PDActionJavaScript()
    assert action.is_empty() is True


def test_is_empty_true_when_source_is_empty_string() -> None:
    """An empty-string ``/JS`` (a present but empty payload) reports as
    empty — the action does nothing."""
    action = PDActionJavaScript("")
    assert action.has_action() is True  # entry exists
    assert action.is_empty() is True   # but no executable source


def test_is_empty_false_when_source_present() -> None:
    action = PDActionJavaScript("doSomething();")
    assert action.is_empty() is False


def test_is_empty_true_for_unexpected_payload_type() -> None:
    """A ``/JS`` entry stored as e.g. a ``COSName`` (spec-invalid) decodes
    to ``None`` from :meth:`get_action`, so ``is_empty`` returns ``True``."""
    action = PDActionJavaScript()
    action.get_cos_object().set_item(_JS, COSName.get_pdf_name("Surprise"))
    assert action.is_empty() is True


# ---------- payload-form predicates ----------


def test_is_string_payload_true_for_set_action() -> None:
    action = PDActionJavaScript()
    action.set_action("alert(1);")
    assert action.is_string_payload() is True
    assert action.is_stream_payload() is False


def test_is_stream_payload_true_for_stream_entry() -> None:
    action = PDActionJavaScript()
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"alert(2);")
    action.get_cos_object().set_item(_JS, stream)

    assert action.is_stream_payload() is True
    assert action.is_string_payload() is False


def test_payload_form_predicates_false_when_absent() -> None:
    action = PDActionJavaScript()
    assert action.is_string_payload() is False
    assert action.is_stream_payload() is False


def test_payload_form_predicates_false_for_unexpected_type() -> None:
    """Both predicates reject a non-string, non-stream ``/JS`` entry."""
    action = PDActionJavaScript()
    action.get_cos_object().set_item(_JS, COSName.get_pdf_name("Bogus"))

    assert action.is_string_payload() is False
    assert action.is_stream_payload() is False


# ---------- is_valid ----------


def test_is_valid_true_for_default_construction() -> None:
    action = PDActionJavaScript()
    assert action.is_valid() is True


def test_is_valid_false_when_subtype_overwritten() -> None:
    action = PDActionJavaScript()
    action.set_sub_type("Wibble")
    assert action.is_valid() is False


def test_is_valid_round_trips_through_existing_dict() -> None:
    """Wrapping a hand-built dictionary with ``/S = JavaScript`` reports
    valid — even when no payload is set."""
    raw = COSDictionary()
    raw.set_name(_S, "JavaScript")
    action = PDActionJavaScript(raw)
    assert action.is_valid() is True


def test_is_valid_false_for_dict_missing_subtype() -> None:
    """A blank dictionary wrapped via the ``COSDictionary`` constructor
    keeps no ``/S`` entry — the existing-dict ctor branch does *not*
    seed the subtype (mirrors upstream ``PDActionJavaScript(COSDictionary)``
    which calls ``super(a)`` and does not re-set ``/S``)."""
    raw = COSDictionary()
    action = PDActionJavaScript(raw)
    assert action.is_valid() is False
