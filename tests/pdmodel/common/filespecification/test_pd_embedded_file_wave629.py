from __future__ import annotations

import datetime as dt

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSObject, COSStream
from pypdfbox.pdmodel.common.filespecification import PDEmbeddedFile

_CHECK_SUM = COSName.get_pdf_name("CheckSum")
_CREATION_DATE = COSName.get_pdf_name("CreationDate")
_MAC = COSName.get_pdf_name("Mac")
_PARAMS = COSName.get_pdf_name("Params")
_RES_FORK = COSName.get_pdf_name("ResFork")
_SIZE = COSName.SIZE  # type: ignore[attr-defined]
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]


def test_wave629_clear_params_removes_all_nested_metadata() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_size(123)
    embedded.set_creator("writer")
    embedded.set_mac_creator("MACS")

    assert embedded.has_params() is True
    assert embedded.has_mac_info() is True

    embedded.clear_params()

    assert embedded.has_params() is False
    assert embedded.get_size() == -1
    assert embedded.get_creator() is None
    assert embedded.get_mac_creator() is None


def test_wave629_clear_mac_info_keeps_non_mac_params() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_size(456)
    embedded.set_mac_subtype("TEXT")
    embedded.set_mac_creator("ttxt")

    embedded.clear_mac_info()

    assert embedded.has_params() is True
    assert embedded.has_mac_info() is False
    assert embedded.get_size() == 456
    assert embedded.get_mac_subtype() is None
    assert embedded.get_mac_creator() is None


def test_wave629_mac_string_getters_ignore_malformed_mac_entry() -> None:
    embedded = PDEmbeddedFile()
    params = COSDictionary()
    params.set_item(_MAC, COSInteger.get(7))
    embedded.get_cos_object().set_item(_PARAMS, params)

    assert embedded.has_mac_info() is False
    assert embedded.get_mac_subtype() is None
    assert embedded.get_mac_creator() is None


def test_wave629_clearing_mac_fields_does_not_create_params() -> None:
    embedded = PDEmbeddedFile()

    embedded.clear_mac_subtype()
    embedded.clear_mac_creator()
    embedded.clear_mac_resource_fork()

    assert embedded.has_params() is False
    assert embedded.has_mac_info() is False


def test_wave629_mac_resource_fork_rejects_non_stream() -> None:
    embedded = PDEmbeddedFile()
    params = COSDictionary()
    mac = COSDictionary()
    mac.set_item(_RES_FORK, COSInteger.get(99))
    params.set_item(_MAC, mac)
    embedded.get_cos_object().set_item(_PARAMS, params)

    assert embedded.get_mac_resource_fork() is None
    assert embedded.has_mac_resource_fork() is False


def test_wave629_set_mac_resource_fork_replaces_malformed_mac_dict() -> None:
    embedded = PDEmbeddedFile()
    params = COSDictionary()
    params.set_item(_MAC, COSInteger.get(1))
    embedded.get_cos_object().set_item(_PARAMS, params)
    stream = COSStream()

    embedded.set_mac_resource_fork(stream)

    assert embedded.get_mac_resource_fork() is stream
    assert embedded.has_mac_res_fork() is True


def test_wave629_has_date_predicates_track_presence_not_parse_success() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_creation_date("not-a-pdf-date")
    embedded.set_mod_date("D:20260230000000Z")

    assert embedded.has_creation_date() is True
    assert embedded.has_mod_date() is True
    assert embedded.get_creation_date() is None
    assert embedded.get_mod_date() is None


def test_wave629_date_setters_clear_without_creating_params() -> None:
    embedded = PDEmbeddedFile()

    embedded.clear_creation_date()
    embedded.clear_mod_date()
    embedded.clear_size()
    embedded.clear_creator()
    embedded.clear_check_sum()

    assert embedded.has_params() is False


def test_wave629_naive_datetime_is_formatted_as_utc_marker() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_mod_date(dt.datetime(2026, 5, 9, 1, 2, 3))

    params = embedded.get_cos_object().get_dictionary_object(_PARAMS)
    assert isinstance(params, COSDictionary)
    # Upstream DateConverter.toString renders UTC as +00'00', never Z.
    assert params.get_string(COSName.get_pdf_name("ModDate")) == (
        "D:20260509010203+00'00'"
    )
    assert embedded.get_mod_date() == dt.datetime(2026, 5, 9, 1, 2, 3, tzinfo=dt.UTC)


def test_wave629_parse_date_without_prefix_defaults_missing_fields_to_one() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_creation_date("2026")

    assert embedded.get_creation_date() == dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


def test_wave629_get_check_sum_ignores_non_string_entry() -> None:
    embedded = PDEmbeddedFile()
    params = COSDictionary()
    params.set_item(_CHECK_SUM, COSInteger.get(5))
    embedded.get_cos_object().set_item(_PARAMS, params)

    assert embedded.get_check_sum() is None
    assert embedded.has_check_sum() is False
    assert embedded.get_check_sum_string() is None


def test_wave629_set_check_sum_accepts_memoryview_and_clears() -> None:
    embedded = PDEmbeddedFile()
    payload = memoryview(bytes(range(16)))

    embedded.set_check_sum(payload)
    assert embedded.get_check_sum() == bytes(range(16))
    embedded.clear_check_sum()
    assert embedded.get_check_sum() is None


def test_wave629_existing_stream_preserves_type_and_indirect_params() -> None:
    raw = COSStream()
    params = COSDictionary()
    params.set_item(_SIZE, COSInteger.get(88))
    raw.set_item(_PARAMS, COSObject(629, 0, resolved=params))
    embedded = PDEmbeddedFile(raw)

    assert embedded.get_cos_object().get_dictionary_object(COSName.TYPE) is None  # type: ignore[attr-defined]
    assert embedded.get_size() == 88


def test_wave629_subtype_clear_removes_string_form_entry() -> None:
    embedded = PDEmbeddedFile()
    embedded.get_cos_object().set_string(_SUBTYPE, "text/plain")

    assert embedded.has_subtype() is True
    embedded.clear_subtype()
    assert embedded.has_subtype() is False
