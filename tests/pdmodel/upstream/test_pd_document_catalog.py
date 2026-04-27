"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDDocumentCatalog.java

Upstream baseline: PDFBox 3.0.
"""

from __future__ import annotations

import pytest

from pypdfbox import PDDocument
from pypdfbox.cos import COSBoolean, COSName


# ``retrievePageLabels`` and ``retrievePageLabelsOnMalformedPdf`` — need
# the upstream test_pagelabels.pdf / badpagelabels.pdf fixtures. PDPageLabels
# itself shipped in pdmodel cluster #2; same label generator is exercised
# synthetically in ``tests/pdmodel/test_pd_page_labels.py``.
@pytest.mark.skip(
    reason="needs test_pagelabels.pdf fixture; covered by test_pd_page_labels.py"
)
def test_retrieve_page_labels() -> None:  # pragma: no cover
    pass


@pytest.mark.skip(
    reason="needs badpagelabels.pdf fixture; tolerant traversal covered synthetically"
)
def test_retrieve_page_labels_on_malformed_pdf() -> None:  # pragma: no cover
    pass


# ``retrieveNumberOfPages`` — needs the ``test.unc.pdf`` fixture. The
# mechanic (loaded doc → number_of_pages) is exercised by our hand-written
# ``test_pd_document.py``; skip rather than gather a redistributable PDF.
@pytest.mark.skip(reason="needs test.unc.pdf fixture; round-trip exercised in hand-written tests")
def test_retrieve_number_of_pages() -> None:  # pragma: no cover
    pass


# ``handleOutputIntents`` — needs PDOutputIntent (pdmodel cluster #2 /
# graphics color cluster) + ICC profile fixture.
@pytest.mark.skip(reason="needs PDOutputIntent — pdmodel cluster #2 + ICC fixture")
def test_handle_output_intents() -> None:  # pragma: no cover
    pass


def test_handle_boolean_in_open_action() -> None:
    """``handleBooleanInOpenAction`` — malformed boolean must not crash."""
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        catalog.get_cos_object().set_item(
            COSName.get_pdf_name("OpenAction"),
            COSBoolean.TRUE,
        )
        assert catalog.get_open_action() is None


def test_null_threads() -> None:
    """``testNullThreads`` — get_threads on a fresh document with no
    ``/Threads`` entry must return an empty list, not crash. Mirrors
    upstream's null-tolerant assertion (upstream returns ``null`` /
    we return an empty ``list`` per Python idiom — both are ``not
    truthy``)."""
    with PDDocument() as doc:
        threads = doc.get_document_catalog().get_threads()
        assert threads == []


# Even though every upstream test in this file targets later clusters,
# we keep at least one round-tripper for the methods cluster #1 *does*
# ship — language / page_layout / page_mode — so the upstream-suite has
# a passing case.
def test_catalog_string_round_trip_smoke() -> None:
    """Smoke parity test: language / layout / mode round-trip (covered by
    upstream's catalog accessors that lack standalone JUnit cases)."""
    with PDDocument() as doc:
        cat = doc.get_document_catalog()
        cat.set_language("en-US")
        cat.set_page_layout("OneColumn")
        cat.set_page_mode("UseOutlines")
        assert cat.get_language() == "en-US"
        assert cat.get_page_layout() == "OneColumn"
        assert cat.get_page_mode() == "UseOutlines"
