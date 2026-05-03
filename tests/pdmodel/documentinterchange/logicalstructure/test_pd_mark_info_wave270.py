"""Wave 270 — pdmodel/documentinterchange/logicalstructure/PDMarkInfo
cold-gap round-out.

Covers the new presence predicates (``has_marked``, ``has_user_properties``,
``has_suspects``), per-key ``clear_*`` helpers, the ``is_tagged`` alias for
:meth:`is_marked`, the ``is_empty`` aggregate predicate, and ``__repr__``.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_mark_info import (
    PDMarkInfo,
)


# ---------- has_* presence predicates ----------


def test_has_marked_false_on_default_wave270() -> None:
    info = PDMarkInfo()
    assert not info.has_marked()
    # Reading is_marked() should still resolve to the spec default.
    assert info.is_marked() is False


def test_has_marked_true_after_set_true_wave270() -> None:
    info = PDMarkInfo()
    info.set_marked(True)
    assert info.has_marked()
    assert info.is_marked() is True


def test_has_marked_true_after_set_false_wave270() -> None:
    """Explicitly writing ``False`` still counts as "present" — the
    predicate distinguishes "absent (default false)" from "present and
    set to false"."""
    info = PDMarkInfo()
    info.set_marked(False)
    assert info.has_marked()
    assert info.is_marked() is False


def test_has_user_properties_false_on_default_wave270() -> None:
    info = PDMarkInfo()
    assert not info.has_user_properties()


def test_has_user_properties_true_after_set_wave270() -> None:
    info = PDMarkInfo()
    info.set_user_properties(True)
    assert info.has_user_properties()


def test_has_suspects_false_on_default_wave270() -> None:
    info = PDMarkInfo()
    assert not info.has_suspects()


def test_has_suspects_true_after_set_wave270() -> None:
    info = PDMarkInfo()
    info.set_suspects(True)
    assert info.has_suspects()


# ---------- clear_* helpers ----------


def test_clear_marked_removes_entry_wave270() -> None:
    info = PDMarkInfo()
    info.set_marked(True)
    info.clear_marked()
    assert not info.has_marked()
    # Falls back to the spec default.
    assert info.is_marked() is False
    assert not info.get_cos_object().contains_key(COSName.get_pdf_name("Marked"))


def test_clear_marked_on_absent_is_noop_wave270() -> None:
    info = PDMarkInfo()
    info.clear_marked()
    assert not info.has_marked()


def test_clear_user_properties_removes_entry_wave270() -> None:
    info = PDMarkInfo()
    info.set_user_properties(True)
    info.clear_user_properties()
    assert not info.has_user_properties()
    assert info.uses_user_properties() is False


def test_clear_suspects_removes_entry_wave270() -> None:
    info = PDMarkInfo()
    info.set_suspects(True)
    info.clear_suspects()
    assert not info.has_suspects()
    assert info.is_suspects() is False
    assert info.is_suspect() is False


# ---------- is_tagged alias ----------


def test_is_tagged_matches_is_marked_default_wave270() -> None:
    info = PDMarkInfo()
    assert info.is_tagged() is False
    assert info.is_tagged() == info.is_marked()


def test_is_tagged_matches_is_marked_after_set_wave270() -> None:
    info = PDMarkInfo()
    info.set_marked(True)
    assert info.is_tagged() is True
    assert info.is_tagged() == info.is_marked()


# ---------- is_empty ----------


def test_is_empty_on_default_constructor_wave270() -> None:
    info = PDMarkInfo()
    assert info.is_empty()


def test_is_empty_false_after_set_marked_wave270() -> None:
    info = PDMarkInfo()
    info.set_marked(True)
    assert not info.is_empty()


def test_is_empty_true_again_after_clear_all_wave270() -> None:
    info = PDMarkInfo()
    info.set_marked(True)
    info.set_user_properties(True)
    info.set_suspects(True)
    assert not info.is_empty()
    info.clear_marked()
    info.clear_user_properties()
    info.clear_suspects()
    assert info.is_empty()


# ---------- repr ----------


def test_repr_includes_all_three_flags_wave270() -> None:
    info = PDMarkInfo()
    info.set_marked(True)
    text = repr(info)
    assert text.startswith("PDMarkInfo(")
    assert "marked=True" in text
    assert "user_properties=False" in text
    assert "suspects=False" in text


# ---------- direct dict construction still works ----------


def test_direct_dict_is_seen_by_predicates_wave270() -> None:
    """Constructing PDMarkInfo over an existing populated COSDictionary
    must still surface presence predicates correctly — confirm the new
    helpers respect the wrapped dictionary rather than only the
    setter-driven path."""
    raw = COSDictionary()
    raw.set_boolean(COSName.get_pdf_name("Marked"), True)
    info = PDMarkInfo(raw)
    assert info.has_marked()
    assert info.is_tagged()
    assert not info.has_user_properties()
    assert not info.has_suspects()
