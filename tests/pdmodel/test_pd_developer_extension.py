from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel import PDDeveloperExtension, PDDocument


def test_default_construction_sets_type() -> None:
    ext = PDDeveloperExtension()
    cos = ext.get_cos_object()
    assert isinstance(cos, COSDictionary)
    type_obj = cos.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
    assert isinstance(type_obj, COSName)
    assert type_obj.get_name() == "DeveloperExtensions"


def test_wrap_existing_dict_preserves_entries() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("DeveloperExtensions"))  # type: ignore[attr-defined]
    raw.set_item(COSName.get_pdf_name("BaseVersion"), COSName.get_pdf_name("1.7"))
    raw.set_item(COSName.get_pdf_name("ExtensionLevel"), COSInteger.get(3))
    ext = PDDeveloperExtension(raw)
    assert ext.get_cos_object() is raw
    assert ext.get_base_version() == "1.7"
    assert ext.get_extension_level() == 3


def test_wrap_existing_dict_without_type_sets_type() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("BaseVersion"), COSName.get_pdf_name("1.7"))
    ext = PDDeveloperExtension(raw)
    type_obj = raw.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
    assert isinstance(type_obj, COSName)
    assert type_obj.get_name() == "DeveloperExtensions"
    assert ext.get_base_version() == "1.7"


def test_base_version_round_trip() -> None:
    ext = PDDeveloperExtension()
    assert ext.get_base_version() is None
    ext.set_base_version("1.7")
    assert ext.get_base_version() == "1.7"
    # Stored as a /Name, not a /String.
    raw = ext.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("BaseVersion")
    )
    assert isinstance(raw, COSName)
    assert raw.get_name() == "1.7"
    ext.set_base_version(None)
    assert ext.get_base_version() is None
    assert not ext.get_cos_object().contains_key(
        COSName.get_pdf_name("BaseVersion")
    )


def test_extension_level_round_trip_and_default() -> None:
    ext = PDDeveloperExtension()
    # Mirrors COSDictionary.getInt's -1 default for missing keys.
    assert ext.get_extension_level() == -1
    ext.set_extension_level(8)
    assert ext.get_extension_level() == 8
    raw = ext.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("ExtensionLevel")
    )
    assert isinstance(raw, COSInteger)
    assert raw.value == 8


def test_url_round_trip_and_string_type() -> None:
    ext = PDDeveloperExtension()
    assert ext.get_url() is None
    ext.set_url("https://example.org/ext")
    assert ext.get_url() == "https://example.org/ext"
    raw = ext.get_cos_object().get_dictionary_object(COSName.get_pdf_name("URL"))
    assert isinstance(raw, COSString)
    assert raw.get_string() == "https://example.org/ext"
    ext.set_url(None)
    assert ext.get_url() is None
    assert not ext.get_cos_object().contains_key(COSName.get_pdf_name("URL"))


def test_repr_includes_base_version_and_level() -> None:
    ext = PDDeveloperExtension()
    ext.set_base_version("1.7")
    ext.set_extension_level(3)
    text = repr(ext)
    assert "1.7" in text
    assert "3" in text


def test_adbe_class_constant_value() -> None:
    assert PDDeveloperExtension.ADBE == "ADBE"


# ---------- catalog wiring ----------


def test_catalog_developer_extensions_empty_by_default() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.get_developer_extensions() == {}


def test_catalog_add_and_get_developer_extension() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    ext = PDDeveloperExtension()
    ext.set_base_version("1.7")
    ext.set_extension_level(3)
    cat.add_developer_extension("ADBE", ext)

    extensions = cat.get_developer_extensions()
    assert set(extensions.keys()) == {"ADBE"}
    adbe = extensions["ADBE"]
    assert adbe.get_base_version() == "1.7"
    assert adbe.get_extension_level() == 3


def test_catalog_set_developer_extensions_replaces_dictionary() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()

    ext1 = PDDeveloperExtension()
    ext1.set_base_version("1.7")
    ext1.set_extension_level(3)

    ext2 = PDDeveloperExtension()
    ext2.set_base_version("2.0")
    ext2.set_extension_level(1)

    cat.set_developer_extensions({"ADBE": ext1, "MYAP": ext2})

    extensions = cat.get_developer_extensions()
    assert set(extensions.keys()) == {"ADBE", "MYAP"}
    assert extensions["ADBE"].get_extension_level() == 3
    assert extensions["MYAP"].get_extension_level() == 1


def test_catalog_set_developer_extensions_none_removes_entry() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    ext = PDDeveloperExtension()
    ext.set_base_version("1.7")
    ext.set_extension_level(3)
    cat.add_developer_extension("ADBE", ext)
    assert cat.get_developer_extensions()

    cat.set_developer_extensions(None)
    assert cat.get_developer_extensions() == {}
    assert not cat.get_cos_object().contains_key(
        COSName.get_pdf_name("Extensions")
    )

    # Also accept an empty dict.
    cat.add_developer_extension("ADBE", ext)
    cat.set_developer_extensions({})
    assert cat.get_developer_extensions() == {}
    assert not cat.get_cos_object().contains_key(
        COSName.get_pdf_name("Extensions")
    )


def test_catalog_remove_developer_extension_clears_when_empty() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    ext = PDDeveloperExtension()
    ext.set_base_version("1.7")
    ext.set_extension_level(3)
    cat.add_developer_extension("ADBE", ext)

    cat.remove_developer_extension("ADBE")
    assert cat.get_developer_extensions() == {}
    # Empty mapping should drop /Extensions entirely.
    assert not cat.get_cos_object().contains_key(
        COSName.get_pdf_name("Extensions")
    )


def test_catalog_remove_developer_extension_missing_is_noop() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    # Removing from nothing should not raise.
    cat.remove_developer_extension("ADBE")
    assert cat.get_developer_extensions() == {}


def test_catalog_developer_extensions_ignores_non_dict_entries() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    ext = PDDeveloperExtension()
    ext.set_base_version("1.7")
    ext.set_extension_level(3)
    cat.add_developer_extension("ADBE", ext)
    # Inject garbage under another prefix; getter should skip it.
    raw_extensions = cat.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Extensions")
    )
    assert isinstance(raw_extensions, COSDictionary)
    raw_extensions.set_item(
        COSName.get_pdf_name("BOGUS"), COSString("not a dict")
    )
    extensions = cat.get_developer_extensions()
    assert set(extensions.keys()) == {"ADBE"}
