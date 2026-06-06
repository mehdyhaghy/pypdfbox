"""Live Apache PDFBox differential parity for the **appended cross-reference
STREAM geometry** of an incremental save over an xref-stream source.

When ``save_incremental`` appends a revision to a PDF whose most-recent
cross-reference is an xref *stream* (PDF 1.5+), ``COSWriter.doWriteXRefInc``
builds a ``PDFXRefStream`` fed only the changed objects, then writes it as a
regular object. The exact wire geometry of that stream is governed by
``org.apache.pdfbox.pdfparser.PDFXRefStream`` (PDFBox 3.0.7):

* ``getWEntry()`` sizes each ``/W`` field to the byte width of the MAX value
  in that column **across the changed entries only** — a column whose max is
  0 gets width **0** (not the spec-minimum 1). So an offset-only edit (all
  generations 0, no object-stream rows) emits ``/W [1 3 0]``.
* ``getIndexEntry()`` always seeds object 0 into the ``/Index`` range, then
  the changed object numbers — but the xref stream's OWN self-entry is
  registered on ``COSWriter`` only *after* ``getStream()`` already serialised
  the body, so it never lands in the body nor the ``/Index``.
* ``writeStreamData()`` emits a single leading object-0 row from
  ``FreeXReference.NULL_ENTRY`` (type 0, next-free 0, generation 65535)
  written with the *computed* widths — when ``/W[2] == 0`` the 65535
  generation truncates to zero bytes — then the sorted changed rows.

Wave 1498 (agent D) fixed pypdfbox, which previously (a) injected the
object-0 free head into the width scan, forcing ``/W [1 3 2]``, and (b)
appended the xref stream's self-entry as an extra body row the ``/Index``
never declared. This module pins the corrected geometry byte-for-byte
against the live oracle: the ``/W`` array, the ``/Index`` array, the row
count, and the decoded stream bytes all match Apache PDFBox on the same
deterministic edit.
"""

from __future__ import annotations

import io
import zlib
from pathlib import Path

from pypdfbox import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "pdfwriter" / "unencrypted.pdf"


def _parse_probe_kv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            out[k] = v
    return out


def _py_incremental_xref_shape() -> tuple[str, str, int, str]:
    """Reproduce the PDFBox edit in pypdfbox and return the appended
    xref-stream ``(w, index, rows, rowbytes_hex)`` shape."""
    src = _FIXTURE.read_bytes()
    doc = PDDocument.load(src)
    info = doc.get_document_information()
    info.set_author("Alice")
    info.get_cos_object().set_needs_to_be_updated(True)
    doc.get_document_catalog().get_cos_object().set_needs_to_be_updated(True)
    buf = io.BytesIO()
    doc.save_incremental(buf)
    full = buf.getvalue()
    doc.close()

    i = full.rfind(b"/Type /XRef")
    assert i >= 0, "no appended xref stream found"
    obj_start = full.rfind(b"obj", 0, i)
    seg = full[obj_start : full.find(b"endstream", i) + len(b"endstream")]
    dict_part = seg[: seg.find(b"stream")]

    def _bracket(key: bytes) -> str:
        k = dict_part.find(key)
        o = dict_part.find(b"[", k)
        c = dict_part.find(b"]", o)
        inner = dict_part[o + 1 : c].split()
        return ",".join(p.decode("ascii") for p in inner)

    w = _bracket(b"/W")
    index = _bracket(b"/Index")

    s = seg.find(b"stream")
    data_start = seg.find(b"\n", s) + 1
    data_end = seg.find(b"endstream", data_start)
    raw = seg[data_start:data_end].rstrip(b"\r\n")
    dec = zlib.decompress(raw)
    row_width = sum(int(x) for x in w.split(","))
    rows = len(dec) // row_width if row_width else 0
    return w, index, rows, dec.hex()


@requires_oracle
def test_incremental_xref_stream_shape_matches_pdfbox(tmp_path: Path) -> None:
    """pypdfbox's appended xref-stream ``/W``, ``/Index``, row count, and
    decoded bytes equal exactly what Apache PDFBox 3.0.7 writes for the same
    deterministic incremental edit."""
    java = _parse_probe_kv(
        run_probe_text(
            "IncrementalXrefStreamShapeProbe",
            str(_FIXTURE),
            str(tmp_path / "java_shape.pdf"),
        )
    )
    w, index, rows, rowbytes = _py_incremental_xref_shape()

    assert w == java["w"]
    assert index == java["index"]
    assert rows == int(java["rows"])
    assert rowbytes == java["rowbytes"]


@requires_oracle
def test_incremental_xref_stream_width_is_one_three_zero() -> None:
    """The offset-only edit yields ``/W [1 3 0]`` — the generation column is
    width 0 because every changed object has generation 0 and the implicit
    object-0 free head is excluded from the width scan (regression guard for
    the pre-wave-1498 ``[1 3 2]`` over-width)."""
    w, _index, _rows, _rowbytes = _py_incremental_xref_shape()
    assert w == "1,3,0"


@requires_oracle
def test_incremental_xref_stream_excludes_self_entry() -> None:
    """The appended stream carries exactly the object-0 free head plus the two
    changed objects (3 rows), never a self-row for the xref stream object
    itself — the ``/Index`` declares the same count, so body rows and index
    entries agree (regression guard for the pre-wave-1498 dangling 4th row)."""
    _w, index, rows, _rowbytes = _py_incremental_xref_shape()
    assert rows == 3
    # /Index subsection counts sum to the row count.
    parts = [int(x) for x in index.split(",")]
    declared = sum(parts[1::2])
    assert declared == rows == 3
