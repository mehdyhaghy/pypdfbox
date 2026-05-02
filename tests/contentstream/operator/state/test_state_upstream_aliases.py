"""Upstream layout-parity for ``state`` operators that pypdfbox keeps
under sibling subpackages.

Upstream PDFBox places ``Concatenate`` (the ``cm`` operator) and
``SetMatrix`` (the ``Tm`` operator) in
``org.apache.pdfbox.contentstream.operator.state``. pypdfbox keeps the
implementations under ``graphics`` and ``text`` respectively for
historical reasons but re-exports both from the upstream-faithful path
so callers can write::

    from pypdfbox.contentstream.operator.state import Concatenate, SetMatrix

This file pins the re-export contract.
"""

from __future__ import annotations

from pypdfbox.contentstream.operator.graphics.concatenate_matrix import (
    ConcatenateMatrix,
)
from pypdfbox.contentstream.operator.state import (
    Concatenate,
    ConcatenateMatrix as StateConcatenateMatrix,
    SetMatrix,
)
from pypdfbox.contentstream.operator.text.set_matrix import (
    SetMatrix as TextSetMatrix,
)


def test_concatenate_alias_points_to_concatenate_matrix() -> None:
    """``state.Concatenate`` is the upstream-faithful name for the same
    handler we ship under ``graphics`` as ``ConcatenateMatrix``."""
    assert Concatenate is ConcatenateMatrix


def test_state_concatenate_matrix_alias_matches_graphics() -> None:
    """The legacy ``ConcatenateMatrix`` re-export under ``state`` resolves
    to the same class as the canonical ``graphics`` location."""
    assert StateConcatenateMatrix is ConcatenateMatrix


def test_set_matrix_alias_points_to_text_set_matrix() -> None:
    """``state.SetMatrix`` is the upstream-faithful name for the
    handler that pypdfbox keeps under ``text`` (the ``Tm`` operator)."""
    assert SetMatrix is TextSetMatrix


def test_concatenate_advertises_cm_operator_name() -> None:
    assert Concatenate().get_name() == "cm"


def test_set_matrix_advertises_tm_operator_name() -> None:
    assert SetMatrix().get_name() == "Tm"


def test_state_module_exports_upstream_state_operators() -> None:
    """The upstream ``operator.state`` package surfaces ``Concatenate``
    and ``SetMatrix``; the pypdfbox state module must too."""
    from pypdfbox.contentstream.operator import state

    assert "Concatenate" in state.__all__
    assert "SetMatrix" in state.__all__
