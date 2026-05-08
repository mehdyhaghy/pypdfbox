from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption


def test_v45_filter_presence_helpers_require_well_formed_cos_values() -> None:
    raw = COSDictionary()
    raw.set_item("CF", COSArray())
    raw.set_item("StmF", COSString("StdCF"))
    raw.set_item("StrF", COSDictionary())
    raw.set_item("EFF", COSString("DefaultCryptFilter"))

    encryption = PDEncryption(raw)

    assert encryption.get_cf() is None
    assert encryption.get_stm_f() is None
    assert encryption.get_stream_filter_name() == "Identity"
    assert encryption.get_str_f() is None
    assert encryption.get_string_filter_name() == "Identity"
    assert encryption.get_eff() is None
    assert encryption.has_cf() is False
    assert encryption.has_stm_f() is False
    assert encryption.has_str_f() is False
    assert encryption.has_eff() is False


def test_v45_filter_presence_and_clear_helpers_round_trip() -> None:
    encryption = PDEncryption()
    cf = COSDictionary()

    assert encryption.has_cf() is False
    assert encryption.has_stm_f() is False
    assert encryption.has_str_f() is False
    assert encryption.has_eff() is False

    encryption.set_cf(cf)
    encryption.set_stm_f("StdCF")
    encryption.set_str_f("StdCF")
    encryption.set_eff("DefaultCryptFilter")

    assert encryption.get_cf() is cf
    assert encryption.get_stm_f() == "StdCF"
    assert encryption.get_str_f() == "StdCF"
    assert encryption.get_eff() == "DefaultCryptFilter"
    assert encryption.has_cf() is True
    assert encryption.has_stm_f() is True
    assert encryption.has_str_f() is True
    assert encryption.has_eff() is True

    encryption.clear_cf()
    encryption.clear_stm_f()
    encryption.clear_str_f()
    encryption.clear_eff()

    assert encryption.get_cf() is None
    assert encryption.get_stm_f() is None
    assert encryption.get_stream_filter_name() == "Identity"
    assert encryption.get_str_f() is None
    assert encryption.get_string_filter_name() == "Identity"
    assert encryption.get_eff() is None
    assert encryption.has_cf() is False
    assert encryption.has_stm_f() is False
    assert encryption.has_str_f() is False
    assert encryption.has_eff() is False


def test_v45_filter_name_setters_accept_none_as_clear() -> None:
    encryption = PDEncryption()
    encryption.set_stm_f("StdCF")
    encryption.set_str_f("StdCF")
    encryption.set_eff("DefaultCryptFilter")

    encryption.set_stm_f(None)
    encryption.set_str_f(None)
    encryption.set_eff(None)

    assert encryption.get_cos_object().get_dictionary_object(COSName.get_pdf_name("StmF")) is None
    assert encryption.get_cos_object().get_dictionary_object(COSName.get_pdf_name("StrF")) is None
    assert encryption.get_cos_object().get_dictionary_object(COSName.get_pdf_name("EFF")) is None
    assert encryption.has_stm_f() is False
    assert encryption.has_str_f() is False
    assert encryption.has_eff() is False
