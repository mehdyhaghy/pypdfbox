"""Round-out coverage for :class:`PDActionMovie` — Wave 222.

Targets the 2026-spec gaps not exercised by ``test_pd_action_typed_extras``:
``/Operation`` constants and predicates, default-when-absent semantics
(PDF 32000-1 §12.6.4.10 Table 209), and the ``has_annotation`` /
``has_title`` mutual-exclusivity helpers."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_movie import PDActionMovie

# ---------- /Operation constants ----------


def test_operation_constants_match_spec() -> None:
    """Operation constants are the four name strings from Table 209."""
    assert PDActionMovie.OPERATION_PLAY == "Play"
    assert PDActionMovie.OPERATION_STOP == "Stop"
    assert PDActionMovie.OPERATION_PAUSE == "Pause"
    assert PDActionMovie.OPERATION_RESUME == "Resume"


# ---------- get_operation / get_effective_operation ----------


def test_get_operation_returns_none_when_absent() -> None:
    """Raw accessor reports absence (does not apply the spec default)."""
    action = PDActionMovie()
    assert action.get_operation() is None


def test_get_effective_operation_defaults_to_play_when_absent() -> None:
    """``/Operation`` defaults to ``"Play"`` per PDF 32000-1 Table 209."""
    action = PDActionMovie()
    assert action.get_effective_operation() == PDActionMovie.OPERATION_PLAY
    assert action.get_effective_operation() == "Play"


def test_get_effective_operation_returns_explicit_value_when_present() -> None:
    """Explicit ``/Operation`` is returned verbatim — default does not
    shadow a stored value."""
    action = PDActionMovie()
    action.set_operation(PDActionMovie.OPERATION_STOP)
    assert action.get_effective_operation() == "Stop"


def test_set_operation_round_trip_with_constants() -> None:
    """Each spec constant survives a round-trip through ``set_operation``."""
    action = PDActionMovie()
    for value in (
        PDActionMovie.OPERATION_PLAY,
        PDActionMovie.OPERATION_STOP,
        PDActionMovie.OPERATION_PAUSE,
        PDActionMovie.OPERATION_RESUME,
    ):
        action.set_operation(value)
        assert action.get_operation() == value
        assert action.get_effective_operation() == value


def test_set_operation_none_clears_entry() -> None:
    """Passing ``None`` removes ``/Operation`` and re-engages the default."""
    action = PDActionMovie()
    action.set_operation(PDActionMovie.OPERATION_PAUSE)
    assert action.get_operation() == "Pause"

    action.set_operation(None)
    assert action.get_operation() is None
    assert action.get_effective_operation() == PDActionMovie.OPERATION_PLAY
    # Underlying entry is gone (not stored as a null).
    assert (
        action.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Operation")
        )
        is None
    )


# ---------- /Operation predicates ----------


def test_is_play_true_when_operation_absent() -> None:
    """Absence implies the spec default ``"Play"`` — :meth:`is_play`
    follows :meth:`get_effective_operation`."""
    action = PDActionMovie()
    assert action.is_play() is True
    assert action.is_stop() is False
    assert action.is_pause() is False
    assert action.is_resume() is False


def test_is_play_true_when_operation_explicit_play() -> None:
    action = PDActionMovie()
    action.set_operation(PDActionMovie.OPERATION_PLAY)
    assert action.is_play() is True
    assert action.is_stop() is False


def test_predicate_helpers_each_match_their_operation() -> None:
    """Each predicate is exclusively true for its own operation; the
    others return ``False`` (excluding :meth:`is_play` which is also
    ``True`` when /Operation is absent — covered separately)."""
    action = PDActionMovie()

    action.set_operation(PDActionMovie.OPERATION_STOP)
    assert action.is_stop() is True
    assert action.is_play() is False
    assert action.is_pause() is False
    assert action.is_resume() is False

    action.set_operation(PDActionMovie.OPERATION_PAUSE)
    assert action.is_pause() is True
    assert action.is_play() is False
    assert action.is_stop() is False
    assert action.is_resume() is False

    action.set_operation(PDActionMovie.OPERATION_RESUME)
    assert action.is_resume() is True
    assert action.is_play() is False
    assert action.is_stop() is False
    assert action.is_pause() is False


def test_unknown_operation_value_makes_all_predicates_false() -> None:
    """A non-spec ``/Operation`` value (malformed PDF) should not match
    any of the typed predicates — including :meth:`is_play`, since the
    entry is present but not equal to ``"Play"``."""
    action = PDActionMovie()
    action.set_operation("Rewind")  # not in Table 209
    assert action.is_play() is False
    assert action.is_stop() is False
    assert action.is_pause() is False
    assert action.is_resume() is False
    # Effective op echoes the stored value verbatim (no normalisation).
    assert action.get_effective_operation() == "Rewind"


# ---------- has_annotation / has_title ----------


def test_has_annotation_and_has_title_both_false_when_empty() -> None:
    """A bare Movie action targets neither — both helpers report ``False``."""
    action = PDActionMovie()
    assert action.has_annotation() is False
    assert action.has_title() is False


def test_has_annotation_true_when_dict_present() -> None:
    """A dictionary in ``/Annotation`` flips the predicate to ``True``."""
    action = PDActionMovie()
    action.set_annotation(COSDictionary())
    assert action.has_annotation() is True
    assert action.has_title() is False


def test_has_title_true_when_t_present() -> None:
    """A non-empty ``/T`` flips the predicate to ``True``; absent /Annotation
    keeps :meth:`has_annotation` ``False``."""
    action = PDActionMovie()
    action.set_t("Intro")
    assert action.has_title() is True
    assert action.has_annotation() is False


def test_has_annotation_false_after_clear() -> None:
    """Clearing ``/Annotation`` flips the predicate back."""
    action = PDActionMovie()
    action.set_annotation(COSDictionary())
    assert action.has_annotation() is True

    action.set_annotation(None)
    assert action.has_annotation() is False


def test_has_title_false_after_clear() -> None:
    """Setting ``/T`` to ``None`` removes the entry."""
    action = PDActionMovie()
    action.set_t("Trailer")
    assert action.has_title() is True

    action.set_t(None)
    assert action.has_title() is False


def test_has_annotation_and_title_can_both_be_true() -> None:
    """The spec marks ``/Annotation`` and ``/T`` as alternative addressing
    forms but allows malformed PDFs to set both. The helpers report what
    is *present* — they do not enforce mutual exclusivity (matching
    PDFBox's tolerant parsing posture)."""
    action = PDActionMovie()
    action.set_annotation(COSDictionary())
    action.set_t("Intro")

    assert action.has_annotation() is True
    assert action.has_title() is True
