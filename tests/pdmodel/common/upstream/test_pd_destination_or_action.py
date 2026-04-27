"""
Upstream parity tests for ``PDDestinationOrAction``.

Apache PDFBox 3.0 ships ``PDDestinationOrAction`` as a pure marker
interface (``public interface PDDestinationOrAction extends COSObjectable
{}``), with no test class in
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/``. The dispatch
behaviour we synthesise into ``PDDestinationOrAction.create(...)`` is
exercised in upstream code via ``PDDocumentCatalog.getOpenAction()`` and
``PDDestination.create(...)``; the parity tests for those live alongside
their respective Java test classes (e.g. ``PDDestinationTest``,
``TestPDDocumentCatalog``).

This file therefore mirrors the upstream layout (so re-syncs are
diffable) but contains no ported cases — see
``tests/pdmodel/common/test_pd_destination_or_action.py`` for the
hand-written behavioural coverage.
"""

from __future__ import annotations
