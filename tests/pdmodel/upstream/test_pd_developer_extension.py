"""
Upstream parity tests for ``PDDeveloperExtension``.

There is **no upstream JUnit test** for this class in Apache PDFBox
3.0.x or trunk — PDFBox 3.0 does not ship a typed
``PDDeveloperExtension`` wrapper at all (only the ``COSName``
constants ``BASE_VERSION``, ``EXTENSION_LEVEL``, ``EXTENSIONS``).

The tests below mirror the **upstream-equivalent JUnit shape** that a
PDFBox port test would carry: round-trip ``BaseVersion`` /
``ExtensionLevel`` / ``URL``, default-construct sets ``/Type``, and
the catalog ``/Extensions`` mapping behaves like a Java
``Map<String, PDDeveloperExtension>``. If upstream later adds such a
test class, the assertions here remain a strict subset.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel import PDDeveloperExtension, PDDocument


# Java: assertEquals("DeveloperExtensions",
#       ext.getCOSObject().getNameAsString(COSName.TYPE));
def test_default_type_is_developer_extensions() -> None:
    ext = PDDeveloperExtension()
    cos = ext.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "DeveloperExtensions"  # type: ignore[attr-defined]


# Java: ext.setBaseVersion("1.7");
#       assertEquals("1.7", ext.getBaseVersion());
def test_base_version_round_trip() -> None:
    ext = PDDeveloperExtension()
    ext.set_base_version("1.7")
    assert ext.get_base_version() == "1.7"


# Java: assertNull(ext.getBaseVersion()); on a fresh dict.
def test_base_version_default_null() -> None:
    ext = PDDeveloperExtension()
    assert ext.get_base_version() is None


# Java: ext.setExtensionLevel(3);
#       assertEquals(3, ext.getExtensionLevel());
def test_extension_level_round_trip() -> None:
    ext = PDDeveloperExtension()
    ext.set_extension_level(3)
    assert ext.get_extension_level() == 3


# Java: assertEquals(-1, ext.getExtensionLevel());
# (PDFBox's ``COSDictionary.getInt`` default for missing keys is -1.)
def test_extension_level_default_is_minus_one() -> None:
    ext = PDDeveloperExtension()
    assert ext.get_extension_level() == -1


# Java equivalent: ext.setURL("https://...");
# pypdfbox enrichment over upstream PDFBox 3.0 (PDF 2.0 entry).
def test_url_round_trip() -> None:
    ext = PDDeveloperExtension()
    ext.set_url("https://example.org/ext")
    assert ext.get_url() == "https://example.org/ext"


# Java: COSDictionary dict = new COSDictionary();
#       dict.setName(COSName.BASE_VERSION, "1.7");
#       PDDeveloperExtension ext = new PDDeveloperExtension(dict);
#       assertEquals("1.7", ext.getBaseVersion());
def test_wrap_existing_cos_dictionary() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("BaseVersion"), COSName.get_pdf_name("1.7"))
    raw.set_item(COSName.get_pdf_name("ExtensionLevel"), COSInteger.get(3))
    ext = PDDeveloperExtension(raw)
    assert ext.get_base_version() == "1.7"
    assert ext.get_extension_level() == 3
    # Constructor should backfill /Type when missing.
    assert raw.get_name(COSName.TYPE) == "DeveloperExtensions"  # type: ignore[attr-defined]


# Java: catalog.getDeveloperExtensions() returns a Map; default empty.
def test_catalog_developer_extensions_default_empty() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    assert cat.get_developer_extensions() == {}


# Java equivalent of upstream-style:
#   PDDeveloperExtension ext = new PDDeveloperExtension();
#   ext.setBaseVersion("1.7");
#   ext.setExtensionLevel(3);
#   catalog.addDeveloperExtension("ADBE", ext);
#   assertEquals("1.7", catalog.getDeveloperExtensions().get("ADBE").getBaseVersion());
def test_catalog_add_and_round_trip_through_extensions_map() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    ext = PDDeveloperExtension()
    ext.set_base_version("1.7")
    ext.set_extension_level(3)
    cat.add_developer_extension("ADBE", ext)

    extensions = cat.get_developer_extensions()
    assert "ADBE" in extensions
    adbe = extensions["ADBE"]
    assert adbe.get_base_version() == "1.7"
    assert adbe.get_extension_level() == 3


# Java: catalog.setDeveloperExtensions(null) removes /Extensions.
def test_catalog_set_extensions_null_removes_entry() -> None:
    doc = PDDocument()
    cat = doc.get_document_catalog()
    ext = PDDeveloperExtension()
    ext.set_base_version("1.7")
    ext.set_extension_level(3)
    cat.add_developer_extension("ADBE", ext)
    cat.set_developer_extensions(None)
    assert cat.get_developer_extensions() == {}
    assert not cat.get_cos_object().contains_key(
        COSName.get_pdf_name("Extensions")
    )


# Sanity: /URL is encoded as a COSString (text), not a COSName.
def test_url_is_stored_as_cos_string() -> None:
    ext = PDDeveloperExtension()
    ext.set_url("https://example.org/ext")
    raw = ext.get_cos_object().get_dictionary_object(COSName.get_pdf_name("URL"))
    assert isinstance(raw, COSString)
