"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDPageTree.java

Upstream baseline: PDFBox 3.0.
"""

from __future__ import annotations

import pytest

from pypdfbox import PDDocument, PDPage


# ``indexOfPageFromOutlineDestination`` — needs PDDocumentOutline /
# PDOutlineItem / destination resolution. Land with pdmodel cluster #7
# (outlines + destinations + actions). Also requires ``with_outline.pdf``
# fixture.
@pytest.mark.skip(reason="needs PDDocumentOutline + destinations — pdmodel cluster #7")
def test_index_of_page_from_outline_destination() -> None:  # pragma: no cover
    pass


# ``positiveSingleLevel`` and ``positiveMultipleLevel`` rely on a fixture
# PDF and on ``PDPageTree.indexOf`` (which we haven't wired into the public
# API yet — upstream uses it externally). The mechanic is exercised by our
# hand-written ``test_pd_page_tree.py``; we'd duplicate it without the
# fixtures, so skip rather than synthesise.
@pytest.mark.skip(reason="needs with_outline.pdf fixture + PDPageTree.indexOf")
def test_positive_single_level() -> None:  # pragma: no cover
    pass


@pytest.mark.skip(reason="needs page_tree_multiple_levels.pdf fixture + PDPageTree.indexOf")
def test_positive_multiple_level() -> None:  # pragma: no cover
    pass


@pytest.mark.skip(reason="needs with_outline.pdf fixture + PDPageTree.indexOf")
def test_negative() -> None:  # pragma: no cover
    pass


def test_insert_before_blank_page() -> None:
    """``testInsertBeforeBlankPage``."""
    with PDDocument() as document:
        page_one = PDPage()
        page_two = PDPage()
        page_three = PDPage()

        document.add_page(page_one)
        document.add_page(page_two)
        document.get_pages().insert_before(page_three, page_two)

        # We use list iteration as our ``indexOf``-equivalent — there's
        # no public ``index_of`` on PDPageTree in cluster #1.
        order = list(document.get_pages())
        assert order[0] is page_one or order[0].get_cos_object() is page_one.get_cos_object()
        assert order[1].get_cos_object() is page_three.get_cos_object()
        assert order[2].get_cos_object() is page_two.get_cos_object()


def test_insert_after_blank_page() -> None:
    """``testInsertAfterBlankPage``."""
    with PDDocument() as document:
        page_one = PDPage()
        page_two = PDPage()
        page_three = PDPage()

        document.add_page(page_one)
        document.add_page(page_two)
        document.get_pages().insert_after(page_three, page_two)

        order = list(document.get_pages())
        assert order[0].get_cos_object() is page_one.get_cos_object()
        assert order[1].get_cos_object() is page_two.get_cos_object()
        assert order[2].get_cos_object() is page_three.get_cos_object()


# ``testNodeLoop`` — needs the PDFBOX-6040-nodeloop.pdf fixture. Our
# hand-written ``test_inheritable_attribute_breaks_cycles`` covers the
# same loop-protection invariant synthetically.
@pytest.mark.skip(reason="needs PDFBOX-6040-nodeloop.pdf fixture; cycle protection covered synthetically")
def test_node_loop() -> None:  # pragma: no cover
    pass
