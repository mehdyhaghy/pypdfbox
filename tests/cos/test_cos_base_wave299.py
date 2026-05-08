from __future__ import annotations

from pypdfbox.cos import COSInteger, COSString


def test_wave299_direct_camelcase_aliases_share_base_flag() -> None:
    item = COSInteger.get(1)

    item.setDirect(True)
    assert item.isDirect() is True
    assert item.is_direct() is True

    item.set_direct(False)
    assert item.isDirect() is False


def test_wave299_need_to_be_updated_camelcase_aliases_share_base_flag() -> None:
    item = COSString(b"abc")

    item.setNeedToBeUpdated(True)
    assert item.isNeedToBeUpdated() is True
    assert item.is_needs_to_be_updated() is True

    item.set_needs_to_be_updated(False)
    assert item.isNeedToBeUpdated() is False
