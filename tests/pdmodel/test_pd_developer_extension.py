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


def test_base_version_class_constants() -> None:
    assert PDDeveloperExtension.BASE_VERSION_1_3 == "1.3"
    assert PDDeveloperExtension.BASE_VERSION_1_4 == "1.4"
    assert PDDeveloperExtension.BASE_VERSION_1_5 == "1.5"
    assert PDDeveloperExtension.BASE_VERSION_1_6 == "1.6"
    assert PDDeveloperExtension.BASE_VERSION_1_7 == "1.7"
    assert PDDeveloperExtension.BASE_VERSION_2_0 == "2.0"


def test_eq_uses_backing_dict_identity() -> None:
    raw = COSDictionary()
    a = PDDeveloperExtension(raw)
    b = PDDeveloperExtension(raw)
    assert a == b
    assert hash(a) == hash(b)


def test_eq_distinguishes_separate_dicts() -> None:
    a = PDDeveloperExtension()
    b = PDDeveloperExtension()
    assert a != b


def test_eq_returns_notimplemented_for_other_types() -> None:
    a = PDDeveloperExtension()
    assert (a == "not an extension") is False
    assert (a == 42) is False


def test_hash_allows_use_in_sets() -> None:
    a = PDDeveloperExtension()
    b = PDDeveloperExtension()
    members = {a, b, a}
    assert len(members) == 2


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


# ---------- Wave 229: typed accessors / predicates / defensive reads ----------


def test_get_type_default_is_developer_extensions() -> None:
    ext = PDDeveloperExtension()
    assert ext.get_type() == "DeveloperExtensions"


def test_get_type_when_dictionary_lacks_type_returns_none() -> None:
    raw = COSDictionary()
    # Skip the wrapper's auto-backfill by removing /Type after construction.
    ext = PDDeveloperExtension(raw)
    raw.remove_item(COSName.TYPE)  # type: ignore[attr-defined]
    assert ext.get_type() is None


def test_has_base_version_predicate() -> None:
    ext = PDDeveloperExtension()
    assert ext.has_base_version() is False
    ext.set_base_version("1.7")
    assert ext.has_base_version() is True
    ext.set_base_version(None)
    assert ext.has_base_version() is False


def test_has_extension_level_predicate() -> None:
    ext = PDDeveloperExtension()
    assert ext.has_extension_level() is False
    ext.set_extension_level(3)
    assert ext.has_extension_level() is True


def test_has_url_predicate() -> None:
    ext = PDDeveloperExtension()
    assert ext.has_url() is False
    ext.set_url("https://example.org/x")
    assert ext.has_url() is True
    ext.set_url(None)
    assert ext.has_url() is False


def test_get_extension_level_with_custom_default() -> None:
    ext = PDDeveloperExtension()
    # Absent: caller-supplied default returned, not the -1 sentinel.
    assert ext.get_extension_level(0) == 0
    assert ext.get_extension_level(99) == 99
    # Once present, default is ignored.
    ext.set_extension_level(7)
    assert ext.get_extension_level(0) == 7
    assert ext.get_extension_level(99) == 7


def test_set_base_version_accepts_cos_name() -> None:
    ext = PDDeveloperExtension()
    name = COSName.get_pdf_name("1.7")
    ext.set_base_version(name)
    assert ext.get_base_version() == "1.7"
    raw = ext.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("BaseVersion")
    )
    # The exact COSName instance flows through unchanged.
    assert raw is name


def test_get_base_version_accepts_cos_string_payload() -> None:
    # Defensive read: some producers store /BaseVersion as a COSString.
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("DeveloperExtensions"))  # type: ignore[attr-defined]
    raw.set_item(COSName.get_pdf_name("BaseVersion"), COSString("1.7"))
    ext = PDDeveloperExtension(raw)
    assert ext.get_base_version() == "1.7"
