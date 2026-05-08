"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDDocumentInformation.java

Upstream baseline: PDFBox 3.0.
"""

from __future__ import annotations

import pytest


# ``testMetadataExtraction`` — needs ``input/hello3.pdf`` fixture from
# upstream's resources. The /Info round-trip itself is exercised by our
# hand-written tests; skip rather than redistribute the PDF until the
# corpus tooling lands.
@pytest.mark.skip(
    reason="needs input/hello3.pdf fixture; field round-trip exercised in hand-written tests"
)
def test_metadata_extraction() -> None:  # pragma: no cover
    pass


# ``testPDFBox3068`` — indirect /Title needs the PDFBOX-3068.pdf fixture.
@pytest.mark.skip(
    reason=(
        "needs PDFBOX-3068.pdf fixture; indirect-object resolution exercised by "
        "COSDictionary tests"
    )
)
def test_pdfbox_3068() -> None:  # pragma: no cover
    pass
