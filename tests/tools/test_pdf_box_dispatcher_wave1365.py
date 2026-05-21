"""Wave 1365 — broader coverage of ``pypdfbox.tools.pdf_box.PDFBox``.

The existing ``test_misc_class_ports`` file covers the unknown / no-args /
version paths. This file exercises:

* every entry in ``_SUBCOMMANDS`` is wired to a class that exposes
  ``main(...) -> int`` (mirrors upstream PDFBox.java's ``addSubcommand``
  registrations);
* ``PDFBox.run()`` raises ``SystemExit`` (port of upstream's
  ``ParameterException`` "Error: Subcommand required");
* ``PDFBox.main`` returns 0 when a subcommand returns ``None`` (matches
  the ``int(cls.main(rest) or 0)`` contract in ``pdf_box.py``);
* ``PDFBox.main(None)`` reads ``sys.argv[1:]`` rather than NPE'ing;
* the dispatcher routes the trailing argv to the chosen subcommand
  (``cls.main(rest)`` — ``rest`` must be the slice after the command
  name).
"""
from __future__ import annotations

import sys

import pytest

from pypdfbox.tools import pdf_box
from pypdfbox.tools.pdf_box import PDFBox

# ---------------------------------------------------------------------------
# Wiring parity vs. upstream PDFBox.java
# ---------------------------------------------------------------------------

# Upstream ``PDFBox.main`` (PDFBox.java:48-71) registers exactly these
# subcommands. ``debug`` is only added when not headless; ``help`` is
# picocli-builtin. We additionally register ``decompress`` (not upstream,
# but useful — and harmless to verify it stays wired).
_UPSTREAM_SUBCOMMANDS = {
    "decrypt",
    "encrypt",
    "decode",
    "export:images",
    "export:xmp",
    "export:text",
    "export:fdf",
    "export:xfdf",
    "import:fdf",
    "import:xfdf",
    "overlay",
    "print",
    "render",
    "merge",
    "split",
    "fromimage",
    "fromtext",
    "version",
}


def test_subcommand_map_covers_upstream_set() -> None:
    """The dispatcher must register every upstream subcommand name."""
    registered = set(pdf_box._SUBCOMMANDS.keys())
    missing = _UPSTREAM_SUBCOMMANDS - registered
    assert not missing, f"missing subcommands vs. upstream: {sorted(missing)}"


@pytest.mark.parametrize("name", sorted(pdf_box._SUBCOMMANDS.keys()))
def test_each_subcommand_class_has_callable_main(name: str) -> None:
    cls = pdf_box._SUBCOMMANDS[name]
    assert hasattr(cls, "main"), f"{name}: {cls.__name__} missing .main()"
    assert callable(cls.main)


# ---------------------------------------------------------------------------
# ``run`` method — picocli ParameterException analogue
# ---------------------------------------------------------------------------


def test_run_raises_system_exit() -> None:
    inst = PDFBox()
    with pytest.raises(SystemExit) as excinfo:
        inst.run()
    # Mirrors upstream "Error: Subcommand required" message.
    assert "Subcommand required" in str(excinfo.value)


# ---------------------------------------------------------------------------
# ``main`` — dispatch contract
# ---------------------------------------------------------------------------


def test_main_returns_zero_when_subcommand_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``int(cls.main(rest) or 0)`` — a ``None`` return must coerce to 0."""

    class _Stub:
        @staticmethod
        def main(_args: list[str]) -> int | None:
            return None

    monkeypatch.setitem(pdf_box._SUBCOMMANDS, "stub", _Stub)
    assert PDFBox.main(["stub", "ignored"]) == 0


def test_main_propagates_subcommand_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Stub:
        @staticmethod
        def main(_args: list[str]) -> int:
            return 7

    monkeypatch.setitem(pdf_box._SUBCOMMANDS, "stub", _Stub)
    assert PDFBox.main(["stub"]) == 7


def test_main_passes_through_remaining_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dispatcher hands ``args[1:]`` to the subcommand's ``main``."""
    captured: list[list[str]] = []

    class _Capture:
        @staticmethod
        def main(args: list[str]) -> int:
            captured.append(args)
            return 0

    monkeypatch.setitem(pdf_box._SUBCOMMANDS, "capture", _Capture)
    PDFBox.main(["capture", "--foo", "bar", "baz"])
    assert captured == [["--foo", "bar", "baz"]]


def test_main_with_none_reads_sys_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling ``PDFBox.main(None)`` (no explicit args) must read ``sys.argv``
    rather than crashing with ``TypeError``."""
    monkeypatch.setattr(sys, "argv", ["pdfbox", "version"])
    rc = PDFBox.main(None)
    assert rc == 0


def test_main_with_no_args_prints_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No args → stderr "Error: Subcommand required" + exit 2."""
    rc = PDFBox.main([])
    err = capsys.readouterr().err
    assert rc == 2
    assert "Error: Subcommand required" in err


def test_main_unknown_command_returns_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = PDFBox.main(["bogus-not-registered"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "Unknown command" in err
    assert "bogus-not-registered" in err


# ---------------------------------------------------------------------------
# Subcommand dispatch — exercise a few via their argparse error path so
# we don't depend on heavy side-effects (load_pdf etc.).
# ---------------------------------------------------------------------------


def test_dispatch_decode_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        PDFBox.main(["decode", "--help"])
    captured = capsys.readouterr()
    assert excinfo.value.code == 0
    assert "decode" in captured.out.lower() or "usage" in captured.out.lower()


def test_dispatch_render_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        PDFBox.main(["render", "--help"])
    assert excinfo.value.code == 0
    capsys.readouterr()


def test_dispatch_overlay_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        PDFBox.main(["overlay", "--help"])
    assert excinfo.value.code == 0
    capsys.readouterr()


@pytest.mark.parametrize(
    "name",
    [
        "decrypt", "encrypt", "decode", "export:images", "export:xmp",
        "export:text", "export:fdf", "export:xfdf", "import:fdf",
        "import:xfdf", "overlay", "print", "render", "merge", "split",
        "fromimage", "fromtext", "version",
    ],
)
def test_dispatch_help_for_each_subcommand(
    name: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--help`` on every upstream subcommand must exit zero (argparse)."""
    if name == "version":
        # ``Version.main`` doesn't define ``--help`` via argparse — invoking
        # it directly returns 0 anyway. Verify the no-help path.
        assert PDFBox.main([name]) == 0
        capsys.readouterr()
        return
    with pytest.raises(SystemExit) as excinfo:
        PDFBox.main([name, "--help"])
    assert excinfo.value.code == 0
    capsys.readouterr()
