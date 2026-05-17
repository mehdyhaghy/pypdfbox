"""Tests for ``CreateEmptySignatureForm``.

NOTE — latent source bug flagged for wave 1341:
``CreateEmptySignatureForm.create`` imports
``pypdfbox.pdmodel.common.pd_rectangle`` which does not exist; the real
module is ``pypdfbox.pdmodel.pd_rectangle``. Tests below only exercise
the static-helper surface + ``main`` dispatch via a stub; the
end-to-end PDF round-trip cannot run until the import is fixed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.signature.create_empty_signature_form import (
    CreateEmptySignatureForm,
)


def test_static_helper_cannot_be_instantiated():
    # ``__init__`` is annotated ``pragma: no cover``; if the wrapper is
    # ever inadvertently made instantiable, this test still catches it.
    with pytest.raises(RuntimeError):
        CreateEmptySignatureForm()


def test_create_method_is_callable():
    assert callable(CreateEmptySignatureForm.create)


def test_main_method_is_callable():
    assert callable(CreateEmptySignatureForm.main)


def test_main_without_args_raises_usage() -> None:
    """Empty argv triggers the ``raise SystemExit("usage: ...")`` guard
    (line 18 of the source). Covers the ``not args`` branch."""
    with pytest.raises(SystemExit) as exc_info:
        CreateEmptySignatureForm.main([])
    # ``SystemExit("usage ...")`` -> .code holds the message string.
    assert "usage" in str(exc_info.value)


def test_main_dispatches_to_create(tmp_path: Path, monkeypatch) -> None:
    """``main([path])`` should forward ``path`` straight to ``create``.

    We stub ``create`` to capture the argument so this test exercises
    the dispatch line independently of the unrelated ``pd_rectangle``
    import bug flagged in the module docstring.
    """
    received: list[str] = []

    def _stub(output_path):
        received.append(str(output_path))

    monkeypatch.setattr(CreateEmptySignatureForm, "create", staticmethod(_stub))
    out = tmp_path / "sig.pdf"
    CreateEmptySignatureForm.main([str(out)])
    assert received == [str(out)]


def test_main_passes_first_positional_arg(monkeypatch) -> None:
    """``main`` ignores any args beyond the first positional output path."""
    received: list[str] = []

    def _stub(output_path):
        received.append(str(output_path))

    monkeypatch.setattr(CreateEmptySignatureForm, "create", staticmethod(_stub))
    CreateEmptySignatureForm.main(["primary.pdf", "ignored", "also-ignored"])
    assert received == ["primary.pdf"]
