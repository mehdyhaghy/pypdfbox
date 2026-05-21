"""Port of upstream ``GsubWorkerForLatinTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GsubWorkerForLatinTest.java``.

Upstream's test has two cases:

1. ``testApplyLigaturesCalibri`` — loads
   ``c:/windows/fonts/calibri.ttf`` (Microsoft Windows-only,
   proprietary; upstream guards with
   ``Assumptions.assumeTrue(file.exists(), ...)``). pypdfbox cannot
   bundle Calibri; upstream itself only runs this case on Windows
   developer machines so a parity-aware skip is appropriate.
2. ``testApplyLigaturesFoglihtenNo07`` — loads
   ``src/test/resources/otf/FoglihtenNo07.otf``. The Foglihten font
   ships with a custom non-Apache license (declined for bundling per
   the wave 1360 Lohit-Tamil policy decision noted on
   ``tests/fontbox/ttf/gsub/upstream/test_gsub_worker_for_aalt.py``).

The Latin shaper surface is covered by:

- ``tests/fontbox/ttf/gsub/test_gsub_worker_for_latin.py`` (hand
  written, exercises ``GsubWorkerForLatin`` directly)
- The Liberation Sans round-trip in
  ``tests/fontbox/ttf/upstream/test_glyph_substitution_table_liberation_font.py``

This file exists as the parity placeholder so future re-syncs see the
upstream test mapped.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Calibri is Windows-proprietary (upstream itself only "
    "runs this case via assumeTrue on dev machines) and "
    "FoglihtenNo07.otf is not bundled (custom non-Apache license); "
    "GsubWorkerForLatin is covered by "
    "tests/fontbox/ttf/gsub/test_gsub_worker_for_latin.py and "
    "tests/fontbox/ttf/upstream/test_glyph_substitution_table_liberation_font.py"
)


def test_apply_ligatures_calibri() -> None:
    """Ported from ``GsubWorkerForLatinTest#testApplyLigaturesCalibri``."""


def test_apply_ligatures_foglihten_no07() -> None:
    """Ported from ``GsubWorkerForLatinTest#testApplyLigaturesFoglihtenNo07``."""
