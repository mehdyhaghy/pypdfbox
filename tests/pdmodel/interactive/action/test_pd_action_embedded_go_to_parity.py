"""Parity tests for ``PDActionEmbeddedGoTo`` spec-named accessors —
``getDestination`` / ``setDestination``, ``getOpenInNewWindow`` /
``setOpenInNewWindow``, and ``getTargetDirectory`` /
``setTargetDirectory`` (PDF 32000-1 §12.6.4.4)."""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_target_directory import (
    PDTargetDirectory,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (
    PDPageFitDestination,
)

_NEW_WINDOW = COSName.get_pdf_name("NewWindow")
_D = COSName.get_pdf_name("D")
_T = COSName.get_pdf_name("T")


# ---------- /NewWindow ----------


def test_get_open_in_new_window_default_false_when_absent() -> None:
    """When ``/NewWindow`` is absent the spec default is ``False``."""
    action = PDActionEmbeddedGoTo()
    assert action.get_open_in_new_window() is False


def test_set_open_in_new_window_round_trip_true() -> None:
    """``set_open_in_new_window(True)`` is observable via the spec
    accessor and the legacy ``is_new_window`` accessor alike."""
    action = PDActionEmbeddedGoTo()
    action.set_open_in_new_window(True)
    assert action.get_open_in_new_window() is True
    assert action.is_new_window() is True
    # And visible on the underlying COSDictionary as a /NewWindow boolean.
    assert action.get_cos_object().get_boolean(_NEW_WINDOW, False) is True


def test_set_open_in_new_window_round_trip_false() -> None:
    """Setting ``False`` after ``True`` flips back."""
    action = PDActionEmbeddedGoTo()
    action.set_open_in_new_window(True)
    action.set_open_in_new_window(False)
    assert action.get_open_in_new_window() is False
    assert action.is_new_window() is False


def test_legacy_set_new_window_observable_via_spec_accessor() -> None:
    """The legacy ``set_new_window`` writes the same key the spec accessor
    reads — back-compat must hold."""
    action = PDActionEmbeddedGoTo()
    action.set_new_window(True)
    assert action.get_open_in_new_window() is True


# ---------- /D ----------


def test_get_destination_returns_same_kind_as_get_d() -> None:
    """``get_destination`` is an alias for ``get_d`` and dispatches the
    same wrapper subclass through ``PDDestination.create``."""
    action = PDActionEmbeddedGoTo()
    dest = PDPageFitDestination()
    dest.set_page_number(7)
    action.set_d(dest)

    via_legacy = action.get_d()
    via_spec = action.get_destination()
    assert via_legacy is not None
    assert via_spec is not None
    assert isinstance(via_spec, PDDestination)
    assert type(via_spec) is type(via_legacy)
    # Same underlying COS array — wrapper instances may differ but the
    # COS object backing them must be identical.
    assert via_spec.get_cos_object() is via_legacy.get_cos_object()


def test_set_destination_round_trip_named() -> None:
    """``set_destination(PDNamedDestination(...))`` round-trips through
    the spec getter."""
    action = PDActionEmbeddedGoTo()
    action.set_destination(PDNamedDestination("Chapter1"))
    got = action.get_destination()
    assert isinstance(got, PDNamedDestination)
    assert got.get_named_destination() == "Chapter1"


def test_set_destination_none_clears_d() -> None:
    """``set_destination(None)`` removes ``/D`` from the underlying dict."""
    action = PDActionEmbeddedGoTo()
    action.set_destination(PDPageFitDestination())
    assert action.get_cos_object().contains_key(_D)
    action.set_destination(None)
    assert not action.get_cos_object().contains_key(_D)
    assert action.get_destination() is None


# ---------- /T ----------


def test_get_target_directory_returns_same_wrapper_as_get_target() -> None:
    """``get_target_directory`` is an alias for ``get_target`` and wraps
    the same underlying COS dictionary."""
    action = PDActionEmbeddedGoTo()
    target = PDTargetDirectory()
    target.set_relationship("C")
    target.set_target_filename("child.pdf")
    action.set_target(target)

    via_legacy = action.get_target()
    via_spec = action.get_target_directory()
    assert via_legacy is not None
    assert via_spec is not None
    assert isinstance(via_spec, PDTargetDirectory)
    # Same backing COSDictionary — the wrapper instance may be a fresh
    # PDTargetDirectory each call, but it must point at the same dict.
    assert via_spec.get_cos_object() is via_legacy.get_cos_object()


def test_set_target_directory_round_trip() -> None:
    """``set_target_directory`` writes ``/T`` so ``get_target_directory``
    sees the same payload."""
    action = PDActionEmbeddedGoTo()
    target = PDTargetDirectory()
    target.set_relationship("P")
    target.set_target_filename("parent.pdf")
    action.set_target_directory(target)

    got = action.get_target_directory()
    assert got is not None
    rel = got.get_relationship()
    assert rel is not None and rel.get_name() == "P"
    assert got.get_target_filename() == "parent.pdf"


def test_set_target_directory_none_clears_t() -> None:
    """``set_target_directory(None)`` removes ``/T`` from the underlying
    dict."""
    action = PDActionEmbeddedGoTo()
    target = PDTargetDirectory()
    target.set_target_filename("child.pdf")
    action.set_target_directory(target)
    assert action.get_cos_object().contains_key(_T)

    action.set_target_directory(None)
    assert not action.get_cos_object().contains_key(_T)
    assert action.get_target_directory() is None


# ---------- set_destination validation ----------


def test_set_destination_rejects_page_object_form() -> None:
    """Per upstream ``PDActionEmbeddedGoTo.setDestination``, a page
    destination whose first array entry is a page object dictionary (not an
    integer page index) must be rejected — page references cannot cross
    documents in a /GoToE chain. Mirrors upstream's
    ``IllegalArgumentException``."""
    import pytest

    from pypdfbox.cos import COSDictionary

    action = PDActionEmbeddedGoTo()
    dest = PDPageFitDestination()
    # Direct page-object form — invalid for /GoToE.
    dest.set_page(COSDictionary())
    with pytest.raises(ValueError, match="must be an integer"):
        action.set_destination(dest)


def test_set_d_rejects_page_object_form_too() -> None:
    """``set_d`` is an alias of ``set_destination``; the same validation
    applies."""
    import pytest

    from pypdfbox.cos import COSDictionary

    action = PDActionEmbeddedGoTo()
    dest = PDPageFitDestination()
    dest.set_page(COSDictionary())
    with pytest.raises(ValueError, match="must be an integer"):
        action.set_d(dest)


def test_set_destination_accepts_integer_page_index() -> None:
    """A page destination with an integer page index is valid for /GoToE."""
    action = PDActionEmbeddedGoTo()
    dest = PDPageFitDestination()
    dest.set_page_number(3)
    # Should not raise.
    action.set_destination(dest)
    got = action.get_destination()
    assert got is not None
    assert isinstance(got, PDPageFitDestination)
    assert got.get_page_number() == 3


def test_set_destination_accepts_fresh_page_destination() -> None:
    """A fresh PDPageDestination (whose first array slot is COSNull) is
    treated as 'no page set yet' and accepted — matches upstream's behaviour
    on an empty destination array (where ``size() < 1`` skips validation)."""
    action = PDActionEmbeddedGoTo()
    # Fresh destination — no page assigned.
    action.set_destination(PDPageFitDestination())
    # Now clearable.
    action.set_destination(None)
    assert action.get_destination() is None


def test_set_destination_accepts_named_destination() -> None:
    """Named destinations (non-page-destination forms) bypass the integer
    check entirely."""
    action = PDActionEmbeddedGoTo()
    action.set_destination(PDNamedDestination("Chapter1"))
    got = action.get_destination()
    assert isinstance(got, PDNamedDestination)
    assert got.get_named_destination() == "Chapter1"


# ---------- predicates ----------


def test_has_file_false_on_fresh_action() -> None:
    """A fresh action has no ``/F`` entry — :meth:`has_file` reports
    ``False``."""
    action = PDActionEmbeddedGoTo()
    assert action.has_file() is False


def test_has_file_true_after_set_file_string() -> None:
    """After writing ``/F`` via the simple-string path, :meth:`has_file`
    reports ``True`` without needing to construct a file spec wrapper."""
    from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
        PDSimpleFileSpecification,
    )

    action = PDActionEmbeddedGoTo()
    spec = PDSimpleFileSpecification()
    spec.set_file("child.pdf")
    action.set_file(spec)
    assert action.has_file() is True


def test_has_file_false_after_clear() -> None:
    """``set_file(None)`` removes the entry — :meth:`has_file` flips back
    to ``False``."""
    from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
        PDSimpleFileSpecification,
    )

    action = PDActionEmbeddedGoTo()
    spec = PDSimpleFileSpecification()
    spec.set_file("child.pdf")
    action.set_file(spec)
    action.set_file(None)
    assert action.has_file() is False


def test_has_destination_false_on_fresh_action() -> None:
    """A fresh action has no ``/D`` — :meth:`has_destination` is
    ``False``."""
    action = PDActionEmbeddedGoTo()
    assert action.has_destination() is False


def test_has_destination_true_after_set_d() -> None:
    """Writing ``/D`` via the legacy or spec accessor flips
    :meth:`has_destination` to ``True``."""
    action = PDActionEmbeddedGoTo()
    dest = PDPageFitDestination()
    dest.set_page_number(1)
    action.set_d(dest)
    assert action.has_destination() is True


def test_has_destination_true_for_named_destination() -> None:
    """Named-destination form also makes :meth:`has_destination` ``True``
    (the predicate doesn't care about the COS form)."""
    action = PDActionEmbeddedGoTo()
    action.set_destination(PDNamedDestination("Chapter1"))
    assert action.has_destination() is True


def test_has_destination_false_after_clear() -> None:
    """``set_destination(None)`` flips :meth:`has_destination` back."""
    action = PDActionEmbeddedGoTo()
    action.set_destination(PDNamedDestination("X"))
    action.set_destination(None)
    assert action.has_destination() is False


def test_has_target_false_on_fresh_action() -> None:
    """A fresh action has no ``/T`` — :meth:`has_target` is ``False``."""
    action = PDActionEmbeddedGoTo()
    assert action.has_target() is False
    assert action.has_target_directory() is False


def test_has_target_true_after_set_target() -> None:
    """Writing ``/T`` via either accessor makes :meth:`has_target` /
    :meth:`has_target_directory` report ``True``."""
    action = PDActionEmbeddedGoTo()
    target = PDTargetDirectory()
    target.set_target_filename("child.pdf")
    action.set_target_directory(target)
    assert action.has_target() is True
    assert action.has_target_directory() is True


def test_has_target_false_for_non_dictionary_value() -> None:
    """Spec-invalid ``/T`` values (anything that isn't a COSDictionary)
    must report as absent — mirrors the ``getCOSDictionary`` shape used
    by :meth:`get_target_directory`."""
    from pypdfbox.cos import COSString

    action = PDActionEmbeddedGoTo()
    # Force a malformed /T entry (a COSString).
    action.get_cos_object().set_item(_T, COSString("oops"))
    assert action.has_target() is False
    # And :meth:`get_target_directory` agrees.
    assert action.get_target_directory() is None


def test_is_valid_true_on_fresh_action() -> None:
    """A fresh ``PDActionEmbeddedGoTo`` has ``/S = "GoToE"`` from the
    constructor — :meth:`is_valid` reports ``True``."""
    action = PDActionEmbeddedGoTo()
    assert action.is_valid() is True


def test_is_valid_false_when_subtype_mismatched() -> None:
    """Wrapping a ``COSDictionary`` whose ``/S`` is something other than
    ``"GoToE"`` makes :meth:`is_valid` report ``False``."""
    from pypdfbox.cos import COSDictionary

    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("S"), "GoTo")  # wrong subtype
    action = PDActionEmbeddedGoTo(raw)
    assert action.is_valid() is False


# ---------- OpenMode predicates ----------


def test_open_mode_predicates_default_user_preference() -> None:
    """A fresh action has no ``/NewWindow`` — only
    :meth:`is_open_in_user_preference` is ``True``."""
    action = PDActionEmbeddedGoTo()
    assert action.is_open_in_user_preference() is True
    assert action.is_open_in_new_window() is False
    assert action.is_open_in_same_window() is False


def test_open_mode_predicates_after_explicit_true() -> None:
    """Setting ``/NewWindow = true`` activates only
    :meth:`is_open_in_new_window`."""
    action = PDActionEmbeddedGoTo()
    action.set_open_in_new_window(True)
    assert action.is_open_in_new_window() is True
    assert action.is_open_in_same_window() is False
    assert action.is_open_in_user_preference() is False


def test_open_mode_predicates_after_explicit_false() -> None:
    """Setting ``/NewWindow = false`` activates only
    :meth:`is_open_in_same_window`."""
    action = PDActionEmbeddedGoTo()
    action.set_open_in_new_window(False)
    assert action.is_open_in_same_window() is True
    assert action.is_open_in_new_window() is False
    assert action.is_open_in_user_preference() is False


def test_open_mode_predicates_after_open_mode_user_preference() -> None:
    """``set_open_in_new_window(OpenMode.USER_PREFERENCE)`` removes the
    entry — :meth:`is_open_in_user_preference` flips back to ``True``."""
    from pypdfbox.pdmodel.interactive.action.open_mode import OpenMode

    action = PDActionEmbeddedGoTo()
    action.set_open_in_new_window(True)
    action.set_open_in_new_window(OpenMode.USER_PREFERENCE)
    assert action.is_open_in_user_preference() is True
    assert action.is_open_in_new_window() is False
    assert action.is_open_in_same_window() is False


def test_open_mode_predicates_after_open_mode_new_window() -> None:
    """``set_open_in_new_window(OpenMode.NEW_WINDOW)`` writes ``true``
    — :meth:`is_open_in_new_window` is ``True``."""
    from pypdfbox.pdmodel.interactive.action.open_mode import OpenMode

    action = PDActionEmbeddedGoTo()
    action.set_open_in_new_window(OpenMode.NEW_WINDOW)
    assert action.is_open_in_new_window() is True
    assert action.get_open_in_new_window_mode() is OpenMode.NEW_WINDOW


def test_open_mode_predicates_after_open_mode_same_window() -> None:
    """``set_open_in_new_window(OpenMode.SAME_WINDOW)`` writes ``false``
    — :meth:`is_open_in_same_window` is ``True``."""
    from pypdfbox.pdmodel.interactive.action.open_mode import OpenMode

    action = PDActionEmbeddedGoTo()
    action.set_open_in_new_window(OpenMode.SAME_WINDOW)
    assert action.is_open_in_same_window() is True
    assert action.get_open_in_new_window_mode() is OpenMode.SAME_WINDOW
