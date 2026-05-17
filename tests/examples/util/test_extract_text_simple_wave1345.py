"""Wave 1345 — coverage round-out for :class:`ExtractTextSimple`.

Targets the remaining uncovered lines: ``__init__``, the
``main`` happy-path that delegates to :meth:`ExtractTextSimple.extract`,
and the ``(AttributeError, NotImplementedError)`` guard that swallows
encryption introspection errors.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pypdfbox.examples.util import extract_text_simple
from pypdfbox.examples.util.extract_text_simple import ExtractTextSimple


def test_constructor_is_inert() -> None:
    """The trivial ``__init__`` body (just ``pass``) is covered."""
    assert ExtractTextSimple() is not None


def test_main_with_one_arg_delegates_to_extract(
    make_pdf: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``main`` returns the text when given exactly one argument."""
    src = make_pdf("main-delegate.pdf", page_count=1)
    text = ExtractTextSimple.main([str(src)])
    assert "page 1:" in text
    # ``extract`` also writes to stdout — surface should agree.
    captured = capsys.readouterr().out
    assert "page 1:" in captured


def test_extract_swallows_attribute_error_on_permission_probe(
    make_pdf: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``get_current_access_permission`` raises ``AttributeError``
    the example silently proceeds with extraction — covers lines 47-49.
    """
    src = make_pdf("attr-error.pdf", page_count=1)

    def _boom(self) -> None:  # noqa: ANN001
        raise AttributeError("encryption probe unsupported")

    monkeypatch.setattr(
        "pypdfbox.pdmodel.pd_document.PDDocument.get_current_access_permission",
        _boom,
    )
    text = ExtractTextSimple.extract(str(src))
    assert "page 1:" in text


def test_extract_swallows_not_implemented_error_on_permission_probe(
    make_pdf: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same guard catches ``NotImplementedError``."""
    src = make_pdf("notimpl.pdf", page_count=1)

    def _boom(self) -> None:  # noqa: ANN001
        raise NotImplementedError("not wired yet")

    monkeypatch.setattr(
        "pypdfbox.pdmodel.pd_document.PDDocument.get_current_access_permission",
        _boom,
    )
    text = ExtractTextSimple.extract(str(src))
    assert "page 1:" in text


def test_extract_raises_when_extraction_forbidden(
    make_pdf: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the access permission denies extraction, the helper raises
    ``OSError("You do not have permission to extract text")`` — line 46."""
    src = make_pdf("no-extract.pdf", page_count=1)

    class _NoExtract:
        def can_extract_content(self) -> bool:
            return False

    def _denied(self) -> _NoExtract:  # noqa: ANN001
        return _NoExtract()

    monkeypatch.setattr(
        "pypdfbox.pdmodel.pd_document.PDDocument.get_current_access_permission",
        _denied,
    )
    with pytest.raises(OSError, match="permission to extract text"):
        ExtractTextSimple.extract(str(src))


def test_module_attributes_present() -> None:
    """Sanity: the module exports the class and its static helpers."""
    assert hasattr(extract_text_simple, "ExtractTextSimple")
    assert callable(ExtractTextSimple.extract)
    assert callable(ExtractTextSimple.main)
    assert callable(ExtractTextSimple.usage)
