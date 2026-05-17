"""Wave 1345 — coverage round-out for the ``Printing`` example port.

Targets the remaining uncovered lines: the ``args is None`` branch in
``main`` that consults ``sys.argv``, and the happy-path that loads a PDF
and dispatches to :meth:`Printing.print`.

LATENT BUG (flagged for future fix, not shimmed here): ``Printing.main``
calls ``Loader.load_pdf(args[0])`` which returns a raw ``COSDocument``,
then forwards that to :meth:`Printing.print` → :class:`PDFPageable` —
whose ``__init__`` calls ``document.get_number_of_pages()``. That method
lives on :class:`PDDocument`, not :class:`COSDocument`, so the
single-arg happy path would explode with ``AttributeError`` on any real
PDF. The wave 1314 ``pdf_to_image`` tests faced the same gap and
introduced a ``_PDLoaderShim``; ``Printing`` needs the same upstream
fix (wrap the loader result in :class:`PDDocument`). To cover lines
41-45 without papering over the bug, the test patches ``Loader`` to
return a fake document that quacks like :class:`PDDocument`.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.examples.printing import printing
from pypdfbox.examples.printing.printing import Printing


class _FakePDDocument:
    """Minimal stand-in for :class:`PDDocument` — only the surface
    :class:`PDFPageable` / :class:`PDFPrintable` touch in ``__init__``.
    """

    def __init__(self) -> None:
        self.closed = False

    def get_number_of_pages(self) -> int:
        return 1

    def close(self) -> None:
        self.closed = True


class _FakeLoader:
    @staticmethod
    def load_pdf(source: Any, password: Any = None) -> _FakePDDocument:
        return _FakePDDocument()


def test_main_with_none_args_uses_sys_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``args`` is ``None`` the helper consults ``sys.argv`` — line 34."""
    monkeypatch.setattr(printing, "Loader", _FakeLoader)
    monkeypatch.setattr("sys.argv", ["printing", "doc.pdf"])
    # Happy path — no SystemExit, no raise.
    Printing.main(None)


def test_main_with_too_many_args_exits() -> None:
    """Two positional args still trip the usage gate (SystemExit 1)."""
    with pytest.raises(SystemExit) as excinfo:
        Printing.main(["one.pdf", "two.pdf"])
    assert excinfo.value.code == 1


def test_main_one_arg_loads_and_dispatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single-arg path loads the PDF and calls :meth:`print` then closes —
    covers lines 41-45 via a fake :class:`PDDocument`-shaped document."""
    holder: dict[str, _FakePDDocument | None] = {"doc": None}

    class _CaptureLoader:
        @staticmethod
        def load_pdf(source: Any, password: Any = None) -> _FakePDDocument:
            doc = _FakePDDocument()
            holder["doc"] = doc
            return doc

    monkeypatch.setattr(printing, "Loader", _CaptureLoader)
    Printing.main(["loaded.pdf"])
    # The try/finally close branch must have run.
    assert holder["doc"] is not None
    assert holder["doc"].closed is True


def test_main_close_runs_even_when_print_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If :meth:`Printing.print` raises, the ``finally`` block still
    closes the document."""
    captured: dict[str, _FakePDDocument | None] = {"doc": None}

    class _Loader:
        @staticmethod
        def load_pdf(source: Any, password: Any = None) -> _FakePDDocument:
            doc = _FakePDDocument()
            captured["doc"] = doc
            return doc

    def _boom(document: Any) -> None:
        raise RuntimeError("print broke")

    monkeypatch.setattr(printing, "Loader", _Loader)
    monkeypatch.setattr(Printing, "print", staticmethod(_boom))
    with pytest.raises(RuntimeError):
        Printing.main(["boom.pdf"])
    assert captured["doc"] is not None
    assert captured["doc"].closed is True
