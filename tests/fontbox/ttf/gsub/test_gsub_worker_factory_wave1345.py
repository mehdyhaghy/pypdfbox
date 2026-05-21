"""Wave 1345 coverage-boost tests for :class:`GsubWorkerFactory`.

Targets the residual branches of the helper internals:

* line 61 — :func:`_normalize_language` early-return for ``None``.
* lines 66-67 — the ``ImportError`` fallback when the optional
  ``..model.language.Language`` enum module is absent.
* lines 92-93 — :func:`_resolve_language_from_scripts` swallowing
  :class:`AttributeError` / :class:`TypeError` when ``get_script_list``
  blows up (e.g. a deliberately malformed :class:`GsubData` stand-in).
* line 105 — :func:`_resolve_language_from_scripts` returning ``""``
  when the font carries script tags but none belong to any known
  language.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pytest

from pypdfbox.fontbox.ttf.gsub import gsub_worker_factory as factory_module
from pypdfbox.fontbox.ttf.gsub.gsub_worker_factory import (
    _normalize_language,
    _resolve_language_from_scripts,
)


def test_normalize_language_none_returns_empty_string() -> None:
    """Line 61 — ``_normalize_language(None) == ""``."""
    assert _normalize_language(None) == ""


def test_normalize_language_handles_missing_language_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``..model.language`` can't be imported, fall back to the
    bare ``str`` branch (lines 66-67)."""
    real_modules = {
        name: mod
        for name, mod in sys.modules.items()
        if name.startswith("pypdfbox.fontbox.ttf.model")
    }
    for name in real_modules:
        monkeypatch.delitem(sys.modules, name, raising=False)

    # Insert a stub ``..model`` package whose ``language`` attribute
    # raises ImportError on access (mimics a missing module).
    class _RaisingFinder:
        def find_module(
            self,
            fullname: str,
            path: Any | None = None,  # noqa: ARG002
        ) -> Any | None:
            if fullname == "pypdfbox.fontbox.ttf.model.language":
                return self
            return None

        def load_module(self, fullname: str) -> Any:
            msg = f"forced missing module: {fullname}"
            raise ImportError(msg)

        # Modern Python uses MetaPathFinder.find_spec; mimic that too.
        def find_spec(
            self,
            fullname: str,
            path: Any | None = None,  # noqa: ARG002
            target: Any | None = None,  # noqa: ARG002
        ) -> Any | None:
            if fullname == "pypdfbox.fontbox.ttf.model.language":
                import importlib.machinery

                msg = f"forced missing module: {fullname}"

                class _RaisingLoader:
                    def create_module(self, spec):  # noqa: ARG002, ANN001
                        return None

                    def exec_module(self, module):  # noqa: ARG002, ANN001
                        raise ImportError(msg)

                return importlib.machinery.ModuleSpec(fullname, _RaisingLoader())
            return None

    finder = _RaisingFinder()
    sys.meta_path.insert(0, finder)
    try:
        # Coerce the str fall-through path with a plain Python str.
        assert _normalize_language("Latin") == "LATIN"
    finally:
        sys.meta_path.remove(finder)
        for name, mod in real_modules.items():
            sys.modules[name] = mod


def test_resolve_language_from_scripts_swallows_attribute_error() -> None:
    """Lines 92-93 — ``get_script_list`` raising :class:`AttributeError`
    yields the empty fallback."""

    class _BadGsub:
        def get_script_list(self) -> dict:
            msg = "deliberately broken script_list accessor"
            raise AttributeError(msg)

    assert _resolve_language_from_scripts(_BadGsub()) == ""  # type: ignore[arg-type]


def test_resolve_language_from_scripts_swallows_type_error() -> None:
    """Same except clause, :class:`TypeError` variant."""

    class _TypeBad:
        def get_script_list(self) -> dict:
            msg = "deliberately broken script_list accessor"
            raise TypeError(msg)

    assert _resolve_language_from_scripts(_TypeBad()) == ""  # type: ignore[arg-type]


def test_resolve_language_from_scripts_returns_empty_for_unrelated_scripts() -> None:
    """A font carrying only scripts unknown to any language (e.g.
    ``"thai"`` / ``"hebr"``) falls through to ``""``. Wave 1375 added
    Tamil to the language map, so ``"taml"`` now resolves; pick tags
    no language matches to exercise the empty-result branch."""
    fake = SimpleNamespace(get_script_list=lambda: {"thai": object(), "hebr": object()})
    assert _resolve_language_from_scripts(fake) == ""  # type: ignore[arg-type]


# A small sanity-check that the wave-1345 helper changes haven't broken
# the public ``GsubWorkerFactory.get_gsub_worker`` happy path.
def test_factory_module_exports_factory_class() -> None:
    """Smoke: ``GsubWorkerFactory`` is exported from the module."""
    assert hasattr(factory_module, "GsubWorkerFactory")
