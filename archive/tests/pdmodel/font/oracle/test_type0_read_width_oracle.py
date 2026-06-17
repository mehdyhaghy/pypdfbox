"""Live PDFBox differential parity for the PARENT ``PDType0Font`` read side.

Pins the composite-font decode + width entry points that callers reach through
the parent :class:`PDType0Font` (as opposed to the descendant ``PDCIDFont``):

    * ``code_to_cid(code)``    — code -> CID through the ``/Encoding`` CMap
    * ``code_to_gid(code)``    — the composite code -> GID (parent method, which
                                 resolves code->CID then descendant CID->GID in a
                                 single parent call; upstream ``codeToGID`` throws
                                 ``IOException`` so the probe pins the ERR boundary)
    * ``get_width(code)``      — composite per-code advance in 1/1000 em
    * ``read_code(bytes) + get_width`` — the READ-side string-advance
                                 accumulation: a content-stream byte buffer is
                                 built from covered codes (Identity-H 2-byte
                                 big-endian), decoded back through ``read_code``
                                 in a loop, and the per-code widths summed. This
                                 is exactly the decode + width half of
                                 ``get_string_width`` *without* the String-encode
                                 step (which lives on the write side and is out
                                 of scope for this READ-side surface).

This is a distinct surface from the two adjacent oracle tests:

  * ``test_cid_gid_oracle`` drives the *descendant* ``PDCIDFont.codeToGID(cid)``
    and ``PDType0Font.codeToCID`` only — not the parent ``codeToGID(code)`` nor
    any width.
  * ``test_cid_width_oracle`` drives the *descendant* ``PDCIDFont.getWidth(int)``
    + ``/DW`` fallback — not the parent composite ``getWidth`` / ``getStringWidth``.

The oracle output is produced by ``oracle/probes/Type0ReadWidthProbe.java``; the
Python side reconstructs the identical line format so a divergence shows up as a
single differing line. Widths are integer-keyed table lookups formatted to 4
decimals (no platform-dependent floating point in play), so no divergence is
tolerated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSName, COSNumber, COSStream
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"

# Every fixture that carries at least one Type0 / CIDFontType2 font. All use
# Identity-H + an embedded /FontFile2. Kept in lockstep with the CidGid /
# CidWidth oracle corpora.
_FIXTURES_REL = [
    "text/input/eu-001.pdf",
    "multipdf/PDFBOX-4417-001031.pdf",
    "multipdf/PDFBOX-4417-054080.pdf",
    "multipdf/PDFBOX-5809-509329.pdf",
    "pdfwriter/attachment.pdf",
    "pdfwriter/unencrypted.pdf",
]

# Synthetic high codes beyond any embedded subset font's glyph count — exercise
# the codeToGID bound check (out-of-range CID -> GID 0) and the /DW width
# fallback. Kept in lockstep with Type0ReadWidthProbe.coveredCodes.
_OOB = (60000, 65535)

_W = COSName.get_pdf_name("W")
_ENCODING = COSName.get_pdf_name("Encoding")


def _fmt(v: float) -> str:
    """Match the Java probe's ``String.format(Locale.ROOT, "%.4f", ...)``."""
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _covered_codes(descendant: object) -> list[int]:
    """Mirror ``Type0ReadWidthProbe.coveredCodes`` exactly."""
    out: set[int] = {0}
    out.update(_OOB)
    if descendant is None:
        return sorted(out)
    w = descendant._dict.get_dictionary_object(_W)
    if isinstance(w, COSArray):
        i = 0
        n = w.size()
        while i < n:
            first = w.get_object(i)
            if not isinstance(first, COSNumber):
                break
            c_first = first.int_value()
            if i + 1 >= n:
                break
            nxt = w.get_object(i + 1)
            if isinstance(nxt, COSArray):
                for k in range(nxt.size()):
                    out.add(c_first + k)
                i += 2
            elif isinstance(nxt, COSNumber):
                if i + 2 >= n:
                    break
                c_last = nxt.int_value()
                upper = min(c_last, c_first + 1024)
                for c in range(c_first, upper + 1):
                    out.add(c)
                i += 3
            else:
                break
    return sorted(out)


def _encoding_name(font: PDType0Font) -> str:
    """Mirror ``Type0ReadWidthProbe.encodingName``."""
    enc = font._dict.get_dictionary_object(_ENCODING)
    if isinstance(enc, COSName):
        return "name:" + enc.name
    if isinstance(enc, COSStream):
        return "stream"
    if enc is not None:
        return "stream"
    return "absent"


def _sample_codes(codes: list[int]) -> list[int]:
    """Mirror ``Type0ReadWidthProbe.sampleCodes``.

    The first up-to-8 in-range covered codes (skip CID 0 and the synthetic
    out-of-range probes 60000/65535).
    """
    out: list[int] = []
    for code in codes:
        if len(out) >= 8:
            break
        if code == 0 or code >= 60000:
            continue
        out.append(code)
    return out


def _identity_bytes(codes: list[int]) -> bytes:
    """Encode codes as Identity-H 2-byte big-endian content-stream bytes."""
    out = bytearray()
    for code in codes:
        out.append((code >> 8) & 0xFF)
        out.append(code & 0xFF)
    return bytes(out)


def _py_output(pdf_path: Path) -> str:
    """Reconstruct the Type0ReadWidthProbe output from pypdfbox, line-for-line."""
    lines: list[str] = []
    doc = PDDocument.load(pdf_path)
    try:
        for page_index, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                try:
                    font = res.get_font(name)
                except Exception:
                    continue
                if not isinstance(font, PDType0Font):
                    continue
                key = name.name if hasattr(name, "name") else str(name)
                descendant = font.get_descendant_font()
                desc_subtype = (
                    "NONE" if descendant is None else type(descendant).__name__
                )
                try:
                    embedded = font.is_embedded()
                except Exception:
                    embedded = False
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{font.get_name()}\t"
                    f"{_encoding_name(font)}\t{desc_subtype}\t"
                    f"{'true' if embedded else 'false'}"
                )
                codes = _covered_codes(descendant)
                for code in codes:
                    try:
                        cid = str(font.code_to_cid(code))
                    except Exception:
                        cid = "ERR"
                    try:
                        gid = str(font.code_to_gid(code))
                    except Exception:
                        gid = "ERR"
                    try:
                        width = _fmt(font.get_width(code))
                    except Exception:
                        width = "ERR"
                    lines.append(
                        f"CODE\t{page_index}\t{key}\t{code}\t{cid}\t{gid}\t{width}"
                    )
                buffer = _identity_bytes(_sample_codes(codes))
                n_decoded = -1
                try:
                    total = 0.0
                    count = 0
                    offset = 0
                    n = len(buffer)
                    while offset < n:
                        code, consumed = font.read_code(buffer, offset)
                        if consumed <= 0:
                            break
                        total += font.get_width(code)
                        offset += consumed
                        count += 1
                    n_decoded = count
                    swb = _fmt(total)
                except Exception:
                    swb = "ERR"
                lines.append(f"SWB\t{page_index}\t{key}\t{n_decoded}\t{swb}")
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


@requires_oracle
@pytest.mark.parametrize("fixture_rel", _FIXTURES_REL)
def test_type0_read_width_matches_pdfbox(fixture_rel: str) -> None:
    """Every parent ``PDType0Font`` code->CID->GID->width + string width must
    match Apache PDFBox exactly.

    Pins the composite-font read side: the ``/Encoding`` CMap (Identity-H
    pass-through here), the parent ``codeToGID`` bound, the composite per-code
    advance, and the ``getStringWidth`` accumulation over a round-tripped
    sample string. No divergence is tolerated.
    """
    pdf_path = _FIXTURES / fixture_rel
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"
    java = run_probe_text("Type0ReadWidthProbe", str(pdf_path)).splitlines()
    py = _py_output(pdf_path).splitlines()
    assert len(java) == len(py), (
        f"line-count mismatch for {fixture_rel}: java={len(java)} py={len(py)}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, (
        f"PDType0Font read-side parity broken for {fixture_rel}:\n"
        + "\n".join(diffs[:40])
    )


@requires_oracle
def test_at_least_one_fixture_exercises_a_type0_font() -> None:
    """Guard against the parametrised suite silently covering zero fonts."""
    total = 0
    for rel in _FIXTURES_REL:
        out = run_probe_text("Type0ReadWidthProbe", str(_FIXTURES / rel))
        total += sum(1 for ln in out.splitlines() if ln.startswith("FONT\t"))
    assert total > 0
