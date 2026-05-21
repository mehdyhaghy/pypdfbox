"""
Ported from
pdfbox/src/test/java/org/apache/pdfbox/pdfparser/TestPDFParser.java
(Apache PDFBox 3.0.x).

The upstream suite drives ``Loader.loadPDF`` on a large set of corner-case
PDFs that live under a ``target/pdfs`` directory and are downloaded as part
of the upstream Maven build (PDFBOX-3208, PDFBOX-3783, PDFBOX-3947, etc.).
These fixtures aren't shipped with pypdfbox, so the corresponding tests are
explicitly skipped here; the small set whose fixtures live under
``pdfbox/src/test/resources`` (the package-local ``MissingCatalog.pdf``) is
ported in full.
"""

from __future__ import annotations

import pathlib

import pytest

from pypdfbox.loader import Loader

_FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "pdfparser"


def test_pdf_parser_missing_catalog() -> None:
    """PDFBOX-3060: parser should rebuild a trailer for a file with a
    missing ``/Catalog`` entry and load without raising.
    """
    doc = Loader.load_pdf(_FIXTURES / "MissingCatalog.pdf")
    try:
        # No exception is the upstream success criterion.
        assert doc is not None
    finally:
        doc.close()


# The remaining upstream tests (testPDFBox3208, testPDFBox3940, testPDFBox3783,
# testPDFBox3785, testPDFBox3947, testPDFBox3948, testPDFBox3949, testPDFBox3950,
# testPDFBox3951, testPDFBox3964, testPDFBox3977, testParseGenko, testPDFBox4338,
# testPDFBox4339, testPDFBox4153, testPDFBox4490, testPDFBox5025) all consume
# fixtures from upstream's ``target/pdfs`` directory that pypdfbox does not
# ship. They are intentionally skipped — porting them requires bundling those
# corpora, which is out of scope.
pytestmark_external_corpus = pytest.mark.skip(
    reason="upstream target/pdfs corpus not bundled with pypdfbox"
)


@pytestmark_external_corpus
def test_pdfbox_3208() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-3208 — /Info recovery during trailer rebuild."""


@pytestmark_external_corpus
def test_pdfbox_3940() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-3940 — /Info recovery for file without modification date."""


@pytestmark_external_corpus
def test_pdfbox_3783() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-3783 — parse file with trailing trash after %%EOF."""


@pytestmark_external_corpus
def test_pdfbox_3785() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-3785 / PDFBOX-3957 — truncated multi-revision file page count."""


@pytestmark_external_corpus
def test_pdfbox_3947() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-3947 — broken object stream."""


@pytestmark_external_corpus
def test_pdfbox_3948() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-3948 — object stream with unexpected newlines."""


@pytestmark_external_corpus
def test_pdfbox_3949() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-3949 — incomplete object stream."""


@pytestmark_external_corpus
def test_pdfbox_3950() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-3950 — truncated file with missing pages, rendering."""


@pytestmark_external_corpus
def test_pdfbox_3951() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-3951 — truncated file page count."""


@pytestmark_external_corpus
def test_pdfbox_3964() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-3964 — broken file page count."""


@pytestmark_external_corpus
def test_pdfbox_3977() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-3977 — /Info recovery via brute force."""


@pytestmark_external_corpus
def test_parse_genko() -> None:  # pragma: no cover - external corpus fixture
    """genko_oc_shiryo1.pdf regression."""


@pytestmark_external_corpus
def test_pdfbox_4338() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-4338 — ArrayIndexOutOfBoundsException regression."""


@pytestmark_external_corpus
def test_pdfbox_4339() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-4339 — NullPointerException regression."""


@pytestmark_external_corpus
def test_pdfbox_4153() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-4153 — outline parsing regression."""


@pytestmark_external_corpus
def test_pdfbox_4490() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-4490 — page count regression."""


@pytestmark_external_corpus
def test_pdfbox_5025() -> None:  # pragma: no cover - external corpus fixture
    """PDFBOX-5025 — ``74191endobj`` regression."""
