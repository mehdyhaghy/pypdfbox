from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from tests.multipdf import test_pdf_merger_utility_wave404 as wave404


def test_wave935_identity_cloner_merges_non_excluded_missing_keys_only() -> None:
    src = COSDictionary()
    dst = COSDictionary()
    keep = COSName.get_pdf_name("Keep")
    excluded = COSName.get_pdf_name("Excluded")
    existing = COSName.get_pdf_name("Existing")
    src.set_item(keep, COSInteger.get(1))
    src.set_item(excluded, COSInteger.get(2))
    src.set_item(existing, COSInteger.get(3))
    dst.set_item(existing, COSInteger.get(99))

    cloner = wave404._IdentityCloner()  # noqa: SLF001
    cloner._clone_merge_cos_base(src, dst, {excluded})  # noqa: SLF001

    assert dst.get_item(keep) is COSInteger.get(1)
    assert dst.get_item(excluded) is None
    assert dst.get_item(existing) is COSInteger.get(99)
