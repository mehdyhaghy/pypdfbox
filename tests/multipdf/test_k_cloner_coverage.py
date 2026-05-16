"""Coverage-boost tests for ``pypdfbox.multipdf.k_cloner``.

Targets the ``create_array_clone`` / ``create_dictionary_clone`` /
``has_mci_ds`` / ``remove_possible_orphan_annotation`` branches that
the wave-1281 baseline left uncovered, plus the splitter-delegation
path and the fallback (no-splitter) path with non-trivial inputs.
"""

from __future__ import annotations

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.multipdf.k_cloner import KCloner


class _StubPageTree:
    """Minimal PDPageTree replacement — index_of always reports unknown."""

    def index_of(self, _: object) -> int:
        return -1


class _RecordingSplitter:
    """Stand-in for ``Splitter`` that records delegation calls.

    Exposes ``_k_create_clone`` and ``_remove_possible_orphan_annotation``
    so ``KCloner`` takes the delegation branch (lines 55-62, 79-80,
    96-97, 134-140).
    """

    def __init__(self) -> None:
        self._page_dict_map: dict[int, COSDictionary] = {}
        self._struct_dict_map: dict[int, COSDictionary] = {}
        self.create_calls: list[tuple] = []
        self.remove_calls: list[tuple] = []
        self.return_value: object | None = None

    def _k_create_clone(self, src, dst_parent, current_page_dict, page_tree):
        self.create_calls.append((src, dst_parent, current_page_dict, page_tree))
        if self.return_value is _PASSTHROUGH:
            return src
        return self.return_value

    def _remove_possible_orphan_annotation(
        self, src_obj, src_dict, annotations=None
    ) -> None:
        self.remove_calls.append((src_obj, src_dict, annotations))


_PASSTHROUGH = object()


# ---- splitter-less path -------------------------------------------------


def test_create_clone_returns_none_for_none() -> None:
    cloner = KCloner(_StubPageTree())
    assert cloner.create_clone(None, None, None) is None


def test_create_clone_passes_through_scalar() -> None:
    cloner = KCloner(_StubPageTree())
    val = COSInteger(7)
    assert cloner.create_clone(val, None, None) is val


def test_create_clone_dispatches_array_branch() -> None:
    cloner = KCloner(_StubPageTree())
    src = COSArray()
    src.add(COSInteger(1))
    src.add(COSInteger(2))
    cloned = cloner.create_clone(src, None, None)
    assert isinstance(cloned, COSArray)
    assert cloned.size() == 2
    assert cloned.get_object(0).int_value() == 1
    assert cloned.get_object(1).int_value() == 2


def test_create_clone_dispatches_dictionary_passthrough() -> None:
    cloner = KCloner(_StubPageTree())
    src = COSDictionary()
    src.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("StructElem"))
    assert cloner.create_clone(src, None, None) is src


def test_create_array_clone_returns_none_for_empty_array() -> None:
    cloner = KCloner(_StubPageTree())
    src = COSArray()
    assert cloner.create_array_clone(src, None, None) is None


def test_create_array_clone_skips_none_children() -> None:
    """Direct call to create_array_clone — ensure size-0 result returns None."""
    cloner = KCloner(_StubPageTree())
    # Pre-build an array whose elements vanish: empty COSArray child
    # cloned via create_clone returns None.
    src = COSArray()
    src.add(COSArray())  # empty inner array → cloned to None
    src.add(COSArray())  # ditto
    cloned = cloner.create_array_clone(src, None, None)
    assert cloned is None


def test_create_array_clone_drops_empty_children_keeps_others() -> None:
    cloner = KCloner(_StubPageTree())
    src = COSArray()
    src.add(COSArray())  # empty → None
    src.add(COSInteger(42))  # scalar → kept
    cloned = cloner.create_array_clone(src, None, None)
    assert isinstance(cloned, COSArray)
    assert cloned.size() == 1
    assert cloned.get_object(0).int_value() == 42


def test_create_dictionary_clone_fallback_passthrough() -> None:
    cloner = KCloner(_StubPageTree())
    src = COSDictionary()
    src.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("P"))
    out = cloner.create_dictionary_clone(src, None, None)
    assert out is src


# ---- has_mci_ds branches ------------------------------------------------


def test_has_mci_ds_none_is_false() -> None:
    cloner = KCloner(_StubPageTree())
    assert cloner.has_mci_ds(None) is False


def test_has_mci_ds_bare_integer_is_true() -> None:
    cloner = KCloner(_StubPageTree())
    assert cloner.has_mci_ds(COSInteger(3)) is True


def test_has_mci_ds_dict_with_integer_k_is_true() -> None:
    cloner = KCloner(_StubPageTree())
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("K"), COSInteger(0))
    assert cloner.has_mci_ds(d) is True


def test_has_mci_ds_dict_with_array_k_containing_integer_is_true() -> None:
    cloner = KCloner(_StubPageTree())
    arr = COSArray()
    arr.add(COSInteger(1))
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("K"), arr)
    assert cloner.has_mci_ds(d) is True


def test_has_mci_ds_dict_with_array_k_no_integer_is_false() -> None:
    cloner = KCloner(_StubPageTree())
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Foo"))
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("K"), arr)
    assert cloner.has_mci_ds(d) is False


def test_has_mci_ds_dict_with_dict_k_recurses() -> None:
    cloner = KCloner(_StubPageTree())
    inner = COSDictionary()
    inner.set_item(COSName.get_pdf_name("K"), COSInteger(2))
    outer = COSDictionary()
    outer.set_item(COSName.get_pdf_name("K"), inner)
    assert cloner.has_mci_ds(outer) is True


def test_has_mci_ds_dict_without_k_is_false() -> None:
    cloner = KCloner(_StubPageTree())
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("P"))
    assert cloner.has_mci_ds(d) is False


def test_has_mci_ds_array_with_integer_is_true() -> None:
    cloner = KCloner(_StubPageTree())
    arr = COSArray()
    arr.add(COSInteger(0))
    assert cloner.has_mci_ds(arr) is True


def test_has_mci_ds_array_without_integer_is_false() -> None:
    cloner = KCloner(_StubPageTree())
    arr = COSArray()
    arr.add(COSName.get_pdf_name("X"))
    assert cloner.has_mci_ds(arr) is False


# ---- remove_possible_orphan_annotation (fallback) -----------------------


def test_remove_possible_orphan_annotation_clears_obj_ref() -> None:
    cloner = KCloner(_StubPageTree())
    src_obj = COSDictionary()
    src_dict = COSDictionary()
    obj_name = COSName.get_pdf_name("Obj")
    src_dict.set_item(obj_name, src_obj)
    cloner.remove_possible_orphan_annotation(src_obj, src_dict)
    assert not src_dict.contains_key(obj_name)


def test_remove_possible_orphan_annotation_noop_when_no_obj() -> None:
    cloner = KCloner(_StubPageTree())
    src_obj = COSDictionary()
    src_dict = COSDictionary()
    # No /Obj entry to begin with — should not raise.
    cloner.remove_possible_orphan_annotation(src_obj, src_dict)
    assert not src_dict.contains_key(COSName.get_pdf_name("Obj"))


# ---- splitter delegation path -------------------------------------------


def test_create_clone_delegates_to_splitter_and_syncs_maps() -> None:
    splitter = _RecordingSplitter()
    splitter.return_value = COSInteger(99)
    page_map = {1: COSDictionary()}
    struct_map = {2: COSDictionary()}
    cloner = KCloner(
        _StubPageTree(),
        splitter=splitter,
        page_dict_map=page_map,
        struct_dict_map=struct_map,
    )
    src = COSInteger(1)
    result = cloner.create_clone(src, None, None)
    # Splitter's _k_create_clone was invoked, and its return value bubbled up.
    assert len(splitter.create_calls) == 1
    assert result is splitter.return_value
    # State sync: splitter's maps now point at the cloner's maps.
    assert splitter._page_dict_map is page_map
    assert splitter._struct_dict_map is struct_map


def test_create_array_clone_delegates_via_create_clone() -> None:
    splitter = _RecordingSplitter()
    splitter.return_value = _PASSTHROUGH
    cloner = KCloner(_StubPageTree(), splitter=splitter)
    arr = COSArray()
    arr.add(COSInteger(1))
    result = cloner.create_array_clone(arr, None, None)
    # When a splitter is attached, create_array_clone delegates back through
    # create_clone (which delegates to the splitter).
    assert splitter.create_calls, "expected splitter delegation"
    assert result is arr  # passthrough sentinel


def test_create_dictionary_clone_delegates_via_create_clone() -> None:
    splitter = _RecordingSplitter()
    splitter.return_value = _PASSTHROUGH
    cloner = KCloner(_StubPageTree(), splitter=splitter)
    d = COSDictionary()
    result = cloner.create_dictionary_clone(d, None, None)
    assert splitter.create_calls, "expected splitter delegation"
    assert result is d


def test_remove_possible_orphan_annotation_delegates_to_splitter() -> None:
    splitter = _RecordingSplitter()
    cloner = KCloner(_StubPageTree(), splitter=splitter)
    src_obj = COSDictionary()
    src_dict = COSDictionary()
    obj_name = COSName.get_pdf_name("Obj")
    src_dict.set_item(obj_name, src_obj)
    cloner.remove_possible_orphan_annotation(src_obj, src_dict, "some-annots")
    assert splitter.remove_calls == [(src_obj, src_dict, "some-annots")]
    # Splitter delegation path doesn't strip /Obj itself (the splitter's
    # implementation decides).
    assert src_dict.contains_key(obj_name)


# ---- constructor defaults -----------------------------------------------


def test_constructor_initialises_empty_maps_by_default() -> None:
    cloner = KCloner(_StubPageTree())
    # Direct attribute access — verify defaults wired correctly.
    assert cloner._page_dict_map == {}
    assert cloner._struct_dict_map == {}
    assert cloner._splitter is None


def test_constructor_accepts_explicit_maps() -> None:
    page_map = {1: COSDictionary()}
    struct_map = {2: COSDictionary()}
    cloner = KCloner(
        _StubPageTree(), page_dict_map=page_map, struct_dict_map=struct_map
    )
    assert cloner._page_dict_map is page_map
    assert cloner._struct_dict_map is struct_map
