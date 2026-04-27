"""
Upstream parity tests for ``PDMetadata``.

Apache PDFBox 3.0.x does not ship a dedicated
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/PDMetadataTest.java``
class — ``PDMetadata`` is exercised indirectly via
``TestPDDocumentCatalog.testGetMetadata()`` and the XMP round-trip tests
in ``xmpbox/src/test/``. Rather than duplicate those (which belong in
their own clusters), this file mirrors the upstream layout so future
re-syncs are diffable but contains no ported cases.

See ``tests/pdmodel/common/test_pd_metadata.py`` for the hand-written
behavioural coverage of ``PDMetadata``'s constructors,
``import_xmp_metadata`` / ``export_xmp_metadata``, ``create_input_stream``
and the inherited ``set_filters`` / ``get_cos_object`` surface.
"""

from __future__ import annotations
