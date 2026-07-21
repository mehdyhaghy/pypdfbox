"""PDFBOX-6173 (upstream 3.0.8 net shape): output-intent dedup on merge.

Upstream ``PDFMergerUtility.mergeOutputIntents`` copies source output
intents to the destination but skips those whose
``/OutputConditionIdentifier`` already exists in the destination — except
when the identifier is missing or is named ``"Custom"``. The 3.0.8 operand
order compares the source identifier against each destination identifier so
a destination intent lacking the identifier is tolerated.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel.graphics.color import PDOutputIntent

_OUTPUT_INTENTS = COSName.get_pdf_name("OutputIntents")


class _Catalog:
    def __init__(self) -> None:
        self._cos = COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._cos


class _IdentityCloner:
    def clone_for_new_document(self, value: object) -> object:
        return value


def _intent(identifier: str | None) -> COSDictionary:
    oi = PDOutputIntent()
    if identifier is not None:
        oi.set_output_condition_identifier(identifier)
    return oi.get_cos_object()


def _catalog_with_intents(*intents: COSDictionary) -> _Catalog:
    catalog = _Catalog()
    arr = COSArray()
    for entry in intents:
        arr.add(entry)
    catalog.get_cos_object().set_item(_OUTPUT_INTENTS, arr)
    return catalog


def _dest_intents(catalog: _Catalog) -> COSArray:
    arr = catalog.get_cos_object().get_dictionary_object(_OUTPUT_INTENTS)
    assert isinstance(arr, COSArray)
    return arr


def test_duplicate_identifier_is_skipped() -> None:
    util = PDFMergerUtility()
    src = _catalog_with_intents(_intent("FOGRA39"))
    dst = _catalog_with_intents(_intent("FOGRA39"))

    util._merge_output_intents(_IdentityCloner(), src, dst)  # noqa: SLF001

    assert _dest_intents(dst).size() == 1


def test_distinct_identifier_is_appended() -> None:
    util = PDFMergerUtility()
    src = _catalog_with_intents(_intent("FOGRA51"))
    dst = _catalog_with_intents(_intent("FOGRA39"))

    util._merge_output_intents(_IdentityCloner(), src, dst)  # noqa: SLF001

    arr = _dest_intents(dst)
    assert arr.size() == 2
    appended = arr.get_object(1)
    assert isinstance(appended, COSDictionary)
    assert (
        PDOutputIntent(appended).get_output_condition_identifier() == "FOGRA51"
    )


def test_destination_intent_without_identifier_does_not_crash() -> None:
    """3.0.8 operand order: a destination intent lacking the identifier is
    survived; the distinct source intent is still appended."""
    util = PDFMergerUtility()
    src = _catalog_with_intents(_intent("FOGRA39"))
    dst = _catalog_with_intents(_intent(None))

    util._merge_output_intents(_IdentityCloner(), src, dst)  # noqa: SLF001

    assert _dest_intents(dst).size() == 2


def test_custom_identifier_is_always_copied() -> None:
    """Upstream exempts the identifier ``"Custom"`` from dedup."""
    util = PDFMergerUtility()
    src = _catalog_with_intents(_intent("Custom"))
    dst = _catalog_with_intents(_intent("Custom"))

    util._merge_output_intents(_IdentityCloner(), src, dst)  # noqa: SLF001

    assert _dest_intents(dst).size() == 2


def test_source_intent_without_identifier_is_always_copied() -> None:
    util = PDFMergerUtility()
    src = _catalog_with_intents(_intent(None))
    dst = _catalog_with_intents(_intent(None))

    util._merge_output_intents(_IdentityCloner(), src, dst)  # noqa: SLF001

    assert _dest_intents(dst).size() == 2


def test_duplicate_within_source_is_deduped_and_dest_array_created() -> None:
    """Upstream tracks each appended source intent in its local destination
    list, so a later source duplicate is skipped too — and the destination
    /OutputIntents array is created on demand when absent."""
    util = PDFMergerUtility()
    src = _catalog_with_intents(_intent("FOGRA39"), _intent("FOGRA39"))
    dst = _Catalog()

    util._merge_output_intents(_IdentityCloner(), src, dst)  # noqa: SLF001

    assert _dest_intents(dst).size() == 1
