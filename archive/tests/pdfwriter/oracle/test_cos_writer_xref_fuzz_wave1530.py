"""Wave 1530 — live-oracle parity for the COSWriter cross-reference TABLE +
trailer assembly (classic, non-stream full-save path).

The Java probe ``CosWriterXrefFuzzProbe`` builds small ``COSDocument``s from raw
COS primitives, drives each through a fresh ``COSWriter`` over a
``ByteArrayOutputStream``, and projects the normalized ``xref`` table + trailer
region:

    CASE <name> xref=<0|1> ranges=<f:c,...> entries=<gen/flag,...> rowlen=<n>
                size=<n> root=<0|1> info=<0|1> id=<0|1> prev=<0|1>
                startxref=<0|1> eof=<0|1>

This sibling builds the equivalent document with pypdfbox's ``COSWriter`` and
asserts byte/structure-identical projections. ``/ID`` is time/random based, so
only its PRESENCE is compared (never its bytes); everything else (subsection
grouping of contiguous object-number runs, the mandatory free-list head
``0000000000 65535 f``, the 20-byte fixed-width rows, ``/Size`` = max obj + 1,
trailer key set) is deterministic.

Wave 1530 fixed a real divergence here: pypdfbox's classic full-save path used
to preserve a programmatic ``COSObject`` wrapper's declared (possibly sparse)
object number, emitting a gap-filled sparse xref table. Upstream
``COSWriter.getObjectKey`` keys off the resolved actual's own ``getKey()`` and
renumbers any un-keyed actual contiguously from 1 — so a sparse programmatic
document collapses to a single contiguous subsection. See CHANGES.md Wave 1530.
"""

from __future__ import annotations

import io
import re

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
    COSString,
)
from pypdfbox.pdfwriter.cos_writer import COSWriter
from tests.oracle.harness import requires_oracle, run_probe_text

PROBE = "CosWriterXrefFuzzProbe"


# ---- pypdfbox document builders (mirror the Java probe) ----


def _build_explicit(nums: list[int]) -> COSDocument:
    doc = COSDocument()
    trailer = COSDictionary()
    catalog = COSDictionary()
    catalog.set_item(COSName.TYPE, COSName.get_pdf_name("Catalog"))
    root_obj = COSObject(nums[0], 0, resolved=catalog)
    kids = COSArray()
    for n in nums[1:]:
        d = COSDictionary()
        d.set_item(COSName.get_pdf_name("N"), COSInteger.get(n))
        kids.add(COSObject(n, 0, resolved=d))
    if kids.size() > 0:
        catalog.set_item(COSName.get_pdf_name("Kids"), kids)
    trailer.set_item(COSName.ROOT, root_obj)
    doc.set_trailer(trailer)
    return doc


def _build_empty() -> COSDocument:
    doc = COSDocument()
    doc.set_trailer(COSDictionary())
    return doc


def _build_with_info() -> COSDocument:
    doc = COSDocument()
    trailer = COSDictionary()
    catalog = COSDictionary()
    catalog.set_item(COSName.TYPE, COSName.get_pdf_name("Catalog"))
    root_obj = COSObject(1, 0, resolved=catalog)
    info = COSDictionary()
    info.set_item(COSName.get_pdf_name("Producer"), COSString("probe"))
    info_obj = COSObject(2, 0, resolved=info)
    trailer.set_item(COSName.ROOT, root_obj)
    trailer.set_item(COSName.get_pdf_name("Info"), info_obj)
    doc.set_trailer(trailer)
    return doc


def _build_gen_nonzero() -> COSDocument:
    doc = COSDocument()
    trailer = COSDictionary()
    catalog = COSDictionary()
    catalog.set_item(COSName.TYPE, COSName.get_pdf_name("Catalog"))
    root_obj = COSObject(1, 0, resolved=catalog)
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("N"), COSInteger.get(2))
    catalog.set_item(COSName.get_pdf_name("Ref"), COSObject(2, 3, resolved=d))
    trailer.set_item(COSName.ROOT, root_obj)
    doc.set_trailer(trailer)
    return doc


# Build order MUST mirror the Java probe's main() emission order.
def _cases() -> list[tuple[str, COSDocument]]:
    return [
        ("min_catalog", _build_explicit([1])),
        ("contig_3", _build_explicit([1, 2, 3])),
        ("contig_5", _build_explicit([1, 2, 3, 4, 5])),
        ("empty_doc", _build_empty()),
        ("noncontig_gap", _build_explicit([1, 2, 3, 7, 8, 10])),
        ("noncontig_late", _build_explicit([5, 6, 7])),
        ("noncontig_far", _build_explicit([1, 50])),
        ("noncontig_alt", _build_explicit([1, 3, 5, 7])),
        ("with_info", _build_with_info()),
        ("gen_nonzero", _build_gen_nonzero()),
    ]


# ---- pypdfbox projector (mirror CosWriterXrefFuzzProbe.project) ----


def _project(name: str, full: bytes) -> str:
    s = full.decode("iso-8859-1")

    xref_matches = list(re.finditer(r"(?m)^xref\r?\n", s))
    xref = xref_matches[-1].start() if xref_matches else -1
    has_xref = xref >= 0

    trailer_kw = s.rfind("trailer")
    startxref_kw = s.rfind("startxref")
    eof_kw = s.rfind("%%EOF")

    ranges: list[str] = []
    entries: list[str] = []
    rowlen = -1
    if has_xref and trailer_kw > xref:
        body = s[s.index("\n", xref) + 1 : trailer_kw]
        for raw in body.split("\n"):
            line = raw.rstrip("\r")
            if not line:
                continue
            parts = line.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                ranges.append(f"{parts[0]}:{parts[1]}")
            elif (
                len(parts) == 3
                and parts[0].isdigit()
                and parts[1].isdigit()
                and parts[2] in ("n", "f")
            ):
                if rowlen < 0:
                    rowlen = len(raw) + 1  # + the '\n' delimiter
                entries.append(f"{int(parts[1])}/{parts[2]}")

    size = -1
    root = info = ident = prev = False
    if trailer_kw >= 0:
        trailer_end = startxref_kw if startxref_kw > trailer_kw else len(s)
        td = s[trailer_kw:trailer_end]
        m = re.search(r"/Size\s+(-?\d+)", td)
        if m:
            size = int(m.group(1))
        root = "/Root" in td
        info = "/Info" in td
        ident = "/ID" in td
        prev = "/Prev" in td

    return (
        f"CASE {name} xref={1 if has_xref else 0} "
        f"ranges={','.join(ranges)} entries={','.join(entries)} "
        f"rowlen={rowlen} size={size} "
        f"root={1 if root else 0} info={1 if info else 0} "
        f"id={1 if ident else 0} prev={1 if prev else 0} "
        f"startxref={1 if startxref_kw >= 0 else 0} "
        f"eof={1 if eof_kw >= 0 else 0}"
    )


def _pypdfbox_lines() -> dict[str, str]:
    out: dict[str, str] = {}
    for name, doc in _cases():
        buf = io.BytesIO()
        writer = COSWriter(buf)
        try:
            writer.write(doc)
        finally:
            doc.close()
        out[name] = _project(name, buf.getvalue())
    return out


def _oracle_lines() -> dict[str, str]:
    text = run_probe_text(PROBE)
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("CASE "):
            continue
        name = line.split()[1]
        out[name] = line
    return out


_CASE_IDS = [name for name, _ in _cases()]


@requires_oracle
@pytest.mark.parametrize("case", _CASE_IDS)
def test_xref_trailer_projection_matches_pdfbox(case: str) -> None:
    oracle = _oracle_lines()
    ours = _pypdfbox_lines()
    assert case in oracle, f"oracle produced no line for {case}"
    assert ours[case] == oracle[case]


@requires_oracle
def test_all_cases_present_both_sides() -> None:
    oracle = _oracle_lines()
    ours = _pypdfbox_lines()
    assert set(oracle) == set(ours) == set(_CASE_IDS)


def test_free_list_head_and_row_width() -> None:
    """The mandatory free-list head ``0000000000 65535 f`` leads the table and
    every entry row is exactly 20 bytes (offset%010d gen%05d " n"/" f" + CRLF),
    independent of the live oracle."""
    ours = _pypdfbox_lines()
    for name, line in ours.items():
        if name == "empty_doc":
            assert "entries=65535/f " in line + " ", line
        # The leading entry is always the object-0 free head (gen 65535, f).
        m = re.search(r"entries=([^ ]+)", line)
        assert m, line
        first = m.group(1).split(",")[0]
        assert first == "65535/f", (name, first)
        # 20-byte rows when any entry is present.
        if first:
            assert " rowlen=20 " in line, (name, line)


def test_size_is_max_obj_plus_one() -> None:
    """/Size = (highest object number + 1). After contiguous renumbering a
    sparse programmatic doc with 6 objects yields /Size 7 (obj 0..6)."""
    ours = _pypdfbox_lines()
    gap = ours["noncontig_gap"]
    assert " size=7 " in gap, gap
    # Single far-out object {1,50} renumbers to 1,2 -> /Size 3.
    far = ours["noncontig_far"]
    assert " size=3 " in far, far
