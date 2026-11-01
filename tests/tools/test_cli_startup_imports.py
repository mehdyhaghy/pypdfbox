"""Startup-cost regression tests for ``import pypdfbox`` and the CLI.

The CLI registers subcommands without importing their implementation
modules, and the package re-exports resolve lazily, so neither ``import
pypdfbox.tools.cli`` nor loading a small PDF may pull in the heavy
third-party stacks (numpy, Pillow, skia, imagecodecs, fontTools,
cryptography). Each check runs in a fresh interpreter so imports done by
other tests in this process cannot mask a regression.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

from pypdfbox.tools import cli

HEAVY = ("numpy", "PIL", "skia", "imagecodecs", "fontTools", "cryptography")
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "text" / "input" / "eu-001.pdf"


def _loaded_heavy(code: str) -> list[str]:
    script = (
        "import json, sys\n"
        + code
        + f"\nprint(json.dumps([m for m in {list(HEAVY)!r} if m in sys.modules]))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_cli_import_loads_no_heavy_dependency() -> None:
    assert _loaded_heavy("import pypdfbox.tools.cli") == []


def test_package_import_loads_no_heavy_dependency() -> None:
    assert _loaded_heavy("import pypdfbox\nfrom pypdfbox import Loader, PDDocument") == []


def test_loading_a_pdf_loads_no_heavy_dependency() -> None:
    code = (
        "from pypdfbox import PDDocument\n"
        f"doc = PDDocument.load({str(FIXTURE)!r})\n"
        "assert doc.get_number_of_pages() > 0\n"
        "doc.get_document_information()\n"
        "for page in doc.get_pages():\n"
        "    page.get_media_box()\n"
        "    page.get_resources()\n"
        "doc.close()\n"
    )
    assert _loaded_heavy(code) == []


def test_version_command_loads_no_heavy_dependency() -> None:
    code = (
        "import contextlib, io\n"
        "from pypdfbox.tools.cli import run_cli\n"
        "with contextlib.redirect_stdout(io.StringIO()):\n"
        "    assert run_cli(['version']) == 0\n"
    )
    assert _loaded_heavy(code) == []


def test_filter_registry_complete_after_lazy_imports() -> None:
    """Every stream filter registers itself on first FilterFactory use."""
    code = (
        "from pypdfbox.filter.filter_factory import FilterFactory\n"
        "names = ['ASCIIHexDecode', 'ASCII85Decode', 'LZWDecode', 'FlateDecode',\n"
        "         'RunLengthDecode', 'CCITTFaxDecode', 'DCTDecode', 'JBIG2Decode',\n"
        "         'JPXDecode', 'Crypt', 'AHx', 'A85', 'LZW', 'Fl', 'RL', 'CCF', 'DCT']\n"
        "for name in names:\n"
        "    FilterFactory.get(name)\n"
    )
    assert _loaded_heavy(code) == []


def _eager_root_parser() -> argparse.ArgumentParser:
    """The parser as built before subcommands became lazy."""
    parser = argparse.ArgumentParser(
        prog="pypdfbox",
        description="Command-line tools for pypdfbox — Python-native port of "
        "Apache PDFBox.",
    )
    subparsers = parser.add_subparsers(
        dest="command", metavar="COMMAND", required=True, title="commands"
    )
    for _, module_name, _ in cli._COMMANDS:
        cli._load_subcommand(module_name).build_parser(subparsers)
    return parser


def test_lazy_root_help_matches_eager_parser() -> None:
    """The help lines in ``cli._COMMANDS`` stay in sync with each module."""
    assert cli._build_root_parser().format_help() == _eager_root_parser().format_help()


@pytest.mark.parametrize("command", [name for name, _, _ in cli._COMMANDS])
def test_lazy_subcommand_help_matches_eager_parser(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    outputs = []
    for build in (cli._build_root_parser, _eager_root_parser):
        with pytest.raises(SystemExit):
            build().parse_args([command, "--help"])
        outputs.append(capsys.readouterr().out)
    assert outputs[0] == outputs[1]


def test_lazy_dispatch_resolves_subcommand_run() -> None:
    args = cli._build_root_parser().parse_args(["version"])
    assert args.func is cli._load_subcommand("version").run


def test_back_compat_module_attributes() -> None:
    from pypdfbox.tools import info, pdfdebugger

    assert cli.info is info
    assert pdfdebugger in cli._SUBCOMMANDS
    with pytest.raises(AttributeError):
        _ = cli.not_a_subcommand


def test_lazy_package_exports_are_the_defining_objects() -> None:
    import pypdfbox
    from pypdfbox.loader import Loader
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    assert pypdfbox.Loader is Loader
    assert pypdfbox.PDDocument is PDDocument
    assert pypdfbox.PDPage is PDPage
    assert isinstance(pypdfbox.__version__, str)
    assert set(pypdfbox.__all__) <= set(dir(pypdfbox))
    with pytest.raises(AttributeError):
        _ = pypdfbox.NotAnExport
