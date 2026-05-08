from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.font.pd_cid_system_info import PDCIDSystemInfo

_REGISTRY = COSName.get_pdf_name("Registry")
_ORDERING = COSName.get_pdf_name("Ordering")
_SUPPLEMENT = COSName.get_pdf_name("Supplement")


def test_accessors_write_read_and_remove_registry_ordering() -> None:
    info = PDCIDSystemInfo()

    info.set_registry("Adobe")
    info.set_ordering("Japan1")
    info.set_supplement(6)

    assert info.get_registry() == "Adobe"
    assert info.get_ordering() == "Japan1"
    assert info.get_supplement() == 6
    assert str(info) == "Adobe-Japan1-6"

    info.set_registry(None)
    info.set_ordering(None)

    cos = info.get_cos_object()
    assert info.get_registry() is None
    assert info.get_ordering() is None
    assert cos.contains_key(_REGISTRY) is False
    assert cos.contains_key(_ORDERING) is False
    assert cos.get_int(_SUPPLEMENT) == 6


def test_no_arg_defaults_are_empty_and_not_identity_or_adobe() -> None:
    info = PDCIDSystemInfo()

    assert isinstance(info.get_cos_object(), COSDictionary)
    assert info.get_registry() is None
    assert info.get_ordering() is None
    assert info.get_supplement() == 0
    assert info.is_identity() is False
    assert info.is_adobe() is False
    assert str(info) == "null-null-0"


def test_string_representation_matches_java_null_text_for_missing_parts() -> None:
    info = PDCIDSystemInfo()
    info.set_registry("Adobe")

    assert str(info) == "Adobe-null-0"

    info.set_registry(None)
    info.set_ordering("Identity")

    assert str(info) == "null-Identity-0"


def test_cos_dictionary_round_trip_preserves_backing_object() -> None:
    raw = COSDictionary()
    raw.set_string(_REGISTRY, "Adobe")
    raw.set_string(_ORDERING, "Identity")
    raw.set_int(_SUPPLEMENT, 0)

    info = PDCIDSystemInfo(raw)
    assert info.get_cos_object() is raw
    assert info.is_identity() is True

    raw.set_string(_ORDERING, "Korea1")
    raw.set_int(_SUPPLEMENT, 2)

    assert info.get_registry() == "Adobe"
    assert info.get_ordering() == "Korea1"
    assert info.get_supplement() == 2
    assert info.is_identity() is False

    round_tripped = PDCIDSystemInfo(info.get_cos_object())
    assert round_tripped.get_cos_object() is raw
    assert round_tripped == info
    assert str(round_tripped) == "Adobe-Korea1-2"


def test_value_equality_returns_not_implemented_for_other_types() -> None:
    info = PDCIDSystemInfo("Adobe", "Japan1", 6)

    assert info.__eq__(object()) is NotImplemented
    assert info != object()
    assert info != ("Adobe", "Japan1", 6)


def test_hash_tracks_registry_ordering_supplement_values() -> None:
    original = PDCIDSystemInfo("Adobe", "GB1", 5)
    same = PDCIDSystemInfo("Adobe", "GB1", 5)
    different = PDCIDSystemInfo("Adobe", "GB1", 4)

    assert hash(original) == hash(same)
    assert {original, same, different} == {original, different}


def test_constructor_rejects_malformed_single_argument_shapes() -> None:
    with pytest.raises(TypeError, match="COSDictionary"):
        PDCIDSystemInfo(COSArray())  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="COSDictionary"):
        PDCIDSystemInfo(123)  # type: ignore[arg-type]


def test_constructor_rejects_incomplete_three_part_shapes() -> None:
    with pytest.raises(TypeError, match="requires all three arguments"):
        PDCIDSystemInfo("Adobe", "Identity")

    with pytest.raises(TypeError, match="registry must be a str"):
        PDCIDSystemInfo(None, "Identity", 0)


def test_malformed_cos_entry_types_fall_back_to_accessor_defaults() -> None:
    raw = COSDictionary()
    raw.set_item(_REGISTRY, COSInteger.get(7))
    raw.set_item(_ORDERING, COSInteger.get(8))
    raw.set_string(_SUPPLEMENT, "not-an-int")

    info = PDCIDSystemInfo(raw)

    assert info.get_registry() is None
    assert info.get_ordering() is None
    assert info.get_supplement() == 0
    assert info.is_identity() is False
    assert info.is_adobe() is False


def test_cos_name_text_and_float_supplement_are_accepted_by_cos_accessors() -> None:
    raw = COSDictionary()
    raw.set_name(_REGISTRY, "Adobe")
    raw.set_name(_ORDERING, "CNS1")
    raw.set_item(_SUPPLEMENT, COSFloat(4.9))

    info = PDCIDSystemInfo(raw)

    assert info.get_registry() == "Adobe"
    assert info.get_ordering() == "CNS1"
    assert info.get_supplement() == 4
