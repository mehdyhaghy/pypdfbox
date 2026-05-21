"""Port of upstream ``GsubWorkerForDevanagariTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GsubWorkerForDevanagariTest.java``.

Upstream's test loads ``src/test/resources/ttf/Lohit-Devanagari.ttf``
and asserts that :class:`GsubWorkerForDevanagari` produces specific
glyph substitutions for Devanagari words covering locl/nukt/akhn/rphf
/blwf/half/vatu/pres/blws/haln features.

pypdfbox does not bundle ``Lohit-Devanagari.ttf`` (SIL OFL 1.1, kept
consistent with the wave 1360 Lohit-Tamil policy decision —
agent C declined to bundle Lohit fonts so the fixture set stays
self-consistent).

The Devanagari shaper itself is covered by:

- ``tests/fontbox/ttf/gsub/test_gsub_worker_for_devanagari.py``
- ``tests/fontbox/ttf/gsub/test_gsub_worker_for_devanagari_coverage.py``

This file exists as the parity placeholder so future re-syncs see the
upstream test mapped.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Lohit-Devanagari.ttf is not bundled (SIL OFL 1.1, kept "
    "consistent with the wave 1360 Lohit-Tamil policy decision); "
    "GsubWorkerForDevanagari is covered by "
    "tests/fontbox/ttf/gsub/test_gsub_worker_for_devanagari.py and "
    "tests/fontbox/ttf/gsub/test_gsub_worker_for_devanagari_coverage.py"
)


def test_apply_transforms_locl() -> None:
    """Ported from ``GsubWorkerForDevanagariTest#testApplyTransforms_locl``."""


def test_apply_transforms_nukt() -> None:
    """Ported from ``GsubWorkerForDevanagariTest#testApplyTransforms_nukt``."""


def test_apply_transforms_akhn() -> None:
    """Ported from ``GsubWorkerForDevanagariTest#testApplyTransforms_akhn``."""


def test_apply_transforms_rphf() -> None:
    """Ported from ``GsubWorkerForDevanagariTest#testApplyTransforms_rphf``."""


def test_apply_transforms_blwf() -> None:
    """Ported from ``GsubWorkerForDevanagariTest#testApplyTransforms_blwf``."""


def test_apply_transforms_half() -> None:
    """Ported from ``GsubWorkerForDevanagariTest#testApplyTransforms_half``."""


def test_apply_transforms_vatu() -> None:
    """Ported from ``GsubWorkerForDevanagariTest#testApplyTransforms_vatu``."""


def test_apply_transforms_pres() -> None:
    """Ported from ``GsubWorkerForDevanagariTest#testApplyTransforms_pres``."""


def test_apply_transforms_blws() -> None:
    """Ported from ``GsubWorkerForDevanagariTest#testApplyTransforms_blws``."""


def test_apply_transforms_haln() -> None:
    """Ported from ``GsubWorkerForDevanagariTest#testApplyTransforms_haln``."""
