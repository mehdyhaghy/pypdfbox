from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.multipdf.pdf_merger_utility import PDFMergerUtility

_ACRO_FORM = COSName.get_pdf_name("AcroForm")
_ID_TREE = COSName.get_pdf_name("IDTree")
_K = COSName.get_pdf_name("K")
_NAMES = COSName.get_pdf_name("Names")
_P = COSName.get_pdf_name("P")
_PART = COSName.get_pdf_name("Part")
_PG = COSName.get_pdf_name("Pg")
_S = COSName.get_pdf_name("S")
_STRUCT_PARENT = COSName.get_pdf_name("StructParent")


class _IdentityCloner:
    def clone_for_new_document(self, value: object) -> object:
        return value


class _Root:
    def __init__(self, root_dict: COSDictionary | None = None) -> None:
        self._dict = root_dict if root_dict is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


class _Catalog:
    def __init__(self, catalog_dict: COSDictionary | None = None) -> None:
        self._dict = catalog_dict if catalog_dict is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


def test_wave489_add_sources_rejects_single_source_like_values() -> None:
    util = PDFMergerUtility()

    with pytest.raises(TypeError, match="expected an iterable of sources"):
        util.add_sources("one.pdf")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="expected an iterable of sources"):
        util.add_sources(b"%PDF-1.7")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="expected an iterable of sources"):
        util.add_sources(io.BytesIO(b"%PDF-1.7"))  # type: ignore[arg-type]

    assert util.get_sources() == []


def test_wave489_set_destination_routes_path_and_stream_and_rejects_other() -> None:
    util = PDFMergerUtility()
    sink = io.BytesIO()

    util.set_destination("out.pdf")
    assert util.get_destination_file_name() == "out.pdf"

    util.set_destination(sink)
    assert util.get_destination_stream() is sink

    with pytest.raises(TypeError, match="unsupported destination type"):
        util.set_destination(object())  # type: ignore[arg-type]


def test_wave489_is_dynamic_xfa_swallows_probe_exceptions() -> None:
    class BrokenForm:
        def xfa_is_dynamic(self) -> bool:
            raise RuntimeError("bad xfa")

    assert PDFMergerUtility._is_dynamic_xfa(None) is False  # noqa: SLF001
    assert PDFMergerUtility._is_dynamic_xfa(BrokenForm()) is False  # noqa: SLF001


def test_wave489_merge_into_skips_excluded_and_existing_keys() -> None:
    keep = COSName.get_pdf_name("Keep")
    existing = COSName.get_pdf_name("Existing")
    excluded = COSName.get_pdf_name("Excluded")
    src = COSDictionary()
    src.set_item(keep, COSString("new"))
    src.set_item(existing, COSString("source"))
    src.set_item(excluded, COSString("excluded"))
    dst = COSDictionary()
    dst.set_item(existing, COSString("dest"))

    PDFMergerUtility._merge_into(  # noqa: SLF001
        src,
        dst,
        _IdentityCloner(),  # type: ignore[arg-type]
        frozenset({excluded}),
    )

    assert dst.get_dictionary_object(keep).get_string() == "new"
    assert dst.get_dictionary_object(existing).get_string() == "dest"
    assert dst.get_dictionary_object(excluded) is None


def test_wave489_merge_names_removes_misplaced_id_tree_after_clone() -> None:
    names = COSDictionary()
    names.set_item(_ID_TREE, COSDictionary())
    src_dict = COSDictionary()
    src_dict.set_item(_NAMES, names)
    dest_dict = COSDictionary()

    PDFMergerUtility()._merge_names(  # noqa: SLF001
        _IdentityCloner(),  # type: ignore[arg-type]
        _Catalog(src_dict),
        _Catalog(dest_dict),
    )

    merged_names = dest_dict.get_dictionary_object(_NAMES)
    assert isinstance(merged_names, COSDictionary)
    assert merged_names.get_dictionary_object(_ID_TREE) is None


def test_wave489_strip_struct_parent_from_annots_skips_non_dict_entries() -> None:
    annot = COSDictionary()
    annot.set_item(_STRUCT_PARENT, COSString("remove-me"))
    annots = COSArray()
    annots.add(annot)
    annots.add(COSName.get_pdf_name("NotADictionary"))
    page = COSDictionary()
    page.set_item("Annots", annots)

    PDFMergerUtility._strip_struct_parent_from_annots(page)  # noqa: SLF001

    assert annot.get_dictionary_object(_STRUCT_PARENT) is None


def test_wave489_get_number_and_id_tree_maps_recurse_and_unwrap_cos_objects() -> None:
    class Wrapped:
        def __init__(self, value: COSDictionary) -> None:
            self._value = value

        def get_cos_object(self) -> COSDictionary:
            return self._value

    class Tree:
        def __init__(
            self,
            numbers: dict[int, object] | None = None,
            names: dict[str, object] | None = None,
            kids: list[object] | None = None,
        ) -> None:
            self._numbers = numbers
            self._names = names
            self._kids = kids

        def get_numbers(self) -> dict[int, object] | None:
            return self._numbers

        def get_names(self) -> dict[str, object] | None:
            return self._names

        def get_kids(self) -> list[object] | None:
            return self._kids

    number_leaf = COSDictionary()
    id_leaf = COSDictionary()
    tree = Tree(
        numbers={1: Wrapped(number_leaf)},
        names={"root": Wrapped(id_leaf)},
        kids=[Tree(numbers={2: COSString("two")}, names={"kid": COSString("value")})],
    )

    assert PDFMergerUtility.get_number_tree_as_map(tree) == {
        1: number_leaf,
        2: COSString("two"),
    }
    assert PDFMergerUtility.get_id_tree_as_map(tree) == {
        "root": id_leaf,
        "kid": COSString("value"),
    }


def test_wave489_update_parent_entry_sets_parent_and_optional_structure_type() -> None:
    child = COSDictionary()
    child.set_item(_S, COSName.get_pdf_name("Document"))
    non_dict = COSName.get_pdf_name("Skip")
    parent = COSDictionary()
    k_array = COSArray([child, non_dict])

    PDFMergerUtility._update_parent_entry(k_array, parent, _PART)  # noqa: SLF001

    assert child.get_dictionary_object(_P) is parent
    assert child.get_dictionary_object(_S) == _PART


def test_wave489_update_page_references_recurses_into_nested_k_arrays() -> None:
    old_page = COSDictionary()
    new_page = COSDictionary()
    leaf = COSDictionary()
    leaf.set_item(_PG, old_page)
    nested = COSArray([leaf])
    parent = COSDictionary()
    parent.set_item(_K, nested)

    PDFMergerUtility()._update_page_references_dict(  # noqa: SLF001
        _IdentityCloner(),  # type: ignore[arg-type]
        parent,
        {id(old_page): new_page},
    )

    assert leaf.get_dictionary_object(_PG) is new_page
