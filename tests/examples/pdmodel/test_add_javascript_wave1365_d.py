"""Wave 1365 — coverage round-out for :class:`AddJavascript`.

Existing waves cover the happy 2-arg path (``main`` end-to-end) and the
zero-arg usage gate. This module deepens to:

* the ``__init__`` no-op body,
* the ``usage`` direct-call path (no argv),
* the encrypted-source guard (``if document.is_encrypted()`` raises),
* the wrong-arg-count branch (``len(argv) != 2``) for one and three args.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.pdmodel.add_javascript import AddJavascript
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


def _make_blank_pdf(path: Path) -> None:
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(str(path))


def test_constructor_is_a_no_op() -> None:
    """Cover the no-op ``__init__`` body (line 15)."""
    instance = AddJavascript()
    assert isinstance(instance, AddJavascript)


def test_usage_writes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """``usage`` writes the syntax line to ``stderr`` (lines 45-48)."""
    AddJavascript.usage()
    captured = capsys.readouterr()
    assert "AddJavascript" in captured.err
    assert "<input-pdf>" in captured.err
    assert "<output-pdf>" in captured.err


def test_main_with_zero_args_prints_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Zero args hits the usage gate and returns without raising
    (lines 21-23)."""
    AddJavascript.main([])
    captured = capsys.readouterr()
    assert "AddJavascript" in captured.err


def test_main_with_one_arg_prints_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One arg also fails the ``len(argv) != 2`` check (line 21)."""
    AddJavascript.main(["only-input.pdf"])
    captured = capsys.readouterr()
    assert "AddJavascript" in captured.err


def test_main_with_three_args_prints_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Three args also fails the ``len(argv) != 2`` check."""
    AddJavascript.main(["a.pdf", "b.pdf", "c.pdf"])
    captured = capsys.readouterr()
    assert "AddJavascript" in captured.err


def test_main_with_none_argv_prints_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``main(None)`` is normalised to ``[]`` (line 20)."""
    AddJavascript.main(None)
    captured = capsys.readouterr()
    assert "AddJavascript" in captured.err


def test_main_rejects_encrypted_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``if document.is_encrypted()`` raises ``OSError`` (lines 38-41).

    Patch ``PDDocument.is_encrypted`` to return ``True`` so the guard
    fires without needing a real encrypted PDF fixture.
    """
    src = tmp_path / "src.pdf"
    dst = tmp_path / "dst.pdf"
    _make_blank_pdf(src)

    monkeypatch.setattr(
        PDDocument, "is_encrypted", lambda self: True,
    )
    with pytest.raises(OSError, match="Encrypted"):
        AddJavascript.main([str(src), str(dst)])
