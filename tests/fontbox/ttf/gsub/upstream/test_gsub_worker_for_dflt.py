"""Port of upstream ``GsubWorkerForDfltTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/gsub/GsubWorkerForDfltTest.java``.

Upstream's test loads ``src/test/resources/ttf/JosefinSans-Italic.ttf``
and asserts that :class:`GsubWorkerForDflt` produces specific glyph
substitutions for DFLT-script ligatures (fi/fl/ffi/ffl). It also
asserts the worker's result is an unmodifiable list.

pypdfbox does not bundle ``JosefinSans-Italic.ttf`` (SIL OFL 1.1, kept
consistent with the wave 1360 Lohit fonts policy decision so the
fixture set stays self-consistent).

The DFLT shaper surface is covered by:

- ``tests/fontbox/ttf/gsub/test_gsub_worker_for_dflt.py`` (hand
  written, exercises ``GsubWorkerForDflt`` directly)
- ``tests/fontbox/ttf/gsub/test_gsub_worker_factory.py`` (asserts the
  factory falls through to DFLT when no script-specific shaper is
  registered)

This file exists as the parity placeholder so future re-syncs see the
upstream test mapped. Note also that pypdfbox's
:class:`DefaultGsubWorker` returns a mutable defensive copy (documented
divergence) so the upstream ``testApplyTransforms_immutableResult``
case would assert pypdfbox-incompatible behaviour — see
``tests/fontbox/ttf/gsub/upstream/test_default_gsub_worker.py``.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="JosefinSans-Italic.ttf is not bundled (SIL OFL 1.1, kept "
    "consistent with the wave 1360 Lohit policy decision); "
    "GsubWorkerForDflt is covered by "
    "tests/fontbox/ttf/gsub/test_gsub_worker_for_dflt.py and "
    "tests/fontbox/ttf/gsub/test_gsub_worker_factory.py"
)


def test_correct_worker_type() -> None:
    """Ported from ``GsubWorkerForDfltTest#testCorrectWorkerType``."""


def test_apply_transforms_no_ligature() -> None:
    """Ported from ``GsubWorkerForDfltTest#testApplyTransforms`` (code case)."""


def test_apply_transforms_simple_ligature() -> None:
    """Ported from ``GsubWorkerForDfltTest#testApplyTransforms`` (fi case)."""


def test_apply_transforms_ligature_within_word() -> None:
    """Ported from ``GsubWorkerForDfltTest#testApplyTransforms`` (office case)."""


def test_apply_transforms_multi_f_sequence() -> None:
    """Ported from ``GsubWorkerForDfltTest#testApplyTransforms`` (ffl case)."""


def test_apply_transforms_immutable_result() -> None:
    """Ported from ``GsubWorkerForDfltTest#testApplyTransforms_immutableResult``.

    pypdfbox divergence: result is a mutable defensive copy rather than
    an unmodifiable wrapper (see DefaultGsubWorker documented
    divergence). Behaviour is asserted in
    ``tests/fontbox/ttf/gsub/upstream/test_default_gsub_worker.py``.
    """
