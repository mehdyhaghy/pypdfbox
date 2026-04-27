from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.fdf import FDFCatalog, FDFDictionary


def test_default_constructor_is_empty() -> None:
    c = FDFCatalog()
    assert isinstance(c.get_cos_object(), COSDictionary)


def test_get_fdf_creates_empty_when_missing() -> None:
    c = FDFCatalog()
    fdf = c.get_fdf()
    assert isinstance(fdf, FDFDictionary)
    # Subsequent call returns the same wrapper.
    assert c.get_fdf() is fdf
    # And the catalog now carries a /FDF entry.
    assert c.get_cos_object().contains_key(COSName.get_pdf_name("FDF"))


def test_get_fdf_wraps_existing_dict() -> None:
    raw = COSDictionary()
    raw.set_string(COSName.get_pdf_name("Status"), "ready")
    cat = COSDictionary()
    cat.set_item(COSName.get_pdf_name("FDF"), raw)
    c = FDFCatalog(cat)
    fdf = c.get_fdf()
    assert fdf.get_status() == "ready"
    assert fdf.get_cos_object() is raw


def test_set_fdf_replaces_entry() -> None:
    c = FDFCatalog()
    new_fdf = FDFDictionary()
    new_fdf.set_status("new")
    c.set_fdf(new_fdf)
    assert c.get_fdf() is new_fdf
    assert c.get_fdf().get_status() == "new"


def test_set_fdf_none_removes_entry() -> None:
    c = FDFCatalog()
    c.get_fdf()  # materialize
    c.set_fdf(None)
    assert not c.get_cos_object().contains_key(COSName.get_pdf_name("FDF"))


def test_version_round_trip() -> None:
    c = FDFCatalog()
    assert c.get_version() is None
    c.set_version("1.4")
    assert c.get_version() == "1.4"
    c.set_version(None)
    assert c.get_version() is None
