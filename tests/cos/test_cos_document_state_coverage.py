"""Coverage-boost tests for :class:`pypdfbox.cos.cos_document_state.COSDocumentState`.

Exercise the lifecycle round-trip the primary test file doesn't touch
(set-parsing / is-accepting-updates state transitions).
"""
from __future__ import annotations

from pypdfbox.cos.cos_document_state import COSDocumentState


def test_initial_state_is_parsing() -> None:
    state = COSDocumentState()
    assert state.is_accepting_updates() is False


def test_set_parsing_false_flips_accepting_updates_true() -> None:
    state = COSDocumentState()
    state.set_parsing(False)
    assert state.is_accepting_updates() is True


def test_set_parsing_back_to_true_re_locks_updates() -> None:
    state = COSDocumentState()
    state.set_parsing(False)
    state.set_parsing(True)
    assert state.is_accepting_updates() is False


def test_two_instances_track_independent_state() -> None:
    a = COSDocumentState()
    b = COSDocumentState()
    a.set_parsing(False)
    b.set_parsing(False)
    assert a.is_accepting_updates() == b.is_accepting_updates() is True


def test_set_parsing_toggle_sequence() -> None:
    state = COSDocumentState()
    state.set_parsing(False)
    assert state.is_accepting_updates() is True
    state.set_parsing(True)
    assert state.is_accepting_updates() is False
