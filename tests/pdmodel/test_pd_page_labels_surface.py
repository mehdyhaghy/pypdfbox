from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel import (
    PDDocument,
    PDPage,
    PDPageLabelRange,
    PDPageLabels,
)


def _doc_with_pages(n: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n):
        doc.add_page(PDPage())
    return doc


# ---------- PDPageLabelRange.is_valid_style ----------


def test_is_valid_style_accepts_all_five_codes() -> None:
    """All five PDF 32000-1 Table 159 codes are valid."""
    for code in (
        PDPageLabelRange.STYLE_DECIMAL,
        PDPageLabelRange.STYLE_ROMAN_UPPER,
        PDPageLabelRange.STYLE_ROMAN_LOWER,
        PDPageLabelRange.STYLE_LETTERS_UPPER,
        PDPageLabelRange.STYLE_LETTERS_LOWER,
    ):
        assert PDPageLabelRange.is_valid_style(code) is True


def test_is_valid_style_rejects_unknown_and_none() -> None:
    """Unknown codes and ``None`` are not valid styles. ``None`` is the
    "absence of /S" sentinel, distinct from a valid style code."""
    assert PDPageLabelRange.is_valid_style(None) is False
    assert PDPageLabelRange.is_valid_style("") is False
    assert PDPageLabelRange.is_valid_style("X") is False
    # Case-sensitive — upstream lookup is exact-match.
    assert PDPageLabelRange.is_valid_style("d") is False
    assert PDPageLabelRange.is_valid_style("DR") is False


def test_is_valid_style_predicate_matches_set_style_acceptance() -> None:
    """The predicate is consistent with :meth:`set_style`'s validation —
    every code accepted by ``is_valid_style`` is also accepted by
    ``set_style`` and vice versa."""
    r = PDPageLabelRange()
    for code in ("D", "R", "r", "A", "a", "X", "z", "DD"):
        if PDPageLabelRange.is_valid_style(code):
            r.set_style(code)
            assert r.get_style() == code
        else:
            with pytest.raises(ValueError):
                r.set_style(code)


# ---------- PDPageLabels.is_default_only ----------


def test_is_default_only_on_fresh_instance() -> None:
    """A freshly constructed PDPageLabels has the implicit default range
    at index 0 with style /D and no /St entry — it counts as default-only."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    assert labels.is_default_only() is True


def test_is_default_only_false_after_adding_extra_range() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(2, style=PDPageLabels.STYLE_DECIMAL)
    assert labels.is_default_only() is False


def test_is_default_only_false_after_modifying_default_style() -> None:
    """Same range count, but the style at 0 was changed → no longer the
    untouched implicit default."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(0, style=PDPageLabels.STYLE_ROMAN_LOWER)
    assert labels.is_default_only() is False


def test_is_default_only_false_when_default_has_prefix() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    only = labels.get_page_label_range(0)
    assert only is not None
    only.set_prefix("Pre-")
    assert labels.is_default_only() is False


def test_is_default_only_false_when_default_has_explicit_start() -> None:
    """Setting /St explicitly (even to 1) is a deviation from the implicit
    default — the persisted dictionary differs from a default-only one."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    only = labels.get_page_label_range(0)
    assert only is not None
    only.set_start(1)
    assert labels.is_default_only() is False


def test_is_default_only_false_after_clear() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.clear_label_ranges()
    # No ranges at all — definitely not "default-only".
    assert labels.is_default_only() is False


# ---------- PDPageLabels.clear_label_ranges ----------


def test_clear_label_ranges_empties_dict() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(2, style=PDPageLabels.STYLE_DECIMAL)
    labels.set_label_range(5, style=PDPageLabels.STYLE_ROMAN_LOWER)
    assert labels.get_page_range_count() == 3
    labels.clear_label_ranges()
    assert labels.get_page_range_count() == 0
    assert labels.has_label_range(0) is False
    assert labels.get_first_page_index() is None
    assert labels.get_last_page_index() is None


def test_clear_label_ranges_idempotent() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.clear_label_ranges()
    # Calling again is a no-op.
    labels.clear_label_ranges()
    assert labels.get_page_range_count() == 0


def test_clear_then_repopulate() -> None:
    doc = _doc_with_pages(2)
    labels = PDPageLabels(doc)
    labels.clear_label_ranges()
    labels.set_label_range(0, style=PDPageLabels.STYLE_ROMAN_LOWER)
    out = labels.get_labels_by_page_indices()
    assert out == ["i", "ii"]


# ---------- PDPageLabels.__len__ / __contains__ ----------


def test_len_matches_page_range_count() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    assert len(labels) == labels.get_page_range_count() == 1
    labels.set_label_range(2, style=PDPageLabels.STYLE_DECIMAL)
    assert len(labels) == 2
    labels.clear_label_ranges()
    assert len(labels) == 0


def test_contains_int_is_alias_for_has_label_range() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    assert 0 in labels
    assert 1 not in labels
    labels.set_label_range(7, style=PDPageLabels.STYLE_DECIMAL)
    assert 7 in labels


def test_contains_rejects_non_int_keys_silently() -> None:
    """Non-int keys (string, float, bool) return ``False`` — matches
    Python's tolerant ``in`` semantics for containers."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    assert "0" not in labels  # type: ignore[operator]
    assert 0.0 not in labels  # type: ignore[operator]
    # bool is technically a subclass of int — make sure it doesn't
    # accidentally match index 0/1 just because of that subtype quirk.
    assert False not in labels  # type: ignore[operator]
    assert True not in labels  # type: ignore[operator]


def test_contains_after_remove() -> None:
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.set_label_range(3, style=PDPageLabels.STYLE_DECIMAL)
    assert 3 in labels
    labels.remove_label_range(3)
    assert 3 not in labels


# ---------- Cross-check: serialised /Nums shape after surface ops ----------


def test_clear_then_add_serialises_to_one_pair() -> None:
    """clear + single-range add produces a /Nums array with exactly one
    (key, value) pair when serialised — proves the in-memory state is the
    sole source of truth for ``get_cos_object``."""
    doc = _doc_with_pages(0)
    labels = PDPageLabels(doc)
    labels.clear_label_ranges()
    labels.set_label_range(0, style=PDPageLabels.STYLE_ROMAN_UPPER)
    serialised = labels.get_cos_object()
    assert isinstance(serialised, COSDictionary)
    from pypdfbox.cos import COSArray, COSName

    nums = serialised.get_dictionary_object(COSName.get_pdf_name("Nums"))
    assert isinstance(nums, COSArray)
    # One range → one (int, dict) pair → 2 entries.
    assert nums.size() == 2
