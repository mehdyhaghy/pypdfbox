from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName, COSObject


def test_wave302_remove_object_removes_indirect_resolved_match() -> None:
    target = COSInteger.get(302)
    indirect = COSObject(30, 2, resolved=target)
    marker = COSName.get_pdf_name("Wave302Marker")
    cos_array = COSArray([marker, indirect])

    assert cos_array.remove_object(target) is True

    assert cos_array.to_list() == [marker]


def test_wave302_remove_object_prefers_first_matching_entry() -> None:
    target = COSInteger.get(302)
    indirect = COSObject(30, 2, resolved=target)
    cos_array = COSArray([target, indirect])

    assert cos_array.remove_object(target) is True

    assert cos_array.to_list() == [indirect]


def test_wave302_remove_object_returns_false_without_mutating_when_missing() -> None:
    indirect = COSObject(30, 2, resolved=COSInteger.get(302))
    cos_array = COSArray([indirect])

    assert cos_array.remove_object(COSInteger.get(999)) is False

    assert cos_array.to_list() == [indirect]
