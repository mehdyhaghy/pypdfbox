"""Live PDFBox differential parity for the linearization HINT TABLE
surface (PDF 32000-1 Annex F).

Scope finding (wave 1452 — verified against the pinned PDFBox 3.0.7 jar
via :class:`HintTableProbe` and a direct ``jar tf`` of the bundled app
jar): Apache PDFBox 3.0.7 does **not** ship a hint-stream decoder. It
parses the trailing xref, surfaces the linearization parameter dict via
``COSDocument.getLinearizedDictionary()``, and stops. No public class
named ``HintTable`` / ``HPageOffset`` / ``HSharedObject`` exists in the
``pdfbox-app-3.0.7.jar`` (``jar tf`` matches only ``ContentHints.class``
from the bundled bouncycastle dependency). The full Page-Offset /
Shared-Object / Thumbnail decoders are a pypdfbox enrichment.

The parity surface here is therefore:

  (a) Linearization parameter-dictionary parity — pypdfbox reads
      ``/Linearized`` (version), ``/L``, ``/H[0..3]``, ``/O``, ``/E``,
      ``/N``, ``/T`` to the same values as PDFBox 3.0.7.
  (b) Hint-table internals — pypdfbox decodes the page-offset / shared-
      object hint tables to values whose derived totals
      (object counts, page byte lengths) are consistent with the
      linearization dict's pages count (``/N``) and PDFBox's reported
      page count.
  (c) Decoder bytes round-trip — the values read from the qpdf-produced
      linearized fixture are byte-stable: re-running the decoder gives
      identical typed structures (no hidden mutable state).

Fixtures are produced by ``qpdf --linearize`` (qpdf is Apache-2.0,
TEST-ONLY) over two non-linearized pypdfbox-savable inputs. Wave 1452
fix: the prior decoder treated the Page-Offset header as 32 bytes
(spec is 36 — items 12 + 13 are mandatory per Table F.3) and read
per-page records row-major (qpdf and the spec require column-major
per §F.3 — every column ends with skip-to-next-byte). Both bugs are
fixed in ``pypdfbox/pdfparser/linearization_hint_table.py``; the
fixture-driven assertions below would fail on either old layout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "pdfparser"

_LINEARIZED_FIXTURES = [
    _FIXTURES / "linearized_unencrypted.pdf",
    _FIXTURES / "linearized_PDFBOX-3110-poems-beads.pdf",
]


def _parse_probe(raw: str) -> dict[str, str]:
    """Parse ``key=value`` lines from the probe stdout into a dict."""
    fields: dict[str, str] = {}
    for line in raw.split("\n"):
        if not line:
            continue
        key, _, value = line.partition("=")
        fields[key] = value
    return fields


def _decode_via_pypdfbox(fixture: Path) -> dict[str, object]:
    """Decode the linearization dict + hint tables via pypdfbox and
    return a flat dict for comparison. Closes the COSDocument in a
    ``finally`` so the source handle is released before the next
    fixture (Windows file-lock safety)."""
    parser = PDFParser(RandomAccessReadBuffer(fixture.read_bytes()))
    cos_doc = parser.parse()
    try:
        lin = parser.get_linearization_dictionary()
        is_lin = parser.is_linearized()
        result: dict[str, object] = {
            "linearized": is_lin,
            "lin_dict_present": lin is not None,
        }
        if lin is not None:
            from pypdfbox.cos import (  # noqa: PLC0415 — local import for cos types
                COSArray,
                COSFloat,
                COSInteger,
                COSName,
            )

            def _int(key: str) -> int | None:
                v = lin.get_dictionary_object(COSName.get_pdf_name(key))
                if isinstance(v, (COSInteger, COSFloat)):
                    return int(v.value)
                return None

            def _float(key: str) -> float | None:
                v = lin.get_dictionary_object(COSName.get_pdf_name(key))
                if isinstance(v, (COSInteger, COSFloat)):
                    return float(v.value)
                return None

            h_arr = lin.get_dictionary_object(COSName.get_pdf_name("H"))
            h_values: list[int | None] = [None, None, None, None]
            h_count: int | None = None
            if isinstance(h_arr, COSArray):
                h_count = h_arr.size()
                for i in range(min(4, h_count)):
                    entry = h_arr.get(i)
                    if isinstance(entry, (COSInteger, COSFloat)):
                        h_values[i] = int(entry.value)
            result.update(
                {
                    "linversion": _float("Linearized"),
                    "L": _int("L"),
                    "H_count": h_count,
                    "H_0": h_values[0],
                    "H_1": h_values[1],
                    "H_2": h_values[2],
                    "H_3": h_values[3],
                    "O": _int("O"),
                    "E": _int("E"),
                    "N": _int("N"),
                    "T": _int("T"),
                }
            )

        page_offset = parser.decode_page_offset_hint_table()
        shared_object = parser.decode_shared_object_hint_table()
        result["page_offset_table"] = page_offset
        result["shared_object_table"] = shared_object
        return result
    finally:
        cos_doc.close()


# ---------------------------------------------------------------------------
# (a) Linearization-dict parity
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("fixture", _LINEARIZED_FIXTURES, ids=lambda p: p.stem)
def test_linearization_dict_keys_match_pdfbox(fixture: Path) -> None:
    """pypdfbox reads the linearization parameter dictionary's keys to
    the same values as Apache PDFBox 3.0.7. Covers ``/Linearized``,
    ``/L``, ``/H``, ``/O``, ``/E``, ``/N``, ``/T`` — all the surface
    PDFBox exposes through ``getLinearizedDictionary``."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    java = _parse_probe(run_probe_text("HintTableProbe", str(fixture)))
    assert java != {"PARSE_FAIL": ""}, "PDFBox failed to load linearized fixture"
    assert java["linearized"] == "true", "PDFBox didn't recognise the fixture"

    py = _decode_via_pypdfbox(fixture)
    assert py["linearized"] is True
    assert py["lin_dict_present"] is True

    # /Linearized version (float).
    assert py["linversion"] == float(java["linversion"]), (
        f"/Linearized version mismatch: PDFBox={java['linversion']} "
        f"pypdfbox={py['linversion']}"
    )
    # /L total file length.
    assert py["L"] == int(java["L"]), (
        f"/L mismatch: PDFBox={java['L']} pypdfbox={py['L']}"
    )
    # /H array — length + first 4 slots.
    assert py["H_count"] == int(java["H_count"]), (
        f"/H array length mismatch: PDFBox={java['H_count']} "
        f"pypdfbox={py['H_count']}"
    )
    for i in range(4):
        java_h = java[f"H_{i}"]
        py_h = py[f"H_{i}"]
        if java_h == "absent":
            assert py_h is None, f"/H[{i}] should be absent on pypdfbox"
        else:
            assert py_h == int(java_h), (
                f"/H[{i}] mismatch: PDFBox={java_h} pypdfbox={py_h}"
            )
    # /O first-page object number, /E end of first page, /N page count,
    # /T trailing xref offset.
    for key in ("O", "E", "N", "T"):
        assert py[key] == int(java[key]), (
            f"/{key} mismatch: PDFBox={java[key]} pypdfbox={py[key]}"
        )

    # PDFBox's reported page count must equal /N (which itself matches
    # pypdfbox's read above). Documents the read-side invariant the
    # linearization decoder feeds the rest of the parity tests.
    assert int(java["pages"]) == int(java["N"]) == py["N"]


# ---------------------------------------------------------------------------
# (b) Hint-table internal consistency
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("fixture", _LINEARIZED_FIXTURES, ids=lambda p: p.stem)
def test_hint_table_page_count_matches_pdfbox(fixture: Path) -> None:
    """The Page Offset Hint Table pypdfbox decodes has exactly ``/N``
    rows — one per page. Without this guarantee the per-page byte-range
    accessors (``page_length_for_page`` etc.) silently return values
    for the wrong page index."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    java = _parse_probe(run_probe_text("HintTableProbe", str(fixture)))
    py = _decode_via_pypdfbox(fixture)

    page_offset = py["page_offset_table"]
    assert page_offset is not None, (
        "pypdfbox failed to decode the Page Offset Hint Table on a "
        "genuinely linearized fixture"
    )
    expected_pages = int(java["N"])
    assert page_offset.page_count() == expected_pages, (
        f"hint-table page count mismatch vs /N: hint_table="
        f"{page_offset.page_count()} /N={expected_pages}"
    )
    # And against PDFBox's getNumberOfPages — same number reached via
    # both the linearization dict and the catalog walk.
    assert page_offset.page_count() == int(java["pages"])


@requires_oracle
@pytest.mark.parametrize("fixture", _LINEARIZED_FIXTURES, ids=lambda p: p.stem)
def test_hint_table_object_counts_positive_and_finite(fixture: Path) -> None:
    """Every per-page object count derived from the hint table is
    strictly positive (every PDF page has at least its /Page object)
    and below a sane upper bound. This catches a misaligned per-page
    bit cursor more loudly than the page-count check — wave 1452's row-
    major bug surfaced here as negative-/garbage-large object counts
    on multi-page fixtures."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    py = _decode_via_pypdfbox(fixture)
    page_offset = py["page_offset_table"]
    assert page_offset is not None
    total = int(py["N"])
    # /L is the upper bound on any plausible per-page object count —
    # no single page references more objects than the entire file's
    # byte length permits.
    file_len = int(py["L"])
    for idx in range(total):
        nobj = page_offset.object_count_for_page(idx)
        plen = page_offset.page_length_for_page(idx)
        clen = page_offset.content_stream_length_for_page(idx)
        assert nobj > 0, f"page {idx} has non-positive object count {nobj}"
        assert nobj < file_len, (
            f"page {idx} object count {nobj} exceeds /L={file_len}"
        )
        assert plen > 0, f"page {idx} has non-positive byte length {plen}"
        assert plen <= file_len, (
            f"page {idx} byte length {plen} exceeds /L={file_len}"
        )
        assert clen > 0, f"page {idx} has non-positive content length"
        assert clen <= file_len


@requires_oracle
@pytest.mark.parametrize("fixture", _LINEARIZED_FIXTURES, ids=lambda p: p.stem)
def test_hint_table_first_page_length_matches_E_minus_H(fixture: Path) -> None:
    """The first-page byte length derivable from the linearization
    parameter dictionary — ``/E - (H_offset + H_length)`` — equals the
    Page Offset Hint Table's reported length for the first page (the
    linearized first page = page 0 for both fixtures, confirmed by
    qpdf's ``first_page: 0`` field). This is the strongest single
    cross-check between PDFBox-readable values and pypdfbox's hint-
    table decoder: a row-major / wrong-header decode produces a wholly
    different number here. Wave 1452 would have failed this assertion
    on the prior 32-byte header + row-major path."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    java = _parse_probe(run_probe_text("HintTableProbe", str(fixture)))
    py = _decode_via_pypdfbox(fixture)
    e = int(java["E"])
    h0 = int(java["H_0"])
    h1 = int(java["H_1"])
    expected_first_page_len = e - (h0 + h1)

    page_offset = py["page_offset_table"]
    assert page_offset is not None
    page_zero_len = page_offset.page_length_for_page(0)
    assert page_zero_len == expected_first_page_len, (
        f"first-page byte-length mismatch: hint_table={page_zero_len} "
        f"/E-(/H[0]+/H[1])={expected_first_page_len}"
    )


# ---------------------------------------------------------------------------
# (c) Decoder byte stability — round-trip / re-read invariance
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("fixture", _LINEARIZED_FIXTURES, ids=lambda p: p.stem)
def test_hint_table_decoder_is_idempotent(fixture: Path) -> None:
    """Re-running the decoder on the same fixture yields a structurally
    identical PageOffsetHintTable — guards against any hidden cursor /
    cache state leaking between calls."""
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")

    py1 = _decode_via_pypdfbox(fixture)
    py2 = _decode_via_pypdfbox(fixture)
    a = py1["page_offset_table"]
    b = py2["page_offset_table"]
    assert a is not None and b is not None
    assert a.header == b.header
    assert a.pages == b.pages
