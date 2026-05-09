from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.multipdf.pdf_merger_utility import PDFMergerUtility

_ACRO_FORM = COSName.get_pdf_name("AcroForm")
_DESTS = COSName.get_pdf_name("Dests")
_ID_TREE = COSName.get_pdf_name("IDTree")
_OPEN_ACTION = COSName.get_pdf_name("OpenAction")
_OUTPUT_INTENTS = COSName.get_pdf_name("OutputIntents")
_STRUCT_PARENT = COSName.get_pdf_name("StructParent")


class _IdentityCloner:
    def clone_for_new_document(self, value: object) -> object:
        return value

    def _clone_merge_cos_base(
        self,
        src: COSDictionary,
        dst: COSDictionary,
        exclude: set[COSName],
    ) -> None:
        for key, value in src.entry_set():
            if key not in exclude:
                dst.set_item(key, value)


class _Catalog:
    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()
        self.outline: object | None = None

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_acro_form(self) -> object | None:
        return None

    def get_document_outline(self) -> object | None:
        return self.outline


class _Form:
    def __init__(self) -> None:
        self._dict = COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


class _CatalogWithForm(_Catalog):
    def __init__(self, form: _Form | None) -> None:
        super().__init__()
        self._form = form

    def get_acro_form(self) -> _Form | None:
        return self._form


class _BrokenCatalog(_Catalog):
    def get_acro_form(self) -> object:
        raise RuntimeError("cannot inspect")


class _Tree:
    def __init__(
        self,
        numbers: dict[int | str, object] | None = None,
        names: dict[str, object] | None = None,
        kids: list[_Tree] | None = None,
    ) -> None:
        self._numbers = numbers
        self._names = names
        self._kids = kids

    def get_numbers(self) -> dict[int | str, object] | None:
        return self._numbers

    def get_names(self) -> dict[str, object] | None:
        return self._names

    def get_kids(self) -> list[_Tree] | None:
        return self._kids


class _StructRoot:
    def __init__(self, id_tree: object | None = None) -> None:
        self._dict = COSDictionary()
        self._id_tree = id_tree
        self.installed_id_tree: object | None = None

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_id_tree(self) -> object | None:
        return self._id_tree

    def set_id_tree(self, tree: object) -> None:
        self.installed_id_tree = tree


def test_wave615_merge_acro_form_installs_source_form_when_destination_missing() -> None:
    source_form = _Form()
    source_form.get_cos_object().set_string(COSName.get_pdf_name("NeedAppearances"), "yes")
    dest_catalog = _CatalogWithForm(None)

    PDFMergerUtility()._merge_acro_form(  # noqa: SLF001
        _IdentityCloner(),  # type: ignore[arg-type]
        dest_catalog,
        _CatalogWithForm(source_form),
    )

    assert dest_catalog.get_cos_object().get_dictionary_object(_ACRO_FORM) is (
        source_form.get_cos_object()
    )


def test_wave615_merge_acro_form_reraises_errors_unless_ignored() -> None:
    with pytest.raises(OSError, match="cannot inspect"):
        PDFMergerUtility()._merge_acro_form(  # noqa: SLF001
            _IdentityCloner(),  # type: ignore[arg-type]
            _BrokenCatalog(),
            _Catalog(),
        )


def test_wave615_legacy_dests_are_installed_then_merged() -> None:
    src_dests = COSDictionary()
    src_dests.set_string(COSName.get_pdf_name("A"), "alpha")
    src_catalog = _Catalog()
    src_catalog.get_cos_object().set_item(_DESTS, src_dests)
    dest_catalog = _Catalog()

    util = PDFMergerUtility()
    util._merge_names(_IdentityCloner(), src_catalog, dest_catalog)  # noqa: SLF001

    installed = dest_catalog.get_cos_object().get_dictionary_object(_DESTS)
    assert installed is src_dests

    more_dests = COSDictionary()
    more_dests.set_string(COSName.get_pdf_name("B"), "bravo")
    second_source = _Catalog()
    second_source.get_cos_object().set_item(_DESTS, more_dests)

    util._merge_names(_IdentityCloner(), second_source, dest_catalog)  # noqa: SLF001

    assert src_dests.get_string(COSName.get_pdf_name("B")) == "bravo"


def test_wave615_output_intents_install_and_append() -> None:
    first = COSArray([COSString("first")])
    src_catalog = _Catalog()
    src_catalog.get_cos_object().set_item(_OUTPUT_INTENTS, first)
    dest_catalog = _Catalog()

    util = PDFMergerUtility()
    util._merge_output_intents(_IdentityCloner(), src_catalog, dest_catalog)  # noqa: SLF001

    installed = dest_catalog.get_cos_object().get_dictionary_object(_OUTPUT_INTENTS)
    assert installed is first

    second = COSArray([COSString("second")])
    second_source = _Catalog()
    second_source.get_cos_object().set_item(_OUTPUT_INTENTS, second)

    util._merge_output_intents(_IdentityCloner(), second_source, dest_catalog)  # noqa: SLF001

    assert first.size() == 2
    assert first.get_object(1).get_string() == "second"


def test_wave615_open_action_is_first_source_wins() -> None:
    source_action = COSArray([COSString("go")])
    src_catalog = _Catalog()
    src_catalog.get_cos_object().set_item(_OPEN_ACTION, source_action)
    dest_catalog = _Catalog()

    util = PDFMergerUtility()
    util._merge_open_action(_IdentityCloner(), src_catalog, dest_catalog)  # noqa: SLF001

    assert dest_catalog.get_cos_object().get_dictionary_object(_OPEN_ACTION) is source_action

    other_action = COSArray([COSString("skip")])
    other_source = _Catalog()
    other_source.get_cos_object().set_item(_OPEN_ACTION, other_action)

    util._merge_open_action(_IdentityCloner(), other_source, dest_catalog)  # noqa: SLF001

    assert dest_catalog.get_cos_object().get_dictionary_object(_OPEN_ACTION) is source_action


def test_wave615_strip_struct_parent_from_annotations_is_defensive() -> None:
    page = COSDictionary()
    PDFMergerUtility._strip_struct_parent_from_annots(page)  # noqa: SLF001

    annot = COSDictionary()
    annot.set_item(_STRUCT_PARENT, COSInteger.get(5))
    page.set_item(COSName.get_pdf_name("Annots"), COSArray([annot, COSString("skip")]))

    PDFMergerUtility._strip_struct_parent_from_annots(page)  # noqa: SLF001

    assert annot.get_dictionary_object(_STRUCT_PARENT) is None


def test_wave615_number_and_id_tree_maps_flatten_wrappers_and_kids() -> None:
    class Wrapper:
        def __init__(self, cos: COSDictionary) -> None:
            self._cos = cos

        def get_cos_object(self) -> COSDictionary:
            return self._cos

    parent_value = COSDictionary()
    child_value = COSDictionary()
    number_tree = _Tree(
        numbers={"2": Wrapper(parent_value)},
        kids=[_Tree(numbers={4: child_value})],
    )

    assert PDFMergerUtility.get_number_tree_as_map(number_tree) == {
        2: parent_value,
        4: child_value,
    }

    root_value = COSDictionary()
    kid_value = COSDictionary()
    id_tree = _Tree(names={"root": Wrapper(root_value)}, kids=[_Tree(names={"kid": kid_value})])

    assert PDFMergerUtility.get_id_tree_as_map(id_tree) == {
        "root": root_value,
        "kid": kid_value,
    }


def test_wave615_merge_id_tree_drops_duplicates_and_wraps_cos_dictionaries(
    caplog: pytest.LogCaptureFixture,
) -> None:
    duplicate = COSDictionary()
    fresh = COSDictionary()
    src_root = _StructRoot(_Tree(names={"same": duplicate, "fresh": fresh}))
    dest_root = _StructRoot(_Tree(names={"same": COSDictionary()}))

    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.pdf_merger_utility"):
        PDFMergerUtility()._merge_id_tree(  # noqa: SLF001
            _IdentityCloner(),  # type: ignore[arg-type]
            src_root,
            dest_root,
        )

    assert "already exists in destination IDTree" in caplog.text
    assert dest_root.installed_id_tree is not None
    names = dest_root.installed_id_tree.get_names()  # type: ignore[attr-defined]
    assert set(names) == {"same", "fresh"}
