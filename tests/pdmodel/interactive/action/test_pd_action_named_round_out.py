"""Wave 242 round-out tests for ``PDActionNamed``.

Covers the predicate helpers (``is_next_page`` / ``is_prev_page`` /
``is_first_page`` / ``is_last_page`` / ``is_standard_named_action``) and
the ``STANDARD_NAMED_ACTIONS`` constant added on top of the upstream
``getN`` / ``setN`` surface."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import PDActionNamed

_N: COSName = COSName.get_pdf_name("N")


# ---------- STANDARD_NAMED_ACTIONS constant ----------


def test_standard_named_actions_contains_exactly_the_four_table_211_names() -> None:
    """The constant must hold exactly the four spec-required names — no
    more (extension names belong to viewers, not the spec) and no less."""
    assert frozenset(
        {"NextPage", "PrevPage", "FirstPage", "LastPage"}
    ) == PDActionNamed.STANDARD_NAMED_ACTIONS


def test_standard_named_actions_is_immutable_frozenset() -> None:
    """Storing the standard action list as a ``frozenset`` prevents callers
    from accidentally mutating the class-level constant — important since
    a single shared instance backs every ``PDActionNamed``."""
    assert isinstance(PDActionNamed.STANDARD_NAMED_ACTIONS, frozenset)
    with pytest.raises(AttributeError):
        # ``frozenset`` exposes no ``add``; ensure the type really blocks
        # mutation (would-be regression if someone swaps it for a plain set).
        PDActionNamed.STANDARD_NAMED_ACTIONS.add("Foo")  # type: ignore[attr-defined]


# ---------- per-action predicates ----------


@pytest.mark.parametrize(
    ("name", "expected_predicate"),
    [
        (PDActionNamed.NAMED_ACTION_NEXT_PAGE, "is_next_page"),
        (PDActionNamed.NAMED_ACTION_PREV_PAGE, "is_prev_page"),
        (PDActionNamed.NAMED_ACTION_FIRST_PAGE, "is_first_page"),
        (PDActionNamed.NAMED_ACTION_LAST_PAGE, "is_last_page"),
    ],
)
def test_predicate_is_true_only_for_matching_name(
    name: str, expected_predicate: str
) -> None:
    """Each predicate fires only for its own ``/N`` value; never for the
    other three standard names."""
    action = PDActionNamed()
    action.set_n(name)

    predicates = ["is_next_page", "is_prev_page", "is_first_page", "is_last_page"]
    for predicate in predicates:
        result = getattr(action, predicate)()
        assert result is (predicate == expected_predicate), (
            f"{predicate}() returned {result} for /N={name!r}"
        )


def test_predicates_all_false_when_n_missing() -> None:
    """A freshly-constructed ``PDActionNamed`` has no ``/N`` — every
    predicate must return ``False`` rather than raising."""
    action = PDActionNamed()
    # Ensure /N really is absent (no incidental default).
    action.set_n(None)

    assert action.is_next_page() is False
    assert action.is_prev_page() is False
    assert action.is_first_page() is False
    assert action.is_last_page() is False
    assert action.is_standard_named_action() is False


def test_predicates_all_false_for_extension_name() -> None:
    """PDF 1.5+ allows extension named actions (e.g. Acrobat's ``GoBack``).
    None of the standard predicates should match them — including
    :meth:`is_standard_named_action`."""
    action = PDActionNamed()
    action.set_n("GoBack")

    assert action.is_next_page() is False
    assert action.is_prev_page() is False
    assert action.is_first_page() is False
    assert action.is_last_page() is False
    assert action.is_standard_named_action() is False
    # …but the raw value still round-trips.
    assert action.get_n() == "GoBack"


def test_predicates_are_case_sensitive() -> None:
    """PDF names are case-sensitive (PDF 32000-1 §7.3.5). ``"nextpage"``
    is *not* the standard ``"NextPage"`` action — the predicate must
    not coerce."""
    action = PDActionNamed()
    action.set_n("nextpage")

    assert action.is_next_page() is False
    assert action.is_standard_named_action() is False


# ---------- is_standard_named_action ----------


@pytest.mark.parametrize(
    "name",
    [
        PDActionNamed.NAMED_ACTION_NEXT_PAGE,
        PDActionNamed.NAMED_ACTION_PREV_PAGE,
        PDActionNamed.NAMED_ACTION_FIRST_PAGE,
        PDActionNamed.NAMED_ACTION_LAST_PAGE,
    ],
)
def test_is_standard_named_action_true_for_each_table_211_constant(
    name: str,
) -> None:
    """All four Table 211 standard actions classify as standard."""
    action = PDActionNamed()
    action.set_n(name)

    assert action.is_standard_named_action() is True


def test_is_standard_named_action_false_for_empty_string() -> None:
    """An empty ``/N`` is invalid PDF but should not crash; classify it
    as non-standard rather than raising."""
    action = PDActionNamed()
    action.set_n("")

    assert action.is_standard_named_action() is False


def test_is_standard_named_action_reads_existing_dictionary() -> None:
    """When wrapping a parsed-from-disk dictionary, the predicate reads
    ``/N`` directly from the COS layer (no constructor-side defaults)."""
    raw = COSDictionary()
    raw.set_name("S", PDActionNamed.SUB_TYPE)
    raw.set_name(_N, "FirstPage")

    action = PDActionNamed(raw)

    assert action.is_first_page() is True
    assert action.is_standard_named_action() is True


# ---------- interaction with set_n / round-trip ----------


def test_set_n_then_predicate_then_clear_then_predicate() -> None:
    """Setting, clearing, and re-checking the predicate verifies the
    helper reads ``/N`` live rather than caching a snapshot."""
    action = PDActionNamed()

    action.set_n(PDActionNamed.NAMED_ACTION_LAST_PAGE)
    assert action.is_last_page() is True

    action.set_n(None)
    assert action.is_last_page() is False
    assert action.is_standard_named_action() is False

    action.set_n(PDActionNamed.NAMED_ACTION_FIRST_PAGE)
    assert action.is_first_page() is True
    assert action.is_last_page() is False


def test_predicate_does_not_mutate_dictionary() -> None:
    """Calling a read-only predicate must leave the underlying dictionary
    untouched — important for round-tripping pre-parsed PDFs."""
    action = PDActionNamed()
    action.set_n(PDActionNamed.NAMED_ACTION_NEXT_PAGE)
    keys_before = set(action.get_cos_object().key_set())

    # Call every predicate.
    action.is_next_page()
    action.is_prev_page()
    action.is_first_page()
    action.is_last_page()
    action.is_standard_named_action()

    keys_after = set(action.get_cos_object().key_set())
    assert keys_before == keys_after
    assert action.get_n() == PDActionNamed.NAMED_ACTION_NEXT_PAGE
