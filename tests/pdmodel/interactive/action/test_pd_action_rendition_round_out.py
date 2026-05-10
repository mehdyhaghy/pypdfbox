"""Round-out tests for ``PDActionRendition``.

Covers the Wave 244 additions: ``/OP`` operation constants and predicates,
``/JS`` COSStream support, and ``has_*`` presence helpers."""

from __future__ import annotations

from pypdfbox.cos import COSName, COSStream, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_rendition import (
    PDActionRendition,
)

_JS: COSName = COSName.get_pdf_name("JS")
_OP: COSName = COSName.get_pdf_name("OP")


# ---------- OP constants ----------


def test_op_constants_match_table_215() -> None:
    """PDF 32000-1 §12.6.4.13 Table 215 ordering: 0=PlayIfStopped, 1=Stop,
    2=Pause, 3=Resume, 4=Play."""
    assert PDActionRendition.OP_PLAY_IF_STOPPED == 0
    assert PDActionRendition.OP_STOP == 1
    assert PDActionRendition.OP_PAUSE == 2
    assert PDActionRendition.OP_RESUME == 3
    assert PDActionRendition.OP_PLAY == 4


# ---------- get_operation / has_op ----------


def test_get_operation_returns_none_when_absent() -> None:
    """Distinguishes 'absent' from 'set to 0', unlike ``get_op`` which
    returns the ``-1`` sentinel default of ``COSDictionary.get_int``."""
    action = PDActionRendition()
    assert action.get_operation() is None
    assert action.has_op() is False


def test_get_operation_returns_zero_when_explicitly_set() -> None:
    """An explicit ``/OP 0`` (PlayIfStopped) must surface as ``0``, not
    ``None`` — that's the whole point of the typed accessor."""
    action = PDActionRendition()
    action.set_op(PDActionRendition.OP_PLAY_IF_STOPPED)
    assert action.get_operation() == 0
    assert action.has_op() is True


def test_get_operation_round_trip_for_all_op_values() -> None:
    action = PDActionRendition()
    for op in (
        PDActionRendition.OP_PLAY_IF_STOPPED,
        PDActionRendition.OP_STOP,
        PDActionRendition.OP_PAUSE,
        PDActionRendition.OP_RESUME,
        PDActionRendition.OP_PLAY,
    ):
        action.set_op(op)
        assert action.get_operation() == op
        assert action.get_op() == op
        assert action.has_op() is True


# ---------- OP predicates ----------


def test_op_predicates_default_all_false_when_absent() -> None:
    """When ``/OP`` is absent every predicate returns ``False`` —
    ``get_operation`` returns ``None`` and ``None != 0..4``."""
    action = PDActionRendition()
    assert action.is_play_if_stopped() is False
    assert action.is_stop() is False
    assert action.is_pause() is False
    assert action.is_resume() is False
    assert action.is_play() is False


def test_op_predicates_only_one_true_per_value() -> None:
    """Each set value should activate exactly one predicate."""
    table = [
        (PDActionRendition.OP_PLAY_IF_STOPPED, "is_play_if_stopped"),
        (PDActionRendition.OP_STOP, "is_stop"),
        (PDActionRendition.OP_PAUSE, "is_pause"),
        (PDActionRendition.OP_RESUME, "is_resume"),
        (PDActionRendition.OP_PLAY, "is_play"),
    ]
    predicates = [name for _, name in table]
    for op, expected_true in table:
        action = PDActionRendition()
        action.set_op(op)
        for name in predicates:
            assert getattr(action, name)() is (name == expected_true), (
                f"OP={op}: predicate {name} returned wrong truth value"
            )


# ---------- get_js / has_js ----------


def test_get_js_returns_none_when_absent() -> None:
    action = PDActionRendition()
    assert action.get_js() is None
    assert action.has_js() is False


def test_get_js_returns_string_when_cos_string() -> None:
    action = PDActionRendition()
    action.set_js("app.alert('hi')")
    assert action.get_js() == "app.alert('hi')"
    assert action.has_js() is True


def test_get_js_unwraps_cos_stream() -> None:
    """``/JS`` may be a stream per PDF 32000-1 §12.6.4.16 — mirrors
    :class:`PDActionJavaScript.get_action` which falls back to
    ``COSStream.to_text_string()`` for streamed JS payloads."""
    action = PDActionRendition()
    stream = COSStream()
    payload = b"console.log('streamed JS payload');\n"
    with stream.create_output_stream() as out:
        out.write(payload)
    action.get_cos_object().set_item(_JS, stream)

    assert action.has_js() is True
    assert action.get_js() == payload.decode("utf-8")


def test_get_js_returns_none_for_unrecognised_type() -> None:
    """A nonsensical ``/JS`` entry (e.g. a name) must surface as ``None``,
    not raise — round-tripping through this class shouldn't tank on
    malformed input."""
    action = PDActionRendition()
    action.get_cos_object().set_item(_JS, COSName.get_pdf_name("Bogus"))
    assert action.get_js() is None
    # has_js still reports presence — we read the raw entry.
    assert action.has_js() is True


def test_set_js_none_clears_entry() -> None:
    action = PDActionRendition()
    action.set_js("noop;")
    assert action.has_js() is True
    action.set_js(None)
    assert action.has_js() is False
    assert action.get_js() is None


# ---------- has_op presence checks ----------


def test_has_op_true_for_explicit_zero() -> None:
    """Even ``/OP 0`` must register as present — ``has_op`` is purely a
    presence check, not a truthiness check."""
    action = PDActionRendition()
    action.set_op(0)
    assert action.has_op() is True


def test_has_op_after_setting_then_removing() -> None:
    """Setting ``/OP`` and then deleting the underlying entry round-trips
    through ``has_op`` correctly."""
    action = PDActionRendition()
    action.set_op(PDActionRendition.OP_STOP)
    assert action.has_op() is True
    action.get_cos_object().remove_item(_OP)
    assert action.has_op() is False
    assert action.get_operation() is None


# ---------- backward compat sanity ----------


def test_existing_get_op_default_unchanged() -> None:
    """``get_op`` keeps its legacy ``-1`` sentinel default to avoid
    breaking callers that already rely on that contract."""
    action = PDActionRendition()
    assert action.get_op() == -1


def test_get_js_with_cos_string_via_raw_set_item() -> None:
    """Equivalent to :func:`set_js` but via the raw COS path — the typed
    reader must still return the unwrapped string."""
    action = PDActionRendition()
    action.get_cos_object().set_item(_JS, COSString("var x = 1;"))
    assert action.get_js() == "var x = 1;"
