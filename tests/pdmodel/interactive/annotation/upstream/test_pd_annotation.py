"""Ported from pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/
annotation/PDAnnotationTest.java (PDFBox 3.0.x).

Upstream's PDAnnotationTest covers only PDAnnotationWidget construction
(both default and via PDTextField → getWidgets). Cluster #5 lite does
NOT port PDAnnotationWidget — Widget falls through to
PDAnnotationUnknown via the factory. Both upstream tests are skipped
with the reason recorded here so a future port can re-enable them."""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="PDAnnotationWidget not ported in cluster #5 lite — Widget "
    "falls through to PDAnnotationUnknown."
)
def test_create_default_widget_annotation() -> None:  # pragma: no cover
    pass


@pytest.mark.skip(
    reason="Depends on PDAcroForm + PDTextField + PDAnnotationWidget — "
    "all deferred past cluster #5 lite."
)
def test_create_widget_annotation_from_field() -> None:  # pragma: no cover
    pass
