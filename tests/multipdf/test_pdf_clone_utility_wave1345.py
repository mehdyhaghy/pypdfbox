"""Wave 1345: residual coverage for ``PDFCloneUtility``.

Targets:
  - the ``seen_pairs is None`` default-construct branch of
    ``clone_merge_cos_base`` (line 193-194);
  - each of the private back-compat shims (``_clone_cos_*``,
    ``_clone_merge_cos_base``, ``_has_self_reference``) that wrap the
    public mirrors (lines 257, 260, 263, 266, 274, 278).
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
)
from pypdfbox.multipdf import PDFCloneUtility
from pypdfbox.pdmodel import PDDocument


def test_clone_merge_cos_base_default_seen_pairs_none() -> None:
    """Calling ``clone_merge_cos_base`` without ``seen_pairs`` engages
    the default-construct path (line 193-194)."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSArray()
        src.add(COSInteger.get(1))
        target = COSArray()
        # No third argument — exercises the default ``seen_pairs = set()``.
        cloner.clone_merge_cos_base(src, target)
        assert target.size() == 1
        assert target.get_int(0) == 1


def test_back_compat_shim_clone_cos_base_for_new_document() -> None:
    """The leading-underscore alias proxies to the public method."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSDictionary()
        src.set_name("Type", "Page")
        clone = cloner._clone_cos_base_for_new_document(src)
        assert isinstance(clone, COSDictionary)
        assert clone is not src
        assert clone.get_name("Type") == "Page"


def test_back_compat_shim_clone_cos_array() -> None:
    """``_clone_cos_array`` mirrors ``clone_cos_array``."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSArray()
        src.add(COSInteger.get(5))
        clone = cloner._clone_cos_array(src)
        assert isinstance(clone, COSArray)
        assert clone is not src
        assert clone.get_int(0) == 5


def test_back_compat_shim_clone_cos_stream() -> None:
    """``_clone_cos_stream`` mirrors ``clone_cos_stream``."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSStream()
        src.set_int("Length", 0)
        clone = cloner._clone_cos_stream(src)
        assert isinstance(clone, COSStream)
        assert clone is not src
        assert clone.get_int("Length") == 0


def test_back_compat_shim_clone_cos_dictionary() -> None:
    """``_clone_cos_dictionary`` mirrors ``clone_cos_dictionary``."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSDictionary()
        src.set_int("Count", 7)
        clone = cloner._clone_cos_dictionary(src)
        assert isinstance(clone, COSDictionary)
        assert clone is not src
        assert clone.get_int("Count") == 7


def test_back_compat_shim_clone_merge_cos_base() -> None:
    """``_clone_merge_cos_base`` mirrors ``clone_merge_cos_base``."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSArray()
        src.add(COSInteger.get(9))
        target = COSArray()
        cloner._clone_merge_cos_base(src, target)
        assert target.get_int(0) == 9


def test_back_compat_shim_has_self_reference() -> None:
    """``_has_self_reference`` proxies to the static public method."""
    parent = COSDictionary()
    cyclic_obj = COSObject(1, 0, resolved=parent)
    # Direct reference: value resolves to parent itself.
    assert PDFCloneUtility._has_self_reference(parent, cyclic_obj) is True
    # Non-cyclic case: value resolves to a different COSBase.
    not_parent = COSDictionary()
    fresh_obj = COSObject(2, 0, resolved=not_parent)
    assert PDFCloneUtility._has_self_reference(parent, fresh_obj) is False
    # And a plain primitive value isn't a reference at all.
    assert PDFCloneUtility._has_self_reference(parent, COSInteger.get(1)) is False


def test_clone_merge_cos_base_skips_when_target_dictionary_entry_exists() -> None:
    """The dict-merge branch recurses into the existing entry when both
    sides carry the same key — exercises the ``existing is not None``
    recursion path."""
    with PDDocument() as dst:
        cloner = PDFCloneUtility(dst)
        src = COSDictionary()
        src_inner = COSArray()
        src_inner.add(COSInteger.get(1))
        src.set_item(COSName.get_pdf_name("K"), src_inner)
        target = COSDictionary()
        target_inner = COSArray()
        target.set_item(COSName.get_pdf_name("K"), target_inner)
        cloner.clone_merge_cos_base(src, target, set())
        # The inner array on the target side should now contain the merged
        # source entry (clone of COSInteger.get(1)).
        merged_inner = target.get_dictionary_object(COSName.get_pdf_name("K"))
        assert isinstance(merged_inner, COSArray)
        assert merged_inner.size() == 1
