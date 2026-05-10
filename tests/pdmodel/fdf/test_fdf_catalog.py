from __future__ import annotations

import io

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.fdf import FDFCatalog, FDFDictionary
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature


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


def test_get_signature_returns_none_when_absent() -> None:
    c = FDFCatalog()
    assert c.get_signature() is None


def test_signature_round_trip() -> None:
    c = FDFCatalog()
    sig = PDSignature()
    sig.set_filter(PDSignature.FILTER_ADOBE_PPKLITE)
    c.set_signature(sig)
    got = c.get_signature()
    assert got is not None
    assert got.get_cos_object() is sig.get_cos_object()
    assert got.get_filter() == PDSignature.FILTER_ADOBE_PPKLITE
    # The catalog now carries a /Sig entry.
    assert c.get_cos_object().contains_key(COSName.get_pdf_name("Sig"))


def test_set_signature_none_removes_entry() -> None:
    c = FDFCatalog()
    c.set_signature(PDSignature())
    assert c.get_signature() is not None
    c.set_signature(None)
    assert c.get_signature() is None
    assert not c.get_cos_object().contains_key(COSName.get_pdf_name("Sig"))


def test_write_xml_delegates_to_fdf() -> None:
    c = FDFCatalog()
    fdf = c.get_fdf()
    fdf.set_status("ready")  # /Status is not emitted by writeXML, but exercising
    buf = io.StringIO()
    c.write_xml(buf)
    # Empty FDF dict produces no <f>/<ids>/<fields> elements.
    assert buf.getvalue() == ""


def test_write_xml_emits_fields_via_fdf() -> None:
    from pypdfbox.pdmodel.fdf import FDFField

    c = FDFCatalog()
    fdf = c.get_fdf()
    field = FDFField()
    field.set_partial_field_name("name")
    fdf.set_fields([field])
    buf = io.StringIO()
    c.write_xml(buf)
    out = buf.getvalue()
    assert "<fields>" in out
    assert "</fields>" in out
