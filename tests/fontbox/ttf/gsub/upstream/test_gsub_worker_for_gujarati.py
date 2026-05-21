"""Port of upstream ``GsubWorkerForGujaratiTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GsubWorkerForGujaratiTest.java``.

Upstream's test loads ``src/test/resources/ttf/Lohit-Gujarati.ttf``
and asserts that :class:`GsubWorkerForGujarati` produces specific
glyph substitutions for Gujarati words covering akhn/rphf/rkrf/blwf
/half/vatu/cjct/pres/abvs/blws features.

pypdfbox does not bundle ``Lohit-Gujarati.ttf`` (SIL OFL 1.1, kept
consistent with the wave 1360 Lohit-Tamil policy decision so the
fixture set stays self-consistent).

The Gujarati shaper itself is covered by:

- ``tests/fontbox/ttf/gsub/test_gsub_worker_for_gujarati.py``
- ``tests/fontbox/ttf/gsub/test_gsub_worker_for_gujarati_coverage.py``

This file exists as the parity placeholder so future re-syncs see the
upstream test mapped.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Lohit-Gujarati.ttf is not bundled (SIL OFL 1.1, kept "
    "consistent with the wave 1360 Lohit-Tamil policy decision); "
    "GsubWorkerForGujarati is covered by "
    "tests/fontbox/ttf/gsub/test_gsub_worker_for_gujarati.py and "
    "tests/fontbox/ttf/gsub/test_gsub_worker_for_gujarati_coverage.py"
)


def test_apply_transforms_akhn() -> None:
    """Ported from ``GsubWorkerForGujaratiTest#testApplyTransforms_akhn``."""


def test_apply_transforms_rphf() -> None:
    """Ported from ``GsubWorkerForGujaratiTest#testApplyTransforms_rphf``."""


def test_apply_transforms_rkrf() -> None:
    """Ported from ``GsubWorkerForGujaratiTest#testApplyTransforms_rkrf``."""


def test_apply_transforms_blwf() -> None:
    """Ported from ``GsubWorkerForGujaratiTest#testApplyTransforms_blwf``."""


def test_apply_transforms_half() -> None:
    """Ported from ``GsubWorkerForGujaratiTest#testApplyTransforms_half``."""


def test_apply_transforms_vatu() -> None:
    """Ported from ``GsubWorkerForGujaratiTest#testApplyTransforms_vatu``."""


def test_apply_transforms_cjct() -> None:
    """Ported from ``GsubWorkerForGujaratiTest#testApplyTransforms_cjct``."""


def test_apply_transforms_pres() -> None:
    """Ported from ``GsubWorkerForGujaratiTest#testApplyTransforms_pres``."""


def test_apply_transforms_abvs() -> None:
    """Ported from ``GsubWorkerForGujaratiTest#testApplyTransforms_abvs``."""


def test_apply_transforms_blws() -> None:
    """Ported from ``GsubWorkerForGujaratiTest#testApplyTransforms_blws``."""
