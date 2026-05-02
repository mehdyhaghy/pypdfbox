"""Round-out coverage for PDCIDSystemInfo (Wave 186).

Covers the three-arg constructor, registry/ordering constants,
``is_identity`` / ``is_adobe`` predicates, and value-equality / hashing
added on top of the lite surface.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_cid_system_info import PDCIDSystemInfo

_REGISTRY = COSName.get_pdf_name("Registry")
_ORDERING = COSName.get_pdf_name("Ordering")
_SUPPLEMENT = COSName.get_pdf_name("Supplement")


# ---------- 3-arg constructor ----------


def test_three_arg_constructor_populates_all_entries() -> None:
    info = PDCIDSystemInfo("Adobe", "Japan1", 6)
    assert info.get_registry() == "Adobe"
    assert info.get_ordering() == "Japan1"
    assert info.get_supplement() == 6
    assert str(info) == "Adobe-Japan1-6"


def test_three_arg_constructor_writes_to_underlying_dict() -> None:
    info = PDCIDSystemInfo("Adobe", "Identity", 0)
    cos = info.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_string(_REGISTRY) == "Adobe"
    assert cos.get_string(_ORDERING) == "Identity"
    assert cos.get_int(_SUPPLEMENT, -1) == 0


def test_three_arg_constructor_coerces_supplement_to_int() -> None:
    # Plain int float-likes (e.g. ``True``) coerce; floats are rejected
    # by the underlying COS setter, so we restrict to integers / int-likes.
    info = PDCIDSystemInfo("Adobe", "GB1", True)  # noqa: FBT003
    assert info.get_supplement() == 1


def test_three_arg_constructor_rejects_non_string_registry() -> None:
    with pytest.raises(TypeError):
        PDCIDSystemInfo(123, "Identity", 0)  # type: ignore[arg-type]


def test_three_arg_constructor_requires_all_three_args_when_ordering_set() -> None:
    with pytest.raises(TypeError):
        PDCIDSystemInfo("Adobe", "Identity")  # missing supplement


def test_three_arg_constructor_requires_all_three_args_when_supplement_set() -> None:
    with pytest.raises(TypeError):
        PDCIDSystemInfo("Adobe", supplement=0)  # missing ordering


# ---------- 1-arg / 0-arg backward compat ----------


def test_no_arg_constructor_yields_empty_wrapper() -> None:
    info = PDCIDSystemInfo()
    assert info.get_registry() is None
    assert info.get_ordering() is None
    assert info.get_supplement() == 0
    assert isinstance(info.get_cos_object(), COSDictionary)


def test_one_arg_constructor_wraps_existing_dict() -> None:
    raw = COSDictionary()
    raw.set_string(_REGISTRY, "Adobe")
    raw.set_string(_ORDERING, "CNS1")
    raw.set_int(_SUPPLEMENT, 4)

    info = PDCIDSystemInfo(raw)
    assert info.get_cos_object() is raw
    assert info.get_registry() == "Adobe"
    assert info.get_ordering() == "CNS1"
    assert info.get_supplement() == 4


# ---------- registry / ordering constants ----------


def test_registry_and_ordering_constants_match_known_strings() -> None:
    assert PDCIDSystemInfo.REGISTRY_ADOBE == "Adobe"
    assert PDCIDSystemInfo.ORDERING_IDENTITY == "Identity"
    assert PDCIDSystemInfo.ORDERING_GB1 == "GB1"
    assert PDCIDSystemInfo.ORDERING_CNS1 == "CNS1"
    assert PDCIDSystemInfo.ORDERING_JAPAN1 == "Japan1"
    assert PDCIDSystemInfo.ORDERING_KOREA1 == "Korea1"
    assert PDCIDSystemInfo.ORDERING_KR == "KR"


def test_constants_are_usable_in_three_arg_constructor() -> None:
    info = PDCIDSystemInfo(
        PDCIDSystemInfo.REGISTRY_ADOBE,
        PDCIDSystemInfo.ORDERING_KOREA1,
        2,
    )
    assert str(info) == "Adobe-Korea1-2"


# ---------- predicates ----------


def test_is_identity_true_for_adobe_identity() -> None:
    info = PDCIDSystemInfo("Adobe", "Identity", 0)
    assert info.is_identity() is True
    assert info.is_adobe() is True


def test_is_identity_false_for_adobe_japan1() -> None:
    info = PDCIDSystemInfo("Adobe", "Japan1", 6)
    assert info.is_identity() is False
    assert info.is_adobe() is True


def test_is_identity_false_when_registry_not_adobe() -> None:
    info = PDCIDSystemInfo("Custom", "Identity", 0)
    assert info.is_identity() is False
    assert info.is_adobe() is False


def test_is_identity_false_for_empty_wrapper() -> None:
    info = PDCIDSystemInfo()
    assert info.is_identity() is False
    assert info.is_adobe() is False


# ---------- value equality / hashing ----------


def test_equal_when_three_fields_match_even_with_distinct_dicts() -> None:
    a = PDCIDSystemInfo("Adobe", "Japan1", 6)
    b = PDCIDSystemInfo("Adobe", "Japan1", 6)
    assert a is not b
    assert a.get_cos_object() is not b.get_cos_object()
    assert a == b
    assert hash(a) == hash(b)


def test_unequal_when_supplement_differs() -> None:
    a = PDCIDSystemInfo("Adobe", "Japan1", 6)
    b = PDCIDSystemInfo("Adobe", "Japan1", 7)
    assert a != b


def test_unequal_when_ordering_differs() -> None:
    a = PDCIDSystemInfo("Adobe", "Japan1", 6)
    b = PDCIDSystemInfo("Adobe", "Korea1", 6)
    assert a != b


def test_unequal_when_registry_differs() -> None:
    a = PDCIDSystemInfo("Adobe", "Japan1", 6)
    b = PDCIDSystemInfo("Custom", "Japan1", 6)
    assert a != b


def test_not_equal_to_non_cid_system_info() -> None:
    info = PDCIDSystemInfo("Adobe", "Japan1", 6)
    assert info != "Adobe-Japan1-6"
    assert info != ("Adobe", "Japan1", 6)
    assert info != 42


def test_hashable_can_be_used_in_set() -> None:
    a = PDCIDSystemInfo("Adobe", "Japan1", 6)
    b = PDCIDSystemInfo("Adobe", "Japan1", 6)  # same value, distinct dict
    c = PDCIDSystemInfo("Adobe", "Identity", 0)

    bag = {a, b, c}
    assert len(bag) == 2  # a and b dedup; c distinct
