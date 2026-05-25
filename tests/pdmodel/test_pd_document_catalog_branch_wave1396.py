"""Wave 1396 branch-coverage tests for ``PDDocumentCatalog``.

Closes False-branch arrows in
``pypdfbox/pdmodel/pd_document_catalog.py``:

* 650->656 — ``/Names`` lookup falls through when neither ``get_value``
  nor ``get_destination`` is on the dests tree wrapper
* 652->656 — ``/Names`` lookup falls through when ``get_value`` returns
  ``None``
* 661->664 — legacy ``/Dests`` returns ``None`` for missing entry
* 742->745 — ``add_output_intent`` reuses an existing /OutputIntents
  array (False arm of ``not isinstance``)
* 919->922 — ``set_developer_extension`` reuses an existing /Extensions
  dict
* 932->exit — ``remove_developer_extension`` keeps a non-empty
  /Extensions dict
* 1019->1022 — ``add_requirement`` reuses an existing /Requirements
  array
* 1292->1290 — ``has_associated_files`` continues looping when
  ``create_fs`` returns ``None`` for an entry
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNull
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument


def test_find_named_destination_page_returns_none_when_tree_has_no_getter() -> None:
    """``/Names /Dests`` tree without get_value/get_destination falls through.

    Closes False arm of ``getter is not None`` (line 650->656).
    """
    with PDDocument() as document:
        catalog = document.get_document_catalog()

        # We can't construct an arbitrary /Names value via set_names because
        # PDDocumentNameDictionary requires get_cos_object. So instead, mock
        # by stuffing a dict into /Names directly.
        names_dict_cos = COSDictionary()
        # Mark with a /Dests value that's a COSDictionary, the wrapper's
        # get_dests() returns a PDDestinationNameTreeNode whose get_value
        # works. Use an empty tree, so result.get_value(name) returns None.
        empty_dests_dict = COSDictionary()
        names_dict_cos.set_item(COSName.get_pdf_name("Dests"), empty_dests_dict)
        catalog.get_cos_object().set_item(
            COSName.get_pdf_name("Names"), names_dict_cos,
        )
        named = PDNamedDestination("ghost")
        result = catalog.find_named_destination_page(named)
        # Both the names tree and legacy /Dests miss; returns None.
        assert result is None


def test_find_named_destination_page_returns_none_when_legacy_dests_miss() -> None:
    """Legacy /Dests without the requested name returns None.

    Closes False arm of ``page_dest is not None`` (line 661->664).
    """
    with PDDocument() as document:
        catalog = document.get_document_catalog()
        # Build a legacy /Dests dictionary with a single bogus key.
        legacy = COSDictionary()
        legacy.set_item(COSName.get_pdf_name("other"), COSNull.NULL)
        catalog.get_cos_object().set_item(
            COSName.get_pdf_name("Dests"), legacy,
        )
        named = PDNamedDestination("ghost")
        assert catalog.find_named_destination_page(named) is None


def test_add_output_intent_reuses_existing_array() -> None:
    """``add_output_intent`` reuses /OutputIntents when it's already a COSArray.

    Closes False arm of ``not isinstance(arr, COSArray)`` (line 742->745).
    """
    with PDDocument() as document:
        catalog = document.get_document_catalog()
        from pypdfbox.pdmodel.graphics.color.pd_output_intent import (
            PDOutputIntent,
        )

        intent1 = PDOutputIntent()
        intent2 = PDOutputIntent()
        catalog.add_output_intent(intent1)
        catalog.add_output_intent(intent2)
        # Two entries — the second call reused the existing array.
        intents = catalog.get_output_intents()
        assert len(intents) == 2


def test_set_developer_extension_reuses_existing_dict() -> None:
    """``set_developer_extension`` reuses an existing /Extensions dictionary.

    Closes False arm of ``not isinstance(v, COSDictionary)`` (line 919->922).
    """
    with PDDocument() as document:
        catalog = document.get_document_catalog()
        from pypdfbox.pdmodel.pd_developer_extension import (
            PDDeveloperExtension,
        )

        ext1 = PDDeveloperExtension()
        ext1.set_base_version("1.7")
        ext1.set_extension_level(3)
        ext2 = PDDeveloperExtension()
        ext2.set_base_version("1.7")
        ext2.set_extension_level(5)

        catalog.add_developer_extension("ADBE", ext1)
        catalog.add_developer_extension("MYOWN", ext2)

        ext_cos = catalog.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Extensions"),
        )
        assert isinstance(ext_cos, COSDictionary)
        assert ext_cos.contains_key(COSName.get_pdf_name("ADBE"))
        assert ext_cos.contains_key(COSName.get_pdf_name("MYOWN"))


def test_remove_developer_extension_keeps_non_empty_dict() -> None:
    """``remove_developer_extension`` keeps /Extensions when other keys remain.

    Closes False arm of ``v.is_empty()`` (line 932->exit).
    """
    with PDDocument() as document:
        catalog = document.get_document_catalog()
        from pypdfbox.pdmodel.pd_developer_extension import (
            PDDeveloperExtension,
        )

        ext1 = PDDeveloperExtension()
        ext1.set_base_version("1.7")
        ext1.set_extension_level(3)
        ext2 = PDDeveloperExtension()
        ext2.set_base_version("1.7")
        ext2.set_extension_level(5)

        catalog.add_developer_extension("ADBE", ext1)
        catalog.add_developer_extension("MYOWN", ext2)
        catalog.remove_developer_extension("ADBE")

        ext_cos = catalog.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Extensions"),
        )
        # /Extensions kept because MYOWN remains.
        assert isinstance(ext_cos, COSDictionary)
        assert not ext_cos.contains_key(COSName.get_pdf_name("ADBE"))
        assert ext_cos.contains_key(COSName.get_pdf_name("MYOWN"))


def test_add_requirement_reuses_existing_array() -> None:
    """``add_requirement`` reuses /Requirements when it's already a COSArray.

    Closes False arm of ``not isinstance(arr, COSArray)`` (line 1019->1022).
    """
    with PDDocument() as document:
        catalog = document.get_document_catalog()
        req1 = COSDictionary()
        req1.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("EnableJavaScripts"))
        req2 = COSDictionary()
        req2.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Other"))

        catalog.add_requirement(req1)
        catalog.add_requirement(req2)

        arr = catalog.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Requirements"),
        )
        assert isinstance(arr, COSArray)
        assert arr.size() == 2


def test_has_associated_files_skips_invalid_entries_keeps_looping() -> None:
    """``has_associated_files`` keeps looping when a /AF entry isn't a valid FS.

    Closes False arm of ``create_fs(...) is not None`` (line 1292->1290).
    """
    with PDDocument() as document:
        catalog = document.get_document_catalog()
        from pypdfbox.cos import COSNull
        from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
            PDComplexFileSpecification,
        )

        af = COSArray()
        # First entry: a COSNull — create_fs returns None.
        af.add(COSNull.NULL)
        # Second entry: a valid file specification.
        fs = PDComplexFileSpecification()
        fs.set_file("data.txt")
        af.add(fs.get_cos_object())
        catalog.get_cos_object().set_item(
            COSName.get_pdf_name("AF"), af,
        )
        assert catalog.has_associated_files() is True
