"""Live PDFBox differential parity for ``/Producer`` + ``/ModDate`` handling on
full save (``pypdfbox.pdfwriter.cos_writer`` + ``pypdfbox.pdmodel.pd_document``).

Some PDF libraries (iText, PyPDF2, …) auto-stamp a vendor-tagged ``/Producer``
and refresh ``/ModDate`` to "now" on every ``save``. Apache PDFBox 3.0.7 does
**neither** — ``PDDocument.save`` is a faithful serialiser of whatever the
in-memory ``/Info`` carries. pypdfbox follows the same contract.

This module locks the contract differentially:

1. ``empty`` — a brand-new ``PDDocument()`` with one blank page, saved + reloaded,
   carries an EMPTY ``/Info`` (no ``/Producer``, ``/CreationDate``, ``/ModDate``,
   or other keys). Catches a regression where either library starts
   auto-stamping a vendor producer or "now" timestamps.
2. ``resave`` — load an existing document with a populated ``/Info``, save without
   mutation, reload — every standard ``/Info`` entry round-trips byte-identical
   (no ``/Producer`` rewrite, no ``/ModDate`` "touch", no ``/CreationDate`` drift).
3. ``mutate`` — load + ``setAuthor("test-author")`` + save. The new ``/Author``
   appears; the pre-existing ``/Producer`` / ``/ModDate`` / ``/CreationDate``
   are NOT silently rewritten (an editor-stamping regression would surface here).

The Java oracle is ``ProducerSaveProbe`` (modes ``empty`` / ``resave`` /
``mutate``); it emits ``Producer=`` / ``CreationDate=`` / ``ModDate=`` /
``keys=`` lines (US 0x1f separator inside ``keys=``). Dates render as epoch
milliseconds so Python can compare without Calendar/timezone repr drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"

# A small, populated-/Info fixture used by the resave + mutate modes. The
# unencrypted.pdf source carries /Producer = "Adobe Acrobat Pro 11.0.18" plus
# /Creator, /CreationDate, /ModDate — covers the four entries the contract
# claims should round-trip untouched.
_FIXTURE = _FIXTURES / "pdfwriter" / "unencrypted.pdf"

# US 0x1f — keys= field separator in the probe's output.
_US = "\x1f"


# ----------------------------------------------------------------- helpers


def _parse_probe(text: str) -> dict[str, str]:
    """Parse a probe's ``key=value`` line-output into a plain dict."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            out[k] = v
    return out


def _parse_keys(value: str) -> list[str]:
    """Split the ``keys=`` field on US 0x1f; empty string → empty list."""
    return [] if value == "" else value.split(_US)


def _py_empty_save(out: Path) -> None:
    """Fresh ``PDDocument()`` + one blank page → ``out``."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(str(out))
    finally:
        doc.close()


def _py_resave(src: Path, out: Path) -> None:
    """Load ``src``, save to ``out`` without mutating ``/Info``."""
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        doc.save(str(out))
    finally:
        doc.close()


def _py_mutate(src: Path, out: Path) -> None:
    """Load ``src``, set /Author to a sentinel, save to ``out``."""
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    try:
        doc.get_document_information().set_author("test-author")
        doc.save(str(out))
    finally:
        doc.close()


def _py_dump(path: Path) -> dict[str, str]:
    """Reload ``path`` through pypdfbox and produce the same key=value shape
    the Java probe emits (so we can compare dicts directly)."""
    cos = Loader.load_pdf(path)
    doc = PDDocument(cos)
    try:
        info = doc.get_document_information()
        cd = info.get_creation_date()
        md = info.get_modification_date()
        return {
            "Producer": "NULL" if info.get_producer() is None else info.get_producer(),
            "CreationDate": "NULL"
            if cd is None
            else str(int(cd.timestamp() * 1000)),
            "ModDate": "NULL" if md is None else str(int(md.timestamp() * 1000)),
            "keys": _US.join(sorted(info.get_metadata_keys())),
        }
    finally:
        doc.close()


# ----------------------------------------------------------------- empty


@requires_oracle
def test_empty_document_save_does_not_auto_stamp_info(tmp_path: Path) -> None:
    """Fresh ``new PDDocument()`` + save → ``/Info`` is empty on BOTH sides.

    Locks the contract that neither library auto-stamps a vendor ``/Producer``
    or a ``/ModDate``/``/CreationDate`` "now" on a clean save. If pypdfbox were
    to start auto-stamping a Producer or ModDate on save this assertion fires.
    """
    java_out = tmp_path / "java_empty.pdf"
    java = _parse_probe(run_probe_text("ProducerSaveProbe", "empty", str(java_out)))

    py_out = tmp_path / "py_empty.pdf"
    _py_empty_save(py_out)
    py = _py_dump(py_out)

    # PDFBox 3.0.7 stamps nothing on a fresh save — pypdfbox matches.
    assert java["Producer"] == "NULL"
    assert java["CreationDate"] == "NULL"
    assert java["ModDate"] == "NULL"
    assert _parse_keys(java["keys"]) == []

    # Pypdfbox parity.
    assert py["Producer"] == "NULL", (
        f"pypdfbox stamped /Producer on a fresh save (got {py['Producer']!r}); "
        f"PDFBox 3.0.7 leaves /Info empty"
    )
    assert py["CreationDate"] == "NULL", (
        f"pypdfbox stamped /CreationDate on a fresh save (got {py['CreationDate']!r})"
    )
    assert py["ModDate"] == "NULL", (
        f"pypdfbox stamped /ModDate on a fresh save (got {py['ModDate']!r})"
    )
    assert _parse_keys(py["keys"]) == []

    # Differential equality across every field — the strictest form of the
    # contract (catches any drift the per-field asserts would individually miss).
    assert py == java


# ----------------------------------------------------------------- resave


@requires_oracle
def test_resave_preserves_info_dict_untouched() -> None:
    """Load → save (no mutation) → reload: every ``/Info`` entry round-trips
    byte-identical on BOTH sides. No ``/Producer`` rewrite, no ``/ModDate`` touch.
    """
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        java_out = td_path / "java_resave.pdf"
        java = _parse_probe(
            run_probe_text("ProducerSaveProbe", "resave", str(_FIXTURE), str(java_out))
        )

        py_out = td_path / "py_resave.pdf"
        _py_resave(_FIXTURE, py_out)
        py = _py_dump(py_out)

    # The source fixture carries a known /Producer; both sides preserve it.
    assert java["Producer"] == "Adobe Acrobat Pro 11.0.18"
    assert py["Producer"] == "Adobe Acrobat Pro 11.0.18", (
        f"pypdfbox rewrote /Producer on resave (got {py['Producer']!r}); "
        f"PDFBox 3.0.7 preserves the source value verbatim"
    )

    # Both dates are present and unchanged across the save (so both sides
    # report identical epoch-millis on reload — no "now" touch).
    assert java["CreationDate"] != "NULL"
    assert java["ModDate"] != "NULL"
    assert py["CreationDate"] == java["CreationDate"], (
        f"pypdfbox /CreationDate drifted on resave: py={py['CreationDate']!r} "
        f"java={java['CreationDate']!r}"
    )
    assert py["ModDate"] == java["ModDate"], (
        f"pypdfbox /ModDate drifted on resave: py={py['ModDate']!r} "
        f"java={java['ModDate']!r}"
    )

    # Key sets match — neither side adds or removes /Info entries.
    assert _parse_keys(py["keys"]) == _parse_keys(java["keys"])

    # Differential equality across every field.
    assert py == java


# ----------------------------------------------------------------- mutate


@requires_oracle
def test_mutating_info_does_not_touch_producer_or_dates() -> None:
    """Load → ``setAuthor("test-author")`` → save → reload.

    The new ``/Author`` appears; the pre-existing ``/Producer``, ``/ModDate``,
    ``/CreationDate`` are NOT silently rewritten by the writer. Locks the
    "the writer is a faithful serialiser, not an editor-stamper" contract
    on the mutation path.
    """
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        java_out = td_path / "java_mutate.pdf"
        java = _parse_probe(
            run_probe_text("ProducerSaveProbe", "mutate", str(_FIXTURE), str(java_out))
        )

        py_out = td_path / "py_mutate.pdf"
        _py_mutate(_FIXTURE, py_out)
        py = _py_dump(py_out)

    # /Author landed on both sides.
    java_keys = _parse_keys(java["keys"])
    py_keys = _parse_keys(py["keys"])
    assert "Author" in java_keys
    assert "Author" in py_keys, (
        f"pypdfbox dropped /Author after set_author + save (keys={py_keys!r})"
    )

    # The original /Producer / dates survived the mutation save on BOTH sides.
    assert java["Producer"] == "Adobe Acrobat Pro 11.0.18"
    assert py["Producer"] == java["Producer"], (
        f"pypdfbox rewrote /Producer during a set_author save "
        f"(py={py['Producer']!r}, java={java['Producer']!r})"
    )
    assert py["CreationDate"] == java["CreationDate"], (
        f"pypdfbox /CreationDate drifted during set_author save: "
        f"py={py['CreationDate']!r} java={java['CreationDate']!r}"
    )
    assert py["ModDate"] == java["ModDate"], (
        f"pypdfbox /ModDate drifted during set_author save: "
        f"py={py['ModDate']!r} java={java['ModDate']!r}"
    )

    # Key sets agree.
    assert py_keys == java_keys

    # Differential equality across every field.
    assert py == java
