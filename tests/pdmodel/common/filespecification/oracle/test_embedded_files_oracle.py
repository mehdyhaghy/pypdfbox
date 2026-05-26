"""Live PDFBox differential parity for embedded files + name-tree traversal.

Backed by the Java probe ``oracle/probes/EmbedFilesProbe.java``, which loads a
PDF, walks the document catalog's ``/Names /EmbeddedFiles`` name tree
(flattening leaf ``/Names`` arrays across every ``/Kids`` node), and for each
embedded file emits one canonical TSV line::

    name \t F-filename \t UF-filename \t byte-length \t sha1(decoded-bytes)

A missing ``/F`` or ``/UF`` renders as ``-``; an absent embedded stream renders
length ``-1`` and sha1 ``-``. The lines are emitted sorted by name.

The pypdfbox side reproduces the identical walk through the public PD model
surface — ``PDDocument`` → ``get_document_catalog()`` →
``PDDocumentNameDictionary.get_embedded_files()`` →
``PDEmbeddedFilesNameTreeNode`` → ``PDComplexFileSpecification`` →
``PDEmbeddedFile.to_byte_array()`` — and the test asserts the two dumps are
byte-for-byte equal. This is a true differential check on names, filenames,
decoded byte lengths, and content hashes (SHA-1), not a value-translation.

Fixtures:

* ``tests/fixtures/pdfwriter/attachment.pdf`` — one attachment (``A4Unicode``).
* a two-attachment PDF built once via pypdfbox (``alpha`` text + ``beta``
  binary, the latter carrying NUL/control bytes) so the flatten-and-decode
  path is exercised with more than one entry and a non-text payload.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_embedded_file import PDEmbeddedFile
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary
from pypdfbox.pdmodel.pd_embedded_files_name_tree_node import (
    PDEmbeddedFilesNameTreeNode,
)
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[5]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"
_ATTACHMENT = _FIXTURES / "pdfwriter" / "attachment.pdf"


def _pypdfbox_dump(path: Path) -> str:
    """Reproduce the EmbedFilesProbe dump from pypdfbox.

    Walks catalog → names → embedded-files name tree → file spec → embedded
    file bytes, emitting the same sorted ``name\\tF\\tUF\\tlen\\tsha1`` lines
    the Java probe prints (trailing newline per line, matching ``println``).
    """
    doc = PDDocument.load(path)
    try:
        catalog = doc.get_document_catalog()
        names = catalog.get_names()
        flat: dict[str, PDComplexFileSpecification] = {}
        if names is not None:
            tree = names.get_embedded_files()
            if tree is not None:
                flat = tree.get_names() or {}
        lines: list[str] = []
        for name in sorted(flat):
            spec = flat[name]
            f = (spec.get_file() if spec is not None else None) or "-"
            uf = (spec.get_file_unicode() if spec is not None else None) or "-"
            ef = spec.get_embedded_file() if spec is not None else None
            if ef is not None:
                data = ef.to_byte_array()
                length = len(data)
                sha = hashlib.sha1(data).hexdigest()  # noqa: S324 — parity hash, not security
            else:
                length = -1
                sha = "-"
            lines.append(f"{name}\t{f}\t{uf}\t{length}\t{sha}")
        return "".join(line + "\n" for line in lines)
    finally:
        doc.close()


def _build_two_attachment_pdf(path: Path) -> None:
    """Create a PDF with two embedded files (one text, one binary).

    Built once via pypdfbox so the multi-entry name-tree flatten + decode
    path is diffed against the Java oracle. The ``beta`` payload carries
    NUL/control bytes to confirm the decoded-byte SHA-1 round-trips bytes
    that are not safe as text.
    """
    payloads = {
        "alpha": ("alpha.txt", b"hello world payload one\n" * 3),
        "beta": ("beta.bin", b"second attachment bytes \x00\x01\x02 zzz"),
    }
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        specs: dict[str, PDComplexFileSpecification] = {}
        for name, (filename, payload) in payloads.items():
            ef = PDEmbeddedFile(doc, payload)
            ef.set_subtype("application/octet-stream")
            ef.set_size(len(payload))
            spec = PDComplexFileSpecification()
            spec.set_file(filename)
            spec.set_file_unicode(filename)
            spec.set_embedded_file(ef)
            specs[name] = spec
        tree = PDEmbeddedFilesNameTreeNode()
        tree.set_names(specs)
        name_dict = PDDocumentNameDictionary(doc.get_document_catalog())
        name_dict.set_embedded_files(tree)
        doc.get_document_catalog().set_names(name_dict)
        doc.save(path)
    finally:
        doc.close()


@requires_oracle
def test_attachment_fixture_matches_pdfbox():
    java = run_probe_text("EmbedFilesProbe", str(_ATTACHMENT))
    py = _pypdfbox_dump(_ATTACHMENT)
    assert py == java
    # Sanity: the fixture really does carry the single A4Unicode attachment.
    assert "A4Unicode" in py


@requires_oracle
def test_two_attachment_round_trip_matches_pdfbox(tmp_path):
    pdf = tmp_path / "two_attach.pdf"
    _build_two_attachment_pdf(pdf)
    java = run_probe_text("EmbedFilesProbe", str(pdf))
    py = _pypdfbox_dump(pdf)
    assert py == java
    # Sanity: both embedded files survived the round trip, sorted by name.
    assert [line.split("\t")[0] for line in py.splitlines()] == ["alpha", "beta"]


@requires_oracle
def test_two_attachment_decoded_bytes_hash_matches_known_payload(tmp_path):
    # Independent of the oracle string, pin the SHA-1 of each decoded payload
    # so a regression in PDEmbeddedFile.to_byte_array (e.g. dropping a filter
    # round-trip) is caught even if the Java probe were to drift identically.
    pdf = tmp_path / "two_attach.pdf"
    _build_two_attachment_pdf(pdf)
    py = _pypdfbox_dump(pdf)
    rows = {
        line.split("\t")[0]: line.split("\t")[4] for line in py.splitlines()
    }
    assert rows["alpha"] == hashlib.sha1(b"hello world payload one\n" * 3).hexdigest()  # noqa: S324
    assert (
        rows["beta"]
        == hashlib.sha1(b"second attachment bytes \x00\x01\x02 zzz").hexdigest()  # noqa: S324
    )
