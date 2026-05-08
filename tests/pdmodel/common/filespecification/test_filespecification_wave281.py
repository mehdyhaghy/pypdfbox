from __future__ import annotations

import datetime as _dt

from pypdfbox.cos import COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.common.filespecification import (
    PDComplexFileSpecification,
    PDEmbeddedFile,
)


def test_complex_embedded_file_cache_tracks_replaced_ef_dictionary() -> None:
    spec = PDComplexFileSpecification()
    first = PDEmbeddedFile()
    spec.set_embedded_file(first)
    assert spec.has_embedded_file() is True

    cos = spec.get_cos_object()
    cos.set_item(COSName.get_pdf_name("EF"), COSString("not-a-dictionary"))

    assert spec.has_embedded_files() is False
    assert spec.has_embedded_file() is False
    assert spec.get_embedded_file() is None

    second = PDEmbeddedFile()
    spec.set_embedded_file(second)
    fetched = spec.get_embedded_file()
    assert fetched is not None
    assert fetched.get_cos_object() is second.get_cos_object()


def test_complex_embedded_file_slot_predicates_and_clearers() -> None:
    spec = PDComplexFileSpecification()
    f_file = PDEmbeddedFile()
    uf_file = PDEmbeddedFile()
    dos_file = PDEmbeddedFile()
    mac_file = PDEmbeddedFile()
    unix_file = PDEmbeddedFile()

    spec.set_embedded_file(f_file)
    spec.set_embedded_file_unicode(uf_file)
    spec.set_embedded_file_dos(dos_file)
    spec.set_embedded_file_mac(mac_file)
    spec.set_embedded_file_unix(unix_file)

    assert spec.has_embedded_file() is True
    assert spec.has_embedded_file_unicode() is True
    assert spec.has_embedded_file_dos() is True
    assert spec.has_embedded_file_mac() is True
    assert spec.has_embedded_file_unix() is True

    spec.clear_embedded_file_dos()
    assert spec.has_embedded_file_dos() is False
    assert spec.get_embedded_file_dos() is None
    assert spec.has_embedded_file() is True
    assert spec.has_embedded_file_unicode() is True
    assert spec.has_embedded_file_mac() is True
    assert spec.has_embedded_file_unix() is True

    spec.clear_embedded_file()
    spec.clear_embedded_file_unicode()
    spec.clear_embedded_file_mac()
    spec.clear_embedded_file_unix()
    assert spec.has_embedded_file() is False
    assert spec.has_embedded_file_unicode() is False
    assert spec.has_embedded_file_mac() is False
    assert spec.has_embedded_file_unix() is False
    assert spec.has_embedded_files() is True


def test_complex_embedded_file_slot_predicate_rejects_malformed_slot() -> None:
    spec = PDComplexFileSpecification()
    ef = COSDictionary()
    ef.set_item(COSName.get_pdf_name("F"), COSString("not-a-stream"))
    spec.get_cos_object().set_item(COSName.get_pdf_name("EF"), ef)

    assert spec.has_embedded_files() is True
    assert spec.has_embedded_file() is False
    assert spec.get_embedded_file() is None


def test_embedded_file_top_level_predicates_and_clearers() -> None:
    embedded = PDEmbeddedFile()
    when = _dt.datetime(2026, 5, 8, 12, 30, 0, tzinfo=_dt.UTC)

    embedded.set_subtype("text/plain")
    embedded.set_size(42)
    embedded.set_creation_date(when)
    embedded.set_mod_date(when)
    embedded.set_check_sum(b"\x00" * 16)
    embedded.set_creator("pypdfbox")

    assert embedded.has_subtype() is True
    assert embedded.has_size() is True
    assert embedded.has_creation_date() is True
    assert embedded.has_mod_date() is True
    assert embedded.has_check_sum() is True
    assert embedded.has_creator() is True

    embedded.clear_subtype()
    embedded.clear_size()
    embedded.clear_creation_date()
    embedded.clear_mod_date()
    embedded.clear_check_sum()
    embedded.clear_creator()

    assert embedded.has_subtype() is False
    assert embedded.has_size() is False
    assert embedded.has_creation_date() is False
    assert embedded.has_mod_date() is False
    assert embedded.has_check_sum() is False
    assert embedded.has_creator() is False


def test_embedded_file_mac_predicates_and_clearers() -> None:
    embedded = PDEmbeddedFile()
    resource_fork = COSStream()

    embedded.set_mac_subtype("TEXT")
    embedded.set_mac_creator("ttxt")
    embedded.set_mac_resource_fork(resource_fork)

    assert embedded.has_params() is True
    assert embedded.has_mac_info() is True
    assert embedded.has_mac_subtype() is True
    assert embedded.has_mac_creator() is True
    assert embedded.has_mac_resource_fork() is True
    assert embedded.has_mac_res_fork() is True

    embedded.clear_mac_subtype()
    embedded.clear_mac_creator()
    embedded.clear_mac_res_fork()

    assert embedded.has_mac_subtype() is False
    assert embedded.has_mac_creator() is False
    assert embedded.has_mac_resource_fork() is False
    assert embedded.has_mac_info() is True

    embedded.clear_mac_info()
    assert embedded.has_mac_info() is False
    assert embedded.has_params() is True

    embedded.clear_params()
    assert embedded.has_params() is False


def test_embedded_file_malformed_params_can_be_cleared_or_replaced() -> None:
    embedded = PDEmbeddedFile()
    embedded.get_cos_object().set_item(COSName.get_pdf_name("Params"), COSString("bad"))

    assert embedded.has_params() is False
    assert embedded.has_size() is False
    assert embedded.get_size() == -1

    embedded.clear_size()
    assert embedded.has_params() is False

    embedded.set_size(7)
    assert embedded.has_params() is True
    assert embedded.has_size() is True
    assert embedded.get_size() == 7

    embedded.clear_params()
    assert embedded.has_params() is False


def test_embedded_file_malformed_mac_dict_can_be_replaced() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_size(1)
    params = embedded.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Params"))
    assert isinstance(params, COSDictionary)
    params.set_item(COSName.get_pdf_name("Mac"), COSString("bad"))

    assert embedded.has_mac_info() is False
    assert embedded.has_mac_resource_fork() is False
    assert embedded.get_mac_resource_fork() is None

    resource_fork = COSStream()
    embedded.set_mac_resource_fork(resource_fork)
    assert embedded.has_mac_info() is True
    assert embedded.has_mac_resource_fork() is True
    assert embedded.get_mac_resource_fork() is resource_fork
