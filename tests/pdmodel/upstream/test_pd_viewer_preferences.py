"""Upstream-mirror module for ``PDViewerPreferences``.

Apache PDFBox 3.0 ships **no** dedicated JUnit class for
``PDViewerPreferences`` — verified against
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/`` (only
``action``, ``annotation``, ``documentnavigation``, ``form``,
``pagenavigation`` subdirectories exist — no ``viewerpreferences``).

Hand-written coverage lives in
``tests/pdmodel/test_pd_viewer_preferences.py``.
"""

from __future__ import annotations
