"""Live PDFBox differential parity for embedded-file *detail* + /AF linkage.

Backed by the Java probe ``oracle/probes/EmbeddedFileDetailProbe.java`` — the
file-spec / ``/Params`` surface that the existing ``EmbedFilesProbe`` (name +
filename + decoded-byte hash) deliberately does NOT cover. The probe loads a
PDF and emits, for every embedded file flattened across the catalog's
``/Names /EmbeddedFiles`` name tree (sorted by name), one canonical
tab-separated line carrying the rich fields::

    ef \t name \t F \t UF \t AFRelationship \t subtype \t size \t
         created \t modified \t declen \t checksumHex \t contentSha1

read via PDFBox's typed accessors (``getFile`` / ``getFileUnicode`` /
``getEmbeddedFile().getSize()`` / ``getCreationDate()`` / ``getModDate()`` /
``getSubtype()`` / ``getCheckSum()`` / ``toByteArray()``). It then emits the
catalog-level ``/AF`` associated-files array, one ``af`` line per entry::

    af \t index \t F \t UF \t AFRelationship

``/AFRelationship`` and the catalog ``/AF`` array are read raw from COS because
PDFBox 3.0.7 surfaces no typed ``getAFRelationship()`` / ``getAF()`` — that is
exactly the parity point: the name + linkage pypdfbox stores must equal the
bytes PDFBox round-trips. Dates render ISO-8601 (from the ``Calendar`` getter,
matching ``MetaProbe.isoDate``); the binary MD5 ``/CheckSum`` renders as
canonical hex so the comparison is binary-safe.

The pypdfbox side reproduces the identical walk through the public PD model
surface — ``PDDocument`` → ``get_document_catalog()`` → name dict →
``PDEmbeddedFilesNameTreeNode`` → ``PDComplexFileSpecification`` →
``get_file`` / ``get_file_unicode`` / ``get_af_relationship`` /
``get_embedded_file()`` → ``get_subtype`` / ``get_size`` / ``get_creation_date``
/ ``get_mod_date`` / ``get_check_sum`` / ``to_byte_array`` — plus
``get_associated_files()`` for the ``/AF`` linkage. The test asserts the two
dumps are byte-for-byte equal.

The PDF is built once via pypdfbox (``tmp_path``) with a single rich
attachment: ``/F`` ASCII filename, ``/UF`` unicode filename (non-ASCII, the
high-value ``/UF`` case), ``/AFRelationship /Data`` (enum round-trip),
``/Params`` ``/Size`` + ``/CreationDate`` + ``/ModDate`` (DateConverter
round-trip, wave 1437) + MD5 ``/CheckSum`` + ``/Subtype text/plain``,
registered in ``/Names /EmbeddedFiles`` *and* as a document-level ``/AF``.
"""

from __future__ import annotations

import datetime as _dt
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

# Payload + fixed metadata so the SHA-1 / MD5 / dates are deterministic.
_PAYLOAD = b"the quick brown fox\njumps over 13 lazy dogs\n"
_F_NAME = "report.txt"
# Non-ASCII /UF filename — the high-value unicode round-trip case.
_UF_NAME = "résumé-ümläut.txt"
_AF_REL = PDComplexFileSpecification.AF_RELATIONSHIP_DATA  # "Data"
_SUBTYPE = "text/plain"
# A real (offset, non-UTC) creation date exercises DateConverter's offset
# handling; ModDate at UTC exercises the Z-offset path.
_IST = _dt.timezone(_dt.timedelta(hours=5, minutes=30))
_CREATED = _dt.datetime(2021, 3, 14, 9, 26, 53, tzinfo=_IST)
_MODIFIED = _dt.datetime(2022, 7, 1, 12, 0, 0, tzinfo=_dt.UTC)
_CHECKSUM = hashlib.md5(_PAYLOAD).digest()  # noqa: S324 — PDF /CheckSum is MD5 by spec
_TREE_NAME = "attachment-001"


def _build_embedded_file_pdf(path: Path) -> None:
    """Create a PDF with one rich attachment, registered in the name tree
    *and* as a document-level associated file (``/AF``)."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())

        ef = PDEmbeddedFile(doc, _PAYLOAD)
        ef.set_subtype(_SUBTYPE)
        ef.set_size(len(_PAYLOAD))
        ef.set_creation_date(_CREATED)
        ef.set_mod_date(_MODIFIED)
        ef.set_check_sum(_CHECKSUM)

        spec = PDComplexFileSpecification()
        spec.set_file(_F_NAME)
        spec.set_file_unicode(_UF_NAME)
        spec.set_af_relationship(_AF_REL)
        spec.set_embedded_file(ef)

        tree = PDEmbeddedFilesNameTreeNode()
        tree.set_names({_TREE_NAME: spec})
        catalog = doc.get_document_catalog()
        name_dict = PDDocumentNameDictionary(catalog)
        name_dict.set_embedded_files(tree)
        catalog.set_names(name_dict)

        # Document-level associated file (/AF) pointing at the same spec.
        catalog.set_associated_files([spec])

        doc.save(path)
    finally:
        doc.close()


def _iso(d: _dt.datetime | None) -> str:
    """Render a datetime the way ``MetaProbe.isoDate`` renders a Calendar:
    ``YYYY-MM-DDTHH:MM:SS+HH:MM`` (NULL when absent)."""
    if d is None:
        return "NULL"
    off = d.utcoffset() or _dt.timedelta(0)
    total = int(off.total_seconds())
    sign = "-" if total < 0 else "+"
    total = abs(total)
    return (
        f"{d.year:04d}-{d.month:02d}-{d.day:02d}"
        f"T{d.hour:02d}:{d.minute:02d}:{d.second:02d}"
        f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"
    )


def _spec_detail(spec: PDComplexFileSpecification | None) -> str:
    if spec is None:
        return "-\t-\t-\t-\t-1\tNULL\tNULL\t-1\t-\t-"
    f = spec.get_file() or "-"
    uf = spec.get_file_unicode() or "-"
    rel = spec.get_af_relationship() or "-"
    ef = spec.get_embedded_file()
    subtype = "-"
    size = -1
    created = "NULL"
    modified = "NULL"
    declen = -1
    checksum = "-"
    content_sha = "-"
    if ef is not None:
        subtype = ef.get_subtype() or "-"
        size = ef.get_size()
        created = _iso(ef.get_creation_date())
        modified = _iso(ef.get_mod_date())
        data = ef.to_byte_array()
        declen = len(data)
        content_sha = hashlib.sha1(data).hexdigest()  # noqa: S324 — parity hash
        cs = ef.get_check_sum()
        checksum = cs.hex() if cs is not None else "-"
    return (
        f"{f}\t{uf}\t{rel}\t{subtype}\t{size}\t{created}\t{modified}\t"
        f"{declen}\t{checksum}\t{content_sha}"
    )


def _pypdfbox_dump(path: Path) -> str:
    """Reproduce the EmbeddedFileDetailProbe dump from pypdfbox."""
    doc = PDDocument.load(path)
    try:
        catalog = doc.get_document_catalog()
        lines: list[str] = []

        names = catalog.get_names()
        flat: dict[str, PDComplexFileSpecification] = {}
        if names is not None:
            tree = names.get_embedded_files()
            if tree is not None:
                flat = tree.get_names() or {}
        for name in sorted(flat):
            lines.append(f"ef\t{name}\t{_spec_detail(flat[name])}")

        for i, spec in enumerate(catalog.get_associated_files()):
            f = "-"
            uf = "-"
            rel = "-"
            if isinstance(spec, PDComplexFileSpecification):
                f = spec.get_file() or "-"
                uf = spec.get_file_unicode() or "-"
                rel = spec.get_af_relationship() or "-"
            lines.append(f"af\t{i}\t{f}\t{uf}\t{rel}")

        return "".join(line + "\n" for line in lines)
    finally:
        doc.close()


@requires_oracle
def test_embedded_file_detail_matches_pdfbox(tmp_path):
    pdf = tmp_path / "embedded_detail.pdf"
    _build_embedded_file_pdf(pdf)
    java = run_probe_text("EmbeddedFileDetailProbe", str(pdf))
    py = _pypdfbox_dump(pdf)
    assert py == java


@requires_oracle
def test_embedded_file_uf_and_af_relationship_present(tmp_path):
    # Sanity: pin the high-value /UF unicode filename + /AFRelationship enum
    # so a silent regression that drops either (even if it drifted identically
    # in the Java probe) is caught against the known build inputs.
    pdf = tmp_path / "embedded_detail.pdf"
    _build_embedded_file_pdf(pdf)
    py = _pypdfbox_dump(pdf)
    ef_line = next(line for line in py.splitlines() if line.startswith("ef\t"))
    cols = ef_line.split("\t")
    # ef \t name \t F \t UF \t AFRelationship \t ...
    assert cols[1] == _TREE_NAME
    assert cols[2] == _F_NAME
    assert cols[3] == _UF_NAME
    assert cols[4] == _AF_REL
    # /AF linkage round-trips the same filename + relationship.
    af_line = next(line for line in py.splitlines() if line.startswith("af\t"))
    af_cols = af_line.split("\t")
    assert af_cols[3] == _UF_NAME
    assert af_cols[4] == _AF_REL


@requires_oracle
def test_embedded_file_params_checksum_and_size_match_known(tmp_path):
    # Independent of the oracle string: pin /Params Size + MD5 CheckSum + the
    # decoded payload SHA-1 so a /Params parse regression is caught even if the
    # Java probe were to drift identically.
    pdf = tmp_path / "embedded_detail.pdf"
    _build_embedded_file_pdf(pdf)
    py = _pypdfbox_dump(pdf)
    ef_line = next(line for line in py.splitlines() if line.startswith("ef\t"))
    cols = ef_line.split("\t")
    # ef name F UF AFRel subtype size created modified declen checksumHex sha1
    assert cols[5] == _SUBTYPE
    assert int(cols[6]) == len(_PAYLOAD)
    assert cols[7] == _iso(_CREATED)
    assert cols[8] == _iso(_MODIFIED)
    assert int(cols[9]) == len(_PAYLOAD)
    assert cols[10] == _CHECKSUM.hex()
    assert cols[11] == hashlib.sha1(_PAYLOAD).hexdigest()  # noqa: S324 — parity hash
