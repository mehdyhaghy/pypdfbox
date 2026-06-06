"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestFDF.java

Upstream baseline: PDFBox 3.0.7.

``testLoad2`` loads two simple FDF files with two fields each; one of them
(``nocatalog.fdf``) has no ``/Type/Catalog`` entry, which isn't required
(PDFBOX-3639). Upstream runs both files in a single method; here they are
split into two methods. Both ship as live ports: the brute-force trailer
rebuild treats an ``/FDF``-bearing dictionary as a catalog
(``BruteForceParser.isCatalog``), so the xref-less trailer's
``/Root 1 0 R`` resolves even when the root object lacks ``/Type/Catalog``.

``testPDFBox5894`` is skipped — it reads ``target/pdfs/PDFBOX-5894.fdf``,
a build-time JIRA download the repo does not bundle.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox import Loader, PDDocument

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "pdfbox" / "pdfparser"
_SIMPLE_FORM = "SimpleForm2Fields.pdf"


def _check_fields(name: str) -> None:
    """Mirror upstream private ``checkFields``."""
    fdf = Loader.load_fdf(_FIXTURE_DIR / name)
    try:
        # Upstream writes to a PrintWriter over a ByteArrayOutputStream
        # purely to exercise the XFDF serialiser; the bytes are discarded.
        fdf.save_xfdf(io.StringIO())

        fields = fdf.get_catalog().get_fdf().get_fields()

        assert len(fields) == 2
        assert fields[0].get_partial_field_name() == "Field1"
        assert fields[1].get_partial_field_name() == "Field2"
        assert fields[0].get_value() == "Test1"
        assert fields[1].get_value() == "Test2"

        pdf = PDDocument.load(_FIXTURE_DIR / _SIMPLE_FORM)
        try:
            acro_form = pdf.get_document_catalog().get_acro_form()
            acro_form.import_fdf(fdf)
            assert acro_form.get_field("Field1").get_value_as_string() == "Test1"
            assert acro_form.get_field("Field2").get_value_as_string() == "Test2"
        finally:
            pdf.close()
    finally:
        fdf.close()


def test_load2_with_catalog() -> None:
    """Upstream ``testLoad2`` — FDF that carries a ``/Type/Catalog``."""
    _check_fields("withcatalog.fdf")


def test_load2_no_catalog() -> None:
    """Upstream ``testLoad2`` — FDF with no ``/Type/Catalog`` entry.

    The FDF root dictionary omits ``/Type /Catalog`` but carries ``/FDF``;
    the brute-force trailer rebuild treats an ``/FDF``-bearing dictionary as
    a catalog (PDFBOX-3639), so the xref-less trailer's ``/Root 1 0 R``
    resolves against the rebuilt object map.
    """
    _check_fields("nocatalog.fdf")
