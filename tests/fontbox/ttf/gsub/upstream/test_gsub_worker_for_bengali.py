"""Port of upstream ``GsubWorkerForBengaliTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GsubWorkerForBengaliTest.java``.

Upstream's test loads ``src/test/resources/ttf/Lohit-Bengali.ttf`` and
asserts that :class:`GsubWorkerForBengali` produces specific glyph
substitutions for words written in Bengali script (e.g. "আমি",
"ব্যাস", "বেলা"...).

pypdfbox does not bundle ``Lohit-Bengali.ttf`` — wave 1360 agent C
flagged Lohit-Tamil.ttf as "SIL OFL 1.1 and not Apache-2.0
interchangeable for re-licensing" and chose a skip-placeholder
instead. We follow the same policy for the other Lohit fonts so the
bundled-fixture set stays self-consistent.

The Bengali shaper itself is covered by:

- ``tests/fontbox/ttf/gsub/test_gsub_worker_for_bengali.py`` (hand
  written, exercises the Python class surface directly)
- ``tests/fontbox/ttf/gsub/test_gsub_worker_for_bengali_wave1345.py``
  (regression for the Bengali-specific rendering corner cases)

This file exists as the parity placeholder so future re-syncs see the
upstream test mapped.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Lohit-Bengali.ttf is not bundled (SIL OFL 1.1, kept "
    "consistent with the wave 1360 Lohit-Tamil policy decision); "
    "GsubWorkerForBengali surface is covered by "
    "tests/fontbox/ttf/gsub/test_gsub_worker_for_bengali.py and "
    "tests/fontbox/ttf/gsub/test_gsub_worker_for_bengali_wave1345.py"
)


def test_apply_transforms_simple_hosshoi_kar() -> None:
    """Ported from ``GsubWorkerForBengaliTest#testApplyTransforms_simple_hosshoi_kar``."""


def test_apply_transforms_ja_phala() -> None:
    """Ported from ``GsubWorkerForBengaliTest#testApplyTransforms_ja_phala``."""


def test_apply_transforms_e_kar() -> None:
    """Ported from ``GsubWorkerForBengaliTest#testApplyTransforms_e_kar``."""


def test_apply_transforms_o_kar() -> None:
    """Ported from ``GsubWorkerForBengaliTest#testApplyTransforms_o_kar``."""


def test_apply_transforms_ou_kar() -> None:
    """Ported from ``GsubWorkerForBengaliTest#testApplyTransforms_ou_kar``."""


def test_apply_transforms_oi_kar() -> None:
    """Ported from ``GsubWorkerForBengaliTest#testApplyTransforms_oi_kar``."""


def test_apply_transforms_kha_e_murddhana_swa_e_khiwa() -> None:
    """Ported from
    ``GsubWorkerForBengaliTest#testApplyTransforms_kha_e_murddhana_swa_e_khiwa``."""


def test_apply_transforms_ra_phala() -> None:
    """Ported from ``GsubWorkerForBengaliTest#testApplyTransforms_ra_phala``."""


def test_apply_transforms_ref() -> None:
    """Ported from ``GsubWorkerForBengaliTest#testApplyTransforms_ref``."""


def test_apply_transforms_ra_e_hosshu() -> None:
    """Ported from ``GsubWorkerForBengaliTest#testApplyTransforms_ra_e_hosshu``."""


def test_apply_transforms_la_e_la_e() -> None:
    """Ported from ``GsubWorkerForBengaliTest#testApplyTransforms_la_e_la_e``."""


def test_apply_transforms_khanda_ta() -> None:
    """Ported from ``GsubWorkerForBengaliTest#testApplyTransforms_khanda_ta``."""
