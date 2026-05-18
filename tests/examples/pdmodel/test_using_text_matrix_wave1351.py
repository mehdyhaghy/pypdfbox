"""Coverage-boost (wave 1351) for
:mod:`pypdfbox.examples.pdmodel.using_text_matrix`.

Covers the ``main`` ``len(argv) != 2`` branch (line 125 — falls into
``usage()``) and the direct ``usage()`` ``sys.stderr.write`` call
(line 130).
"""

from __future__ import annotations

import pytest

from pypdfbox.examples.pdmodel.using_text_matrix import UsingTextMatrix


def test_main_with_no_args_falls_through_to_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``main([])`` triggers the ``len(argv) != 2`` branch, which in turn
    calls :meth:`UsingTextMatrix.usage` — the usage text lands on stderr.
    """
    UsingTextMatrix.main([])
    captured = capsys.readouterr()
    assert "usage:" in captured.err
    assert "UsingTextMatrix" in captured.err
    assert captured.out == ""


def test_main_with_one_arg_falls_through_to_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    UsingTextMatrix.main(["only-message"])
    assert "usage:" in capsys.readouterr().err


def test_main_with_three_args_falls_through_to_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    UsingTextMatrix.main(["a", "b", "c"])
    assert "usage:" in capsys.readouterr().err


def test_main_with_none_argv_falls_through_to_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``argv=None`` normalises to ``[]`` and trips the usage branch."""
    UsingTextMatrix.main(None)
    assert "usage:" in capsys.readouterr().err


def test_usage_writes_only_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Directly drive ``usage()`` to exercise line 130's stderr write."""
    UsingTextMatrix().usage()
    captured = capsys.readouterr()
    assert "usage:" in captured.err
    assert "UsingTextMatrix <Message> <output-file>" in captured.err
    assert captured.out == ""
