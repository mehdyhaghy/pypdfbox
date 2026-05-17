"""Coverage-boost tests for :class:`pypdfbox.cos.cos_document_state.COSDocumentState`.

Exercise the two Java-name aliases (``setParsing`` / ``isAcceptingUpdates``)
that the primary test file doesn't touch.
"""
from __future__ import annotations

from pypdfbox.cos.cos_document_state import COSDocumentState


def test_initial_state_is_parsing() -> None:
    state = COSDocumentState()
    assert state.is_accepting_updates() is False
    assert state.isAcceptingUpdates() is False


def test_set_parsing_false_flips_accepting_updates_true() -> None:
    state = COSDocumentState()
    state.set_parsing(False)
    assert state.is_accepting_updates() is True


def test_set_parsing_back_to_true_re_locks_updates() -> None:
    state = COSDocumentState()
    state.set_parsing(False)
    state.set_parsing(True)
    assert state.is_accepting_updates() is False


def test_java_alias_set_parsing_matches_snake_case() -> None:
    a = COSDocumentState()
    b = COSDocumentState()
    a.set_parsing(False)
    b.setParsing(False)
    assert a.is_accepting_updates() == b.is_accepting_updates()
    assert a.isAcceptingUpdates() == b.isAcceptingUpdates()


def test_java_alias_is_accepting_updates_matches_snake_case() -> None:
    state = COSDocumentState()
    state.setParsing(False)
    assert state.isAcceptingUpdates() is True
    assert state.is_accepting_updates() is True
    state.setParsing(True)
    assert state.isAcceptingUpdates() is False
    assert state.is_accepting_updates() is False
