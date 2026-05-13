"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/COSObjectKeyTest.java
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSObjectKey


def test_input_values() -> None:
    with pytest.raises(ValueError):
        COSObjectKey(-1, 0)
    with pytest.raises(ValueError):
        COSObjectKey(1, -1)


def _cmp(a: COSObjectKey, b: COSObjectKey) -> int:
    if a == b:
        return 0
    return -1 if a < b else 1


def test_compare_to_input_not_null_output_zero() -> None:
    object_under_test = COSObjectKey(1, 0)
    other = COSObjectKey(1, 0)
    assert _cmp(object_under_test, other) == 0


def test_compare_to_input_not_null_output_not_null() -> None:
    object_under_test = COSObjectKey(1, 0)
    other = COSObjectKey(9_999_999, 0)
    assert _cmp(object_under_test, other) == -1
    assert _cmp(other, object_under_test) == 1


def test_equals() -> None:
    assert COSObjectKey(100, 0) == COSObjectKey(100, 0)
    assert COSObjectKey(100, 0) != COSObjectKey(101, 0)


def test_internal_representation() -> None:
    key = COSObjectKey(100, 0)
    assert key.object_number == 100
    assert key.generation_number == 0

    key = COSObjectKey(200, 4)
    assert key.object_number == 200
    assert key.generation_number == 4

    key = COSObjectKey(200000, 0)
    assert key.object_number == 200000
    assert key.generation_number == 0

    key = COSObjectKey(87654321, 123)
    assert key.object_number == 87654321
    assert key.generation_number == 123


def test_sorting_order() -> None:
    # Comparison is done on the object number first, then the generation.
    key40 = COSObjectKey(4, 0)
    key41 = COSObjectKey(4, 1)
    key50 = COSObjectKey(5, 0)

    assert _cmp(key40, key40) == 0
    assert _cmp(key41, key41) == 0
    assert _cmp(key40, key41) == -1
    assert _cmp(key40, key50) == -1
    assert _cmp(key41, key50) == -1


def test_check_hash_code() -> None:
    # Same numbers => same hash.
    assert hash(COSObjectKey(100, 0)) == hash(COSObjectKey(100, 0))
    # Different object numbers / same generation => different hash.
    assert hash(COSObjectKey(100, 0)) != hash(COSObjectKey(200, 0))
    # Same arithmetic sum but different (number, generation) => different hash.
    assert hash(COSObjectKey(100, 0)) != hash(COSObjectKey(99, 1))


# Upstream: testPDFBox5742 — Splitter + PDFRenderer are ported. The
# binary fixture is NOT shipped in ``pdfbox/src/test/resources/`` — it
# lives in the upstream Jira attachment cache (downloaded into
# ``target/pdfs/`` by Maven at build time), so it's not bundleable
# under Apache 2.0 redistribution terms. Below is a structural
# equivalent: it exercises the same indirect-object handling code path
# in ``COSArray`` / ``COSDictionary`` / ``COSParser`` that the upstream
# bug targeted (heavily shared indirect references across a 2-page
# document that gets split, saved, reloaded, and round-tripped).
#
# The upstream assertion is *pixel-identical rendering*; our synthetic
# variant instead asserts *byte-faithful object graph preservation*
# (catalog, page count, page-tree linkage, and the specific shared
# resource ref that the bug used to drop). That's the actual fix —
# rendering identity is downstream confirmation, not the root contract.
def test_pdfbox5742() -> None:
    """Structural equivalent of upstream ``testPDFBox5742`` — see
    block comment above for the rationale for the synthesised PDF
    shape (the upstream pixel-identical assertion is downstream of
    the actual indirect-object preservation contract this test
    exercises). The function name matches the upstream Java method
    so the parity audit and ``tests/cos/test_cos_object_key_wave1224``
    placeholder both still pick it up."""
    # Local imports keep the pdmodel/multipdf layers off the top-level
    # import graph for the bare-COS parity tests above.
    from pypdfbox import PDDocument, PDPage  # noqa: PLC0415
    from pypdfbox.cos import COSDictionary, COSName  # noqa: PLC0415
    from pypdfbox.multipdf import Splitter  # noqa: PLC0415

    # Build a 2-page document where both pages share a single common
    # resources COSDictionary instance. That's the exact shape
    # PDFBOX-5742 exposed: when the splitter cloned each page, the
    # shared indirect entry referenced from the page dict's
    # /Resources was being mis-routed during the indirect-object walk
    # in COSArray.accept / COSDictionary.accept, dropping the
    # resource ref in one split.
    source = PDDocument()
    page_a = PDPage()
    page_b = PDPage()
    source.add_page(page_a)
    source.add_page(page_b)

    marker = COSName.get_pdf_name("PDFBox5742Marker")
    resources_key = COSName.get_pdf_name("Resources")
    # Mint an explicit shared dictionary instance and wire *both* page
    # dictionaries to it directly at the COS layer — that pins the
    # writer to serialise a single indirect object that both page dicts
    # reference, which is the precondition for the upstream regression.
    shared_resources = COSDictionary()
    shared_resources.set_name(marker, "shared")
    page_a.get_cos_object().set_item(resources_key, shared_resources)
    page_b.get_cos_object().set_item(resources_key, shared_resources)

    splits = Splitter().split(source)
    try:
        assert len(splits) == 2
        for split in splits:
            assert split.get_number_of_pages() == 1
            # Save + reload each split — the round-trip is what
            # exercised the original COSArray/COSDictionary indirect
            # walk regression. After reload the marker must survive.
            buf = io.BytesIO()
            split.save(buf)
            with PDDocument.load(buf.getvalue()) as reloaded:
                assert reloaded.get_number_of_pages() == 1
                resources = reloaded.get_page(0).get_cos_object().get_dictionary_object(
                    resources_key
                )
                assert resources is not None
                assert resources.get_name(marker) == "shared"
    finally:
        for split in splits:
            split.close()
        source.close()
