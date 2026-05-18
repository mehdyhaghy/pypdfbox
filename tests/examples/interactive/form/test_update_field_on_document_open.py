"""Smoke test for :class:`UpdateFieldOnDocumentOpen`."""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.update_field_on_document_open import (
    UpdateFieldOnDocumentOpen,
)


def test_attach_open_action_runs(tmp_path: Path) -> None:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    dst = tmp_path / "open.pdf"
    UpdateFieldOnDocumentOpen.attach_open_action(str(src), str(dst))
    assert dst.exists()
    assert dst.stat().st_size > 0


def test_constructor_is_callable() -> None:
    """Exercise the no-op ``__init__`` body (covers line 27)."""
    instance = UpdateFieldOnDocumentOpen()
    assert isinstance(instance, UpdateFieldOnDocumentOpen)


def test_main_with_explicit_argv(tmp_path: Path) -> None:
    """Drive ``main([src, dst])`` so the explicit-argv branch runs."""
    src = tmp_path / "form.pdf"
    dst = tmp_path / "open.pdf"
    CreateSimpleForm.create(str(src))
    UpdateFieldOnDocumentOpen.main([str(src), str(dst)])
    assert dst.exists()


def test_main_with_default_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty-argv branch — both DEFAULT_INPUT and DEFAULT_OUTPUT are
    taken; we redirect them to a temp dir so the test doesn't depend on
    the upstream resources path."""
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    CreateSimpleForm.create(str(src))
    monkeypatch.setattr(UpdateFieldOnDocumentOpen, "DEFAULT_INPUT", str(src))
    monkeypatch.setattr(UpdateFieldOnDocumentOpen, "DEFAULT_OUTPUT", str(dst))
    UpdateFieldOnDocumentOpen.main([])
    assert dst.exists()


def test_main_with_none_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main(None)`` must also fall back to DEFAULT_INPUT / DEFAULT_OUTPUT."""
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    CreateSimpleForm.create(str(src))
    monkeypatch.setattr(UpdateFieldOnDocumentOpen, "DEFAULT_INPUT", str(src))
    monkeypatch.setattr(UpdateFieldOnDocumentOpen, "DEFAULT_OUTPUT", str(dst))
    UpdateFieldOnDocumentOpen.main(None)
    assert dst.exists()


def test_attach_open_action_handles_missing_javascript_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force the ``except ImportError`` defensive fallback (lines 46-47)
    by poisoning the action module in ``sys.modules``. The example then
    skips wiring the open-action and just round-trips the document."""
    import sys

    src = tmp_path / "form.pdf"
    dst = tmp_path / "open.pdf"
    CreateSimpleForm.create(str(src))

    target = "pypdfbox.pdmodel.interactive.action.pd_action_java_script"
    # Make sure no cached module survives so the example's ``from`` import
    # re-resolves to the broken sentinel.
    monkeypatch.setitem(sys.modules, target, None)
    UpdateFieldOnDocumentOpen.attach_open_action(str(src), str(dst))
    assert dst.exists()


def test_attach_writes_javascript_open_action(tmp_path: Path) -> None:
    """After ``attach_open_action``, the output PDF's catalog must carry
    a ``/OpenAction`` dict whose ``/JS`` payload references ``SampleField``.
    Wave 1352 fixed the latent ``pd_action_javascript`` typo (the module
    is ``pd_action_java_script``) so this branch finally fires; the older
    test only asserted that the file was written."""
    from pypdfbox.pdmodel.pd_document import PDDocument

    src = tmp_path / "form.pdf"
    dst = tmp_path / "open.pdf"
    CreateSimpleForm.create(str(src))
    UpdateFieldOnDocumentOpen.attach_open_action(str(src), str(dst))
    with PDDocument.load(str(dst)) as doc:
        catalog = doc.get_document_catalog()
        open_action = catalog.get_open_action()
        assert open_action is not None
