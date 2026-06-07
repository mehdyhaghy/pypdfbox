"""Live PDFBox differential parity for ``PDFMergerUtility`` *output byte
geometry* (``pypdfbox.multipdf.pdf_merger_utility``).

The companion ``test_merge_oracle.py`` pins the recoverable merged *facts*
(page text, AcroForm field set, outline, named dests). This module goes one
level deeper, to the serialized bytes, and answers the standing question:
**does a merged document serialize the same way PDFBox serializes it?**

Findings pinned here (see ``CHANGES.md`` wave 1506):

* **Merge object graph is at parity.** When BOTH sides save with the *same*
  strategy — a traditional xref table + flat object bodies
  (``CompressParameters.NO_COMPRESSION`` on the Java side, pypdfbox's default
  ``PDDocument.save``) — the merged output's object NUMBERING, ``/Type`` ROLES,
  page-tree shape, and ``%PDF`` header version are byte-identical to PDFBox for
  a plain page-concatenation merge. This isolates every byte difference in the
  *default* merge to the save strategy, not the merge logic.

* **The default-merge byte divergence is the documented save-strategy one.**
  PDFBox's ``mergeDocuments()`` saves the destination with
  ``CompressParameters.DEFAULT_COMPRESSION`` → an ``/XRef`` cross-reference
  stream + ``/ObjStm`` object streams (header bumped to 1.6). pypdfbox's merger
  saves through ``PDDocument.save`` which writes a *traditional* xref table with
  flat bodies (``compress_parameters`` is accepted for API parity but currently
  ignored — see ``pd_document.py`` save docstring + CHANGES.md). The two outputs
  therefore differ in xref style, compression, and header version. That is the
  same uncompressed-vs-compressed full-save divergence already documented in the
  pdfwriter cluster (the compressed path itself was made byte-size-identical in
  wave 1501); it is NOT a merger bug.

The Java side runs through ``MergeObjectGeometryProbe`` (which can save either
strategy); the pypdfbox side reproduces the same merge and reads the bytes back.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.pdmodel import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "multipdf"

# Plain page-concatenation pair (no shared catalog substructure to merge):
# the cleanest case for asserting numbering parity.
_PLAIN_PAIR = ("rot0.pdf", "rot90.pdf")


# --------------------------------------------------------------- helpers


def _parse_probe(text: str) -> dict[str, object]:
    """Parse ``MergeObjectGeometryProbe`` stdout into a comparable record."""
    rec: dict[str, object] = {"objs": []}
    objs: list[tuple[int, str]] = []
    for line in text.splitlines():
        if not line:
            continue
        head, _, rest = line.partition(" ")
        if head == "size":
            rec["size"] = int(rest)
        elif head == "header":
            rec["header"] = rest
        elif head == "has_xref_keyword":
            rec["has_xref_keyword"] = rest == "true"
        elif head == "has_xref_stream":
            rec["has_xref_stream"] = rest == "true"
        elif head == "objstm_count":
            rec["objstm_count"] = int(rest)
        elif head == "obj":
            num, _, typ = rest.partition(" ")
            objs.append((int(num), typ))
    rec["objs"] = objs
    return rec


def _merge_py_uncompressed(sources: list[Path]) -> bytes:
    """Reproduce the merger's append+save pipeline but capture the bytes,
    saving UNCOMPRESSED (the matched strategy for the Java NO_COMPRESSION arm).

    Mirrors what ``_legacy_merge_documents_impl`` does internally — append every
    source through ``append_document`` then full-save — so the object graph is
    exactly the merger's, and the save strategy matches the Java side."""
    merger = PDFMergerUtility()
    dest = PDDocument()
    try:
        for src in sources:
            sd = PDDocument.load(src)
            try:
                merger.append_document(dest, sd)
            finally:
                sd.close()
        buf = io.BytesIO()
        with COSWriter(buf) as writer:
            writer.write(dest)
        return buf.getvalue()
    finally:
        dest.close()


def _read_py_geometry(data: bytes) -> dict[str, object]:
    nl = data.find(b"\n")
    objs = [
        (int(m.group(1)), m.group(2).decode("latin1"))
        for m in re.finditer(rb"(\d+) 0 obj\s*<<\s*/Type\s*/(\w+)", data)
    ]
    return {
        "size": len(data),
        "header": data[:nl].decode("latin1"),
        "has_xref_keyword": b"\nxref\n" in data,
        "has_xref_stream": b"/XRef" in data,
        "objstm_count": data.count(b"/ObjStm"),
        "objs": objs,
    }


def _merge_py_default(sources: list[Path], dest_path: Path) -> bytes:
    merger = PDFMergerUtility()
    for src in sources:
        merger.add_source(str(src))
    merger.set_destination_file_name(str(dest_path))
    merger.merge_documents()
    return dest_path.read_bytes()


def _have(*names: str) -> list[Path]:
    paths = [_FIXTURES / n for n in names]
    for p in paths:
        if not p.is_file():
            pytest.skip(f"fixture missing: {p}")
    return paths


# ------------------------------------------------------------------ tests


@requires_oracle
def test_merge_object_numbering_matches_pdfbox_uncompressed() -> None:
    """Under a matched save strategy (traditional xref + flat bodies on both
    sides) the merged document's object numbering, ``/Type`` roles, page-tree
    shape, and ``%PDF`` header version are identical to PDFBox.

    This is the load-bearing parity assertion for the merge object graph: a
    merge arm that cloned in the wrong order, dropped/duplicated an object, or
    renumbered the page tree would shift this list immediately.
    """
    sources = _have(*_PLAIN_PAIR)

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        java_out = str(Path(td) / "java.pdf")
        java = _parse_probe(
            run_probe_text(
                "MergeObjectGeometryProbe",
                "uncompressed",
                java_out,
                *[str(s) for s in sources],
            )
        )

    py = _read_py_geometry(_merge_py_uncompressed(sources))

    # Same save strategy on both sides: traditional table, no ObjStm.
    assert java["has_xref_keyword"] is True
    assert py["has_xref_keyword"] is True
    assert java["objstm_count"] == py["objstm_count"] == 0

    # Header version identical (both 1.4: neither source forces a bump).
    assert py["header"] == java["header"], (
        f"merged header version diverged: pypdfbox {py['header']!r} "
        f"vs PDFBox {java['header']!r}"
    )

    # Object numbering + /Type roles identical — the merge graph parity pin.
    assert py["objs"] == java["objs"], (
        "merged object numbering / type roles diverged:\n"
        f"  pypdfbox: {py['objs']}\n  PDFBox:   {java['objs']}"
    )


@requires_oracle
def test_default_merge_save_strategy_divergence_is_documented() -> None:
    """PDFBox's default ``mergeDocuments()`` compresses the destination
    (``/XRef`` stream + ``/ObjStm``, header 1.6); pypdfbox's default merge saves
    a traditional xref table with flat bodies (``compress_parameters`` is
    accepted but currently ignored — documented divergence).

    This test PINS that divergence structurally so a future change to either
    side's default save strategy is caught: it does NOT assert byte equality
    (that is impossible while the strategies differ), it asserts each side has
    exactly the shape its documented strategy implies.
    """
    sources = _have(*_PLAIN_PAIR)

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        java = _parse_probe(
            run_probe_text(
                "MergeObjectGeometryProbe",
                "compressed",
                str(td_path / "java.pdf"),
                *[str(s) for s in sources],
            )
        )
        py = _read_py_geometry(
            _merge_py_default(sources, td_path / "py.pdf")
        )

    # PDFBox default: compressed (xref stream + at least one object stream).
    assert java["has_xref_stream"] is True
    assert java["objstm_count"] >= 1
    assert java["has_xref_keyword"] is False
    # Compression forces a version bump (>= 1.5).
    assert java["header"] >= "%PDF-1.5"

    # pypdfbox default: uncompressed traditional table, no object streams,
    # header left at the merged-document version (no compression-driven bump).
    assert py["has_xref_keyword"] is True
    assert py["has_xref_stream"] is False
    assert py["objstm_count"] == 0
    assert py["header"] == "%PDF-1.4"
