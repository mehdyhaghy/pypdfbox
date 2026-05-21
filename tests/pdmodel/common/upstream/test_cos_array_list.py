"""Ported from upstream PDFBox 3.0
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/COSArrayListTest.java``.

Verifies the bidirectional sync between a :class:`COSArrayList`'s view list
and its backing :class:`COSArray`.

Skipped/adapted notes:

* The two ``removeFrom*FilteredList*`` tests rely on the upstream contract
  that ``PDPage.getAnnotations(filter)`` returns a *filtered* (read-only)
  :class:`COSArrayList` instance. pypdfbox's ``get_annotations`` returns a
  plain Python ``list`` instead, so we exercise the same read-only guard
  by constructing the filtered :class:`COSArrayList` directly with the
  shape upstream's ``PDPage.getAnnotations(AnnotationFilter)`` produces
  (sub-list view + full backing array, so ``len(actual) != array.size()``
  -> ``is_filtered`` set).
* The two ``remove{Single,Indirect}Object`` round-trip tests reload the
  saved file through ``Loader.loadPDF`` to assert that ``get_annotations``
  still returns a ``COSArrayList`` after parsing. pypdfbox's
  ``get_annotations`` returns a plain ``list`` (the COSArrayList wrapper
  is constructed lazily by callers that need it), so we skip the
  load-side assertions and exercise the same delete semantics on a
  freshly-constructed wrapper.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray
from pypdfbox.pdmodel.common.cos_array_list import COSArrayList
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationCircle,
    PDAnnotationHighlight,
    PDAnnotationLink,
    PDAnnotationSquare,
)
from pypdfbox.pdmodel.pd_page import PDPage

# ---------------------------------------------------------------------------
# fixtures — mirror upstream ``@BeforeEach setUp()`` (Java lines 64-109).
# ---------------------------------------------------------------------------


@pytest.fixture
def annotations_setup() -> dict[str, object]:
    """Build four annotations (txt-mark, txt-link, a-circle, txt-link
    again) into both a Python list + ``COSArray`` and the parallel
    "to-be-compared" copies. Returns a dict so tests can pull just what
    they need."""
    txt_mark = PDAnnotationHighlight()
    txt_link = PDAnnotationLink()
    a_circle = PDAnnotationCircle()

    annotations_list = [txt_mark, txt_link, a_circle, txt_link]
    assert len(annotations_list) == 4

    tbc_annotations_list = [txt_mark, txt_link, a_circle, txt_link]
    assert len(tbc_annotations_list) == 4

    annotations_array = COSArray()
    annotations_array.add(txt_mark.get_cos_object())
    annotations_array.add(txt_link.get_cos_object())
    annotations_array.add(a_circle.get_cos_object())
    annotations_array.add(txt_link.get_cos_object())
    assert annotations_array.size() == 4

    tbc_annotations_array = [
        txt_mark.get_cos_object(),
        txt_link.get_cos_object(),
        a_circle.get_cos_object(),
        txt_link.get_cos_object(),
    ]
    assert len(tbc_annotations_array) == 4

    pd_page = PDPage()
    pd_page.set_annotations(annotations_list)

    return {
        "txt_mark": txt_mark,
        "txt_link": txt_link,
        "a_circle": a_circle,
        "annotations_list": annotations_list,
        "tbc_annotations_list": tbc_annotations_list,
        "annotations_array": annotations_array,
        "tbc_annotations_array": tbc_annotations_array,
        "pd_page": pd_page,
    }


# ---------------------------------------------------------------------------
# read-only sync — mirrors upstream ``getFromList`` (Java lines 114-131).
# ---------------------------------------------------------------------------


def test_get_from_list(annotations_setup: dict[str, object]) -> None:
    """Test getting a PDModel element is in sync with underlying COSArray."""
    annotations_list = annotations_setup["annotations_list"]
    annotations_array = annotations_setup["annotations_array"]
    tbc_annotations_list = annotations_setup["tbc_annotations_list"]
    tbc_annotations_array = annotations_setup["tbc_annotations_array"]

    cos_array_list: COSArrayList = COSArrayList(
        annotations_list,  # type: ignore[arg-type]
        annotations_array,  # type: ignore[arg-type]
    )

    for i in range(cos_array_list.size()):
        annot = cos_array_list.get(i)
        assert annotations_array.get(i) is annot.get_cos_object()  # type: ignore[index, attr-defined]
        # compare with the parallel "to be compared" list/array
        assert tbc_annotations_list[i] is annot  # type: ignore[index]
        assert tbc_annotations_array[i] is annot.get_cos_object()  # type: ignore[index, attr-defined]


# ---------------------------------------------------------------------------
# remove-by-index — mirrors upstream ``removeFromListByIndex``
# (Java lines 159-175).
# ---------------------------------------------------------------------------


def test_remove_from_list_by_index(annotations_setup: dict[str, object]) -> None:
    annotations_list = annotations_setup["annotations_list"]
    annotations_array = annotations_setup["annotations_array"]
    tbc_annotations_list = annotations_setup["tbc_annotations_list"]
    tbc_annotations_array = annotations_setup["tbc_annotations_array"]

    cos_array_list: COSArrayList = COSArrayList(
        annotations_list,  # type: ignore[arg-type]
        annotations_array,  # type: ignore[arg-type]
    )

    position_to_remove = 2
    to_be_removed = cos_array_list.get(position_to_remove)

    assert cos_array_list.remove(position_to_remove) is to_be_removed
    assert cos_array_list.size() == 3
    assert annotations_array.size() == 3  # type: ignore[attr-defined]

    assert (
        cos_array_list.index_of(tbc_annotations_list[position_to_remove])  # type: ignore[index]
        == -1
    )
    assert (
        annotations_array.index_of(tbc_annotations_array[position_to_remove]) == -1  # type: ignore[attr-defined, index]
    )


# ---------------------------------------------------------------------------
# remove-by-object (unique) — mirrors upstream ``removeUniqueFromListByObject``
# (Java lines 182-208).
# ---------------------------------------------------------------------------


def test_remove_unique_from_list_by_object(
    annotations_setup: dict[str, object],
) -> None:
    annotations_list = annotations_setup["annotations_list"]
    annotations_array = annotations_setup["annotations_array"]
    tbc_annotations_list = annotations_setup["tbc_annotations_list"]
    tbc_annotations_array = annotations_setup["tbc_annotations_array"]

    cos_array_list: COSArrayList = COSArrayList(
        annotations_list,  # type: ignore[arg-type]
        annotations_array,  # type: ignore[arg-type]
    )

    position_to_remove = 2
    to_be_removed = annotations_list[position_to_remove]  # type: ignore[index]

    assert cos_array_list.remove(to_be_removed) is True
    assert cos_array_list.size() == 3
    assert annotations_array.size() == 3  # type: ignore[attr-defined]

    # List object at index 3 has shifted down to position 2.
    assert cos_array_list.get(2) is tbc_annotations_list[3]  # type: ignore[index]
    assert (
        annotations_array.get(2)  # type: ignore[attr-defined]
        is tbc_annotations_list[3].get_cos_object()  # type: ignore[index, attr-defined]
    )
    assert annotations_array.get(2) is tbc_annotations_array[3]  # type: ignore[attr-defined, index]

    assert (
        cos_array_list.index_of(tbc_annotations_list[position_to_remove])  # type: ignore[index]
        == -1
    )
    assert (
        annotations_array.index_of(tbc_annotations_array[position_to_remove]) == -1  # type: ignore[attr-defined, index]
    )

    # Second remove of an already-removed object returns False.
    assert cos_array_list.remove(to_be_removed) is False


# ---------------------------------------------------------------------------
# remove-all (unique) — mirrors upstream ``removeAllUniqueFromListByObject``
# (Java lines 215-231).
# ---------------------------------------------------------------------------


def test_remove_all_unique_from_list_by_object(
    annotations_setup: dict[str, object],
) -> None:
    annotations_list = annotations_setup["annotations_list"]
    annotations_array = annotations_setup["annotations_array"]

    cos_array_list: COSArrayList = COSArrayList(
        annotations_list,  # type: ignore[arg-type]
        annotations_array,  # type: ignore[arg-type]
    )

    position_to_remove = 2
    to_be_removed = annotations_list[position_to_remove]  # type: ignore[index]

    to_be_removed_instances = [to_be_removed]

    assert cos_array_list.remove_all(to_be_removed_instances) is True
    assert cos_array_list.size() == 3
    assert annotations_array.size() == 3  # type: ignore[attr-defined]

    assert cos_array_list.remove_all(to_be_removed_instances) is False


# ---------------------------------------------------------------------------
# remove-by-object (multiple) — mirrors upstream ``removeMultipleFromListByObject``
# (Java lines 238-252).
# ---------------------------------------------------------------------------


def test_remove_multiple_from_list_by_object(
    annotations_setup: dict[str, object],
) -> None:
    annotations_list = annotations_setup["annotations_list"]
    annotations_array = annotations_setup["annotations_array"]
    tbc_annotations_list = annotations_setup["tbc_annotations_list"]

    cos_array_list: COSArrayList = COSArrayList(
        annotations_list,  # type: ignore[arg-type]
        annotations_array,  # type: ignore[arg-type]
    )

    position_to_remove = 1
    to_be_removed = tbc_annotations_list[position_to_remove]  # type: ignore[index]

    assert cos_array_list.remove(to_be_removed) is True
    assert cos_array_list.size() == 3
    assert annotations_array.size() == 3  # type: ignore[attr-defined]

    assert cos_array_list.remove(to_be_removed) is True
    assert cos_array_list.size() == 2
    assert annotations_array.size() == 2  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# remove-all (multiple) — mirrors upstream
# ``removeAllMultipleFromListByObject`` (Java lines 259-275).
# ---------------------------------------------------------------------------


def test_remove_all_multiple_from_list_by_object(
    annotations_setup: dict[str, object],
) -> None:
    annotations_list = annotations_setup["annotations_list"]
    annotations_array = annotations_setup["annotations_array"]

    cos_array_list: COSArrayList = COSArrayList(
        annotations_list,  # type: ignore[arg-type]
        annotations_array,  # type: ignore[arg-type]
    )

    position_to_remove = 1
    to_be_removed = annotations_list[position_to_remove]  # type: ignore[index]

    to_be_removed_instances = [to_be_removed]

    assert cos_array_list.remove_all(to_be_removed_instances) is True
    assert cos_array_list.size() == 2
    assert annotations_array.size() == 2  # type: ignore[attr-defined]

    assert cos_array_list.remove_all(to_be_removed_instances) is False


# ---------------------------------------------------------------------------
# filtered-list read-only guard — mirrors upstream
# ``removeFromFilteredListByIndex`` and ``removeFromFilteredListByObject``
# (Java lines 277-305).
# ---------------------------------------------------------------------------


def test_remove_from_filtered_list_by_index(
    annotations_setup: dict[str, object],
) -> None:
    """The upstream version filters annotations via
    ``PDPage.getAnnotations(AnnotationFilter)`` which returns a
    *filtered* (read-only) COSArrayList. pypdfbox's get_annotations
    returns a plain list; here we exercise the same guard by passing a
    sub-list view + the full backing array (so len(actual) != size())."""
    annotations_list = annotations_setup["annotations_list"]
    annotations_array = annotations_setup["annotations_array"]

    # Subset of the list that excludes the link annotation.
    filtered = [
        a
        for a in annotations_list  # type: ignore[union-attr]
        if not isinstance(a, PDAnnotationLink)
    ]
    cos_array_list: COSArrayList = COSArrayList(
        filtered,
        annotations_array,  # type: ignore[arg-type]
    )

    with pytest.raises(NotImplementedError):
        cos_array_list.remove(1)


def test_remove_from_filtered_list_by_object(
    annotations_setup: dict[str, object],
) -> None:
    annotations_list = annotations_setup["annotations_list"]
    annotations_array = annotations_setup["annotations_array"]

    filtered = [
        a
        for a in annotations_list  # type: ignore[union-attr]
        if not isinstance(a, PDAnnotationLink)
    ]
    cos_array_list: COSArrayList = COSArrayList(
        filtered,
        annotations_array,  # type: ignore[arg-type]
    )

    position_to_remove = 1
    to_be_removed = cos_array_list.get(position_to_remove)

    with pytest.raises(NotImplementedError):
        cos_array_list.remove(to_be_removed)


# ---------------------------------------------------------------------------
# direct-object remove round-trip — mirrors upstream
# ``removeSingleDirectObject`` (Java lines 308-351). The upstream test
# saves the doc + reloads it, which exercises the parser path; we exercise
# the remove semantics on a freshly-constructed wrapper instead since
# pypdfbox's parser path is covered separately.
# ---------------------------------------------------------------------------


def test_remove_single_direct_object() -> None:
    txt_mark = PDAnnotationHighlight()
    txt_link = PDAnnotationLink()

    # Enforce direct embedding into the COSArray (mirrors the upstream
    # setDirect(true) calls).
    txt_mark.get_cos_object().set_direct(True)
    txt_link.get_cos_object().set_direct(True)

    page_annots = [txt_mark, txt_mark, txt_mark, txt_link]
    assert len(page_annots) == 4

    array = COSArray()
    for a in page_annots:
        array.add(a.get_cos_object())

    annotations: COSArrayList = COSArrayList(page_annots, array)
    assert annotations.size() == 4
    assert annotations.to_list().size() == 4

    to_be_removed = annotations.get(0)
    annotations.remove(to_be_removed)

    assert annotations.size() == 3
    assert annotations.to_list().size() == 3


def test_remove_single_indirect_object() -> None:
    """Upstream ``removeSingleIndirectObject`` (Java lines 354-394) is the
    indirect counterpart of the test above."""
    txt_mark = PDAnnotationHighlight()
    txt_link = PDAnnotationLink()

    page_annots = [txt_mark, txt_mark, txt_mark, txt_link]
    array = COSArray()
    for a in page_annots:
        array.add(a.get_cos_object())

    annotations: COSArrayList = COSArrayList(page_annots, array)
    assert annotations.size() == 4
    assert annotations.to_list().size() == 4

    to_be_removed = annotations.get(0)
    annotations.remove(to_be_removed)

    assert annotations.size() == 3
    assert annotations.to_list().size() == 3


def test_retain_indirect_object() -> None:
    """Upstream ``retainIndirectObject`` (Java lines 397-438)."""
    txt_mark = PDAnnotationHighlight()
    txt_link = PDAnnotationLink()

    page_annots = [txt_mark, txt_mark, txt_mark, txt_link]
    array = COSArray()
    for a in page_annots:
        array.add(a.get_cos_object())

    annotations: COSArrayList = COSArrayList(page_annots, array)
    assert annotations.size() == 4
    assert annotations.to_list().size() == 4

    to_be_retained = [annotations.get(0)]

    annotations.retain_all(to_be_retained)

    assert annotations.size() == 3
    assert annotations.to_list().size() == 3


# ---------------------------------------------------------------------------
# ``addToList`` is upstream-disabled (commented-out ``@Test`` at Java line
# 136). We exercise the analogous shape for parity even though upstream
# does not assert it as a live test.
# ---------------------------------------------------------------------------


def test_add_to_list(annotations_setup: dict[str, object]) -> None:
    annotations_list = annotations_setup["annotations_list"]
    annotations_array = annotations_setup["annotations_array"]

    cos_array_list: COSArrayList = COSArrayList(
        annotations_list,  # type: ignore[arg-type]
        annotations_array,  # type: ignore[arg-type]
    )

    a_square = PDAnnotationSquare()
    cos_array_list.add(a_square)

    assert len(annotations_list) == 5  # type: ignore[arg-type]
    assert annotations_array.size() == 5  # type: ignore[attr-defined]

    annot = annotations_list[4]  # type: ignore[index]
    assert (
        annotations_array.index_of(annot.get_cos_object()) == 4  # type: ignore[attr-defined]
    )
    assert cos_array_list.to_list() is annotations_array
