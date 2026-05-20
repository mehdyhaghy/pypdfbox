"""Port of upstream ``GsubWorkerForAaltTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GsubWorkerForAaltTest.java``.

Skipped: pypdfbox does not port the upstream ``GsubWorkerForAalt``
worker (the "aalt" Type 3 alternate-substitution shaper) and does not
bundle ``FoglihtenNo07.otf``. The factory falls back to
:class:`DefaultGsubWorker` for fonts whose script tag doesn't match any
of the explicit Latin / Bengali / Devanagari / Gujarati / DFLT workers;
"aalt" alternate selection is intentionally out of scope for the same
reasons as upstream (the single-glyph-in / single-glyph-out signature
can't express ``applyTransforms`` for a multi-alternate feature without
caller-supplied alternate-index resolution).

The fixture ``FoglihtenNo07.otf`` carries a custom non-Apache license
and is not redistributed by pypdfbox.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="GsubWorkerForAalt is not ported (alternate-glyph feature "
    "out of scope) and FoglihtenNo07.otf is not bundled."
)
def test_foglihten_no07() -> None:
    """Ported from ``GsubWorkerForAaltTest#testFoglihtenNo07()``.

    Original asserts the worker maps the GIDs for ``"Abc"`` to
    ``[1139, 1562, 1477]`` via GSUB lookup lists 12/13.
    """
