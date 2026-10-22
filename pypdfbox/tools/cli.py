"""
Top-level ``pypdfbox`` CLI dispatcher. Mirrors upstream's
``org.apache.pdfbox.tools.PDFBox`` (which uses PicoCLI). We use the stdlib
``argparse`` so the CLI ships zero extra dependencies.

Subcommand wiring lives in this module; each subcommand registers itself
through a ``build_parser(subparsers)`` callable, keeping the dispatcher
free of business logic.
"""
import argparse
import sys
from collections.abc import Sequence
from importlib import import_module
from types import ModuleType
from typing import Any

# (command, implementation module, one-line help). Order matters only for
# ``--help`` rendering; argparse dispatches by name. The help strings must
# match what each module's ``build_parser`` passes to ``add_parser`` (pinned
# by tests/tools/test_cli_startup_imports.py). Implementation modules are
# imported only when their command runs, so ``pypdfbox --help`` and
# ``pypdfbox version`` do not pay for the PDF model, fonts, or images.
_COMMANDS: tuple[tuple[str, str, str], ...] = (
    ("info", "info", "print PDF metadata (version, page count, /Info dict)"),
    ("merge", "merge", "concatenate input PDFs into one output"),
    ("split", "split", "split a PDF into per-N-page output files"),
    ("version", "version", "print pypdfbox + Python + dependency versions"),
    ("decrypt", "decrypt", "strip encryption from a PDF"),
    ("encrypt", "encrypt", "encrypt a PDF document"),
    ("extracttext", "extracttext", "extract text from a PDF document"),
    ("imagetopdf", "imagetopdf", "create a PDF document from images"),
    ("texttopdf", "texttopdf", "create a PDF document from a text file"),
    ("listbookmarks", "listbookmarks", "print the outline (bookmarks) tree of a PDF"),
    (
        "pdfdebugger",
        "pdfdebugger",
        "print a PDF object graph as text "
        "(lite CLI replacement for upstream's Swing PDFDebugger)",
    ),
    (
        "writedecodedstream",
        "writedecodedstream",
        "rewrite a PDF with every stream decoded (filters stripped)",
    ),
)


def _load_subcommand(module_name: str) -> ModuleType:
    return import_module(f"{__package__}.{module_name}")


class _LazySubParsersAction(argparse._SubParsersAction):  # type: ignore[type-arg]
    """Subparsers action that builds a command's real parser on dispatch.

    Every command is registered up front as a stub carrying only its name
    and help line (all ``pypdfbox --help`` needs). When argparse dispatches
    to a command, the stub is swapped for the parser the implementation
    module's ``build_parser`` creates, so only that one module is imported.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._lazy_modules: dict[str, str] = {}

    def add_lazy_parser(self, name: str, module_name: str, help: str) -> None:
        self.add_parser(name, help=help)
        self._lazy_modules[name] = module_name

    def _materialize(self, name: str) -> None:
        module_name = self._lazy_modules.pop(name, None)
        if module_name is None:
            return
        module = _load_subcommand(module_name)
        # ``add_parser`` rejects a name that is already registered, so drop
        # the stub first; afterwards keep the stub's help entry and discard
        # the duplicate the real ``add_parser`` call appended.
        del self._name_parser_map[name]
        choices_before = list(self._choices_actions)
        try:
            module.build_parser(self)
        finally:
            self._choices_actions[:] = choices_before

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        if values:
            self._materialize(values[0])
        super().__call__(parser, namespace, values, option_string)


def _build_root_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pypdfbox",
        description="Command-line tools for pypdfbox — Python-native port of "
        "Apache PDFBox.",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        metavar="COMMAND",
        required=True,
        title="commands",
        action=_LazySubParsersAction,
    )
    for name, module_name, help_text in _COMMANDS:
        subparsers.add_lazy_parser(name, module_name, help_text)
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    """Parse ``argv`` (default: ``sys.argv[1:]``) and dispatch to the
    chosen subcommand. Returns the subcommand's exit code."""
    parser = _build_root_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:  # pragma: no cover — argparse rejects this path
        parser.print_help()
        return 2
    try:
        return int(func(args))
    except OSError as exc:
        # I/O failure code matches upstream's PicoCLI tools (exit 4).
        print(f"{args.command}: I/O error: {exc}", file=sys.stderr, flush=True)
        return 4


def main() -> None:
    """Console-script entry point. Calls ``sys.exit`` with the dispatched
    return code so shells see the subcommand's exit status."""
    sys.exit(run_cli())


def __getattr__(name: str) -> object:
    # Back-compat: the subcommand modules (``cli.info`` ...) and the
    # ``_SUBCOMMANDS`` tuple used to be eager module attributes.
    if name == "_SUBCOMMANDS":
        value: object = tuple(_load_subcommand(module) for _, module, _ in _COMMANDS)
    elif any(module == name for _, module, _ in _COMMANDS):
        value = _load_subcommand(name)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


if __name__ == "__main__":  # pragma: no cover — module-as-script
    main()

