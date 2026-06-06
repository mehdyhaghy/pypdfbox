"""Live Apache PDFBox differential parity for the **full (non-incremental)
compressed-save cross-reference STREAM geometry**.

A full compressed save (``doc.save(out, new CompressParameters())`` in PDFBox;
``COSWriter(sink, xref_stream=True, object_stream=True)`` in pypdfbox) packs
the document into object streams (``/Type /ObjStm``) addressed by a single
cross-reference stream (``/Type /XRef``). The exact ``/W`` field widths of that
xref stream are governed by ``org.apache.pdfbox.pdfparser.PDFXRefStream`` —
the same class the incremental path uses (wave 1498 fixed the increment arm):

* ``getWEntry()`` (PDFBox 3.0.7 bytecode ``getWEntry`` 0-126) sizes each ``/W``
  field to the byte width of the MAX value in that column **across the entries
  fed via ``addEntry``** (``while (w[i] > 0) { count++; w[i] >>= 8 }``), so a
  column whose max is 0 gets width **0**, not the spec-minimum 1.
* In the FULL save the xref stream's OWN self-entry (a ``NormalXReference``) IS
  registered before ``getStream()`` serialises the body, so its offset DOES feed
  the width scan — unlike the incremental arm where the self-entry is added
  after serialisation and is excluded.
* The implicit object-0 ``FreeXReference.NULL_ENTRY`` leading row is emitted by
  ``writeStreamData`` (always) but is NOT scanned for width — its generation
  65535 never widens the third column. pypdfbox additionally fills inter-object
  gaps with explicit free entries (generation 65535) for self-consistency; those
  NULL-style generations are excluded from the width scan exactly like upstream's
  implicit NULL_ENTRY, so they don't force an over-wide third column.
* The third column of a type-2 object-stream row carries the in-objstm INDEX
  (``ObjectStreamXReference.getThirdColumnValue``) and IS scanned, so a
  compressed save with object streams widens the third column to that max index.

Wave 1499 (agent A) fixed pypdfbox's full-save arm, which previously hardcoded
the third ``/W`` field to 2 bytes and folded the self-entry offset into a
``+4096``-widened second field, emitting an over-wide ``/W`` (e.g. ``[1 3 2]``)
where the entries only need ``[1 3 1]``. This module pins that the corrected
``/W`` is now minimal — each column width equals the byte-width of that column's
actual maximum (the free-entry generations excluded) — i.e. exactly what
``PDFXRefStream.getWEntry`` computes.

Note: pypdfbox's full-save *body geometry* (row count, ``/Index`` subsection
shape, absolute offsets) legitimately differs from PDFBox's — pypdfbox fills
object-number gaps with explicit free rows and packs object streams differently,
a separate documented divergence — so this module does NOT byte-compare the
decoded rows against PDFBox. It pins the **width-computation algorithm** to
parity: that pypdfbox's ``/W`` is the minimal width set for its own body, which
is precisely what the shared ``getWEntry`` would emit for those same column
maxima.
"""

from __future__ import annotations

import io
import zlib
from pathlib import Path

from pypdfbox import Loader, PDDocument
from pypdfbox.pdfwriter import COSWriter
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"

# A spread of shapes: small text doc, AcroForm, multi-page with threads/beads.
_FIXTURES_LIST = [
    _FIXTURES / "pdfwriter" / "unencrypted.pdf",
    _FIXTURES / "pdfwriter" / "acroform.pdf",
    _FIXTURES / "pdfwriter" / "PDFBOX-3110-poems-beads.pdf",
]


def _parse_probe_kv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            out[k] = v
    return out


def _py_full_compressed_xref_shape(src: Path) -> tuple[list[int], str, int, bytes]:
    """Full-compress-save ``src`` through pypdfbox and return the resulting
    xref-stream ``(W, index, rows, decoded_body)`` shape."""
    cos = Loader.load_pdf(src)
    doc = PDDocument(cos)
    buf = io.BytesIO()
    with COSWriter(buf, xref_stream=True, object_stream=True) as writer:
        writer.write(doc)
    doc.close()
    full = buf.getvalue()

    i = full.rfind(b"/Type /XRef")
    if i < 0:
        i = full.rfind(b"/Type/XRef")
    assert i >= 0, "no xref stream found in compressed save"
    obj_start = full.rfind(b"obj", 0, i)
    seg = full[obj_start : full.find(b"endstream", i) + len(b"endstream")]
    dict_part = seg[: seg.find(b"stream")]

    def _bracket(key: bytes) -> str:
        k = dict_part.find(key)
        o = dict_part.find(b"[", k)
        c = dict_part.find(b"]", o)
        return ",".join(p.decode("ascii") for p in dict_part[o + 1 : c].split())

    w = [int(x) for x in _bracket(b"/W").split(",")]
    index = _bracket(b"/Index")

    s = seg.find(b"stream")
    data_start = seg.find(b"\n", s) + 1
    data_end = seg.find(b"endstream", data_start)
    raw = seg[data_start:data_end].rstrip(b"\r\n")
    dec = zlib.decompress(raw)
    row_width = sum(w)
    rows = len(dec) // row_width if row_width else 0
    return w, index, rows, dec


def _minimal_widths_for_body(w: list[int], dec: bytes) -> list[int]:
    """Recompute the minimal ``/W`` for a decoded xref body, excluding the
    generation column of type-0 (free) rows — exactly the scan
    ``PDFXRefStream.getWEntry`` performs (the implicit/gap NULL-style free
    generations are not scanned)."""
    w1, w2, w3 = w
    row_width = w1 + w2 + w3
    rows = len(dec) // row_width if row_width else 0
    max_f = [0, 0, 0]
    for r in range(rows):
        off = r * row_width
        f1 = int.from_bytes(dec[off : off + w1], "big")
        off += w1
        f2 = int.from_bytes(dec[off : off + w2], "big")
        off += w2
        f3 = int.from_bytes(dec[off : off + w3], "big")
        max_f[0] = max(max_f[0], f1)
        max_f[1] = max(max_f[1], f2)
        if f1 != 0:  # exclude free rows' generation from the third-column scan
            max_f[2] = max(max_f[2], f3)

    def _byte_width(value: int) -> int:
        width = 0
        while value > 0:
            value >>= 8
            width += 1
        return width

    return [_byte_width(m) for m in max_f]


@requires_oracle
def test_full_save_xref_w_is_minimal_like_pdfbox_get_w_entry() -> None:
    """pypdfbox's full-compressed-save ``/W`` equals the minimal width set
    its own decoded body requires (free generations excluded) — i.e. exactly
    what the shared ``PDFXRefStream.getWEntry`` computes. Regression guard for
    the pre-wave-1499 hardcoded third-field width of 2 and the ``+4096``
    second-field widening."""
    for fixture in _FIXTURES_LIST:
        if not fixture.is_file():
            continue
        w, _index, _rows, dec = _py_full_compressed_xref_shape(fixture)
        expected = _minimal_widths_for_body(w, dec)
        assert w == expected, (
            f"{fixture.stem}: /W {w} is not minimal; getWEntry would emit {expected}"
        )


@requires_oracle
def test_full_save_xref_third_field_not_hardcoded_two() -> None:
    """The third ``/W`` field is now the byte width of the max object-stream
    index / generation column, not the pre-wave-1499 hardcoded 2. For a
    compressed save with object streams whose indices fit in one byte that is
    width 1 (regression guard for the over-wide ``w3 = 2``)."""
    fixture = _FIXTURES / "pdfwriter" / "PDFBOX-3110-poems-beads.pdf"
    if not fixture.is_file():
        return
    w, _index, _rows, dec = _py_full_compressed_xref_shape(fixture)
    # Object streams present → at least one type-2 row → third column scanned.
    assert any(row[0] == 2 for row in _iter_rows(w, dec)), "no type-2 rows present"
    expected = _minimal_widths_for_body(w, dec)
    assert w[2] == expected[2]
    assert w[2] <= 2  # the previous bug forced exactly 2 regardless of need


@requires_oracle
def test_full_save_xref_leading_row_is_null_free_head() -> None:
    """The first decoded row is the implicit object-0 ``NULL_ENTRY`` free head
    (type 0), written with the computed widths — its generation 65535 truncates
    to the third-field width without having widened the width scan."""
    fixture = _FIXTURES / "pdfwriter" / "unencrypted.pdf"
    if not fixture.is_file():
        return
    w, _index, _rows, dec = _py_full_compressed_xref_shape(fixture)
    w1, _w2, _w3 = w
    first_type = int.from_bytes(dec[:w1], "big")
    assert first_type == 0, "leading row must be the type-0 NULL_ENTRY free head"


@requires_oracle
def test_full_save_xref_w_matches_pdfbox_when_offsets_agree(tmp_path: Path) -> None:
    """When pypdfbox's compressed output is small enough that its byte offsets
    share PDFBox's magnitude band, the emitted ``/W`` equals PDFBox's verbatim.
    Probes the live oracle for PDFBox's full-compressed ``/W`` and asserts the
    third-field (index/generation) width agrees — the field that the
    pre-wave-1499 hardcode got wrong — on every fixture, and the full ``/W``
    agrees wherever the second-field offset magnitudes coincide."""
    for fixture in _FIXTURES_LIST:
        if not fixture.is_file():
            continue
        java = _parse_probe_kv(
            run_probe_text(
                "FullSaveXrefStreamShapeProbe",
                str(fixture),
                str(tmp_path / f"java_{fixture.stem}.pdf"),
            )
        )
        java_w = [int(x) for x in java["w"].split(",")]
        py_w, _index, _rows, _dec = _py_full_compressed_xref_shape(fixture)
        # Third field (the formerly-hardcoded column) matches PDFBox exactly.
        assert py_w[2] == java_w[2], (
            f"{fixture.stem}: third /W field {py_w[2]} != PDFBox {java_w[2]}"
        )
        # Type field is always one byte on both sides.
        assert py_w[0] == java_w[0] == 1
        # Where pypdfbox's offsets fit the same byte-width as PDFBox's, the
        # whole /W coincides (a wider second field reflects a genuinely larger
        # pypdfbox file, not an over-wide width — its own offsets need it).
        if py_w[1] == java_w[1]:
            assert py_w == java_w


def _iter_rows(w: list[int], dec: bytes):
    w1, w2, w3 = w
    row_width = w1 + w2 + w3
    rows = len(dec) // row_width if row_width else 0
    for r in range(rows):
        off = r * row_width
        f1 = int.from_bytes(dec[off : off + w1], "big")
        off += w1
        f2 = int.from_bytes(dec[off : off + w2], "big")
        off += w2
        f3 = int.from_bytes(dec[off : off + w3], "big")
        yield (f1, f2, f3)
