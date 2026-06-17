"""Live Apache PDFBox differential parity for **CFF / Type1C** font subset
structure — the CFF (``/FontFile3``) sibling of ``test_subset_oracle`` (which
covers the TrueType ``/FontFile2`` / ``glyf`` side). The two never overlap.

Apache PDFBox 3.0.7 has **no public CFF subset-embed builder**:
``PDType0Font.load`` routes every input through ``TTFParser`` and throws
"True Type fonts using CFF outlines are not supported" for a CFF-flavoured OTF
(verified empirically — see the probe's class doc). So the ground truth for a
CFF subset is a CFF subset *already embedded* in a real PDF, read back through
both engines. This module pins the structural shape of those embedded CFF
programs against PDFBox 3.0.7's own reading of the same fixtures:

* the ``/BaseFont`` subset prefix (``ABCDEF+``) is present on both engines;
* the ``/FontFile3`` ``/Subtype`` matches (``Type1C`` / ``CIDFontType0C``);
* the decoded ``/FontFile3`` byte length matches (same embedded program);
* the embedded program parses as a valid CFF via fontbox ``CFFParser`` on both
  engines, retaining the **same glyph count** (charset == charstrings);
* the CID-keyed flag matches;
* the ``/FontDescriptor`` ``/Flags`` integer matches;
* the Type0 descendant ``/W`` array has the same element count;
* ``getWidthFromFont`` for every addressed code matches Apache PDFBox.

Both engines read the *same* embedded subset bytes, so the CFF program is
byte-identical here (these are real-PDF fixtures, not engine-generated subsets).
The structural assertions stay engine-agnostic anyway — per the task brief, a
freshly *generated* CFF subset would legitimately differ at the byte level
(charstring ordering / subr packing); parity is asserted on the parsed
structure (subtype, prefix, glyph count, valid CFF, widths), never on raw bytes.

Per-code width parity uses an integer (1/1000-em rounded) comparison: PDFBox
runs the advance through a ``float`` font-matrix transform and emits values like
``778.0001`` where pypdfbox computes ``778.0000``; the sub-unit delta is
floating-point noise, not a metric divergence, so widths are compared at
whole-unit resolution.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSName, COSNumber
from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "pdmodel" / "font"

# Two bundled CFF subsets copied verbatim from Apache PDFBox 3.0.x test
# resources (see PROVENANCE.md):
#   * a Type0/CFF document (descendant /FontFile3 /CIDFontType0C), and
#   * a simple Type1 document (/FontFile3 /Type1C).
_CID_PDF = _FIXTURES / "PDFBOX-3062-005717-p1.pdf"
_T1C_PDF = _FIXTURES / "PDFBOX-3044-010197-p5-ligatures.pdf"


# --------------------------------------------------------------------------- #
# Probe-line parsing (CffSubsetProbe `read` output).
# --------------------------------------------------------------------------- #


class _CffFacts:
    """Parsed CffSubsetProbe `read` block for one (page, resource) font."""

    def __init__(self) -> None:
        self.base_font = ""
        self.sub_type = ""
        self.has_prefix = False
        self.ff3_sub_type: str | None = None
        self.ff3_len: int | None = None
        self.is_cid: bool | None = None
        self.glyph_count: int | None = None
        self.flags: int | None = None
        self.w_len: str | None = None
        self.widths: dict[int, float] = {}


def _parse_probe(text: str) -> dict[str, _CffFacts]:
    out: dict[str, _CffFacts] = {}
    for line in text.splitlines():
        cols = line.split("\t")
        if not cols or not cols[0]:
            continue
        tag = cols[0]
        if tag == "FONT" and len(cols) >= 6:
            f = out.setdefault(f"{cols[1]}/{cols[2]}", _CffFacts())
            f.base_font = cols[3]
            f.sub_type = cols[4]
            f.has_prefix = cols[5] == "true"
        elif tag == "FF3" and len(cols) >= 6:
            f = out.setdefault(f"{cols[1]}/{cols[2]}", _CffFacts())
            f.ff3_sub_type = cols[3]
            f.ff3_len = int(cols[4])
            f.is_cid = cols[5] == "true"
        elif tag == "CFF" and len(cols) >= 4:
            f = out.setdefault(f"{cols[1]}/{cols[2]}", _CffFacts())
            f.glyph_count = int(cols[3]) if cols[3].lstrip("-").isdigit() else None
        elif tag == "FLAGS" and len(cols) >= 4:
            f = out.setdefault(f"{cols[1]}/{cols[2]}", _CffFacts())
            f.flags = int(cols[3])
        elif tag == "WLEN" and len(cols) >= 4:
            f = out.setdefault(f"{cols[1]}/{cols[2]}", _CffFacts())
            f.w_len = cols[3]
        elif tag == "WID" and len(cols) >= 5:
            f = out.setdefault(f"{cols[1]}/{cols[2]}", _CffFacts())
            if cols[4] != "ERR":
                f.widths[int(cols[3])] = float(cols[4])
    return out


# --------------------------------------------------------------------------- #
# pypdfbox-side fact extraction — mirrors the probe field-for-field.
# --------------------------------------------------------------------------- #


def _ff3_bytes_and_subtype(font: object) -> tuple[bytes | None, str | None]:
    fd = font.get_font_descriptor()
    if fd is None:
        return None, None
    ff3 = fd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("FontFile3"))
    if ff3 is None:
        return None, None
    sub = ff3.get_cos_object().get_name_as_string(COSName.get_pdf_name("Subtype"))
    stream = ff3.create_input_stream()
    try:
        data = bytes(stream.read())
    finally:
        stream.close()
    return data, sub


def _used_codes(font: object, is_type0: bool) -> list[int]:
    codes: set[int] = set()
    if is_type0:
        desc = font.get_descendant_font()
        w = (
            desc.get_cos_object().get_dictionary_object(COSName.get_pdf_name("W"))
            if desc is not None
            else None
        )
        if w is not None:
            i, n = 0, w.size()
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
                        codes.add(c_first + k)
                    i += 2
                elif isinstance(nxt, COSNumber):
                    if i + 2 >= n:
                        break
                    c_last = nxt.int_value()
                    for c in range(c_first, min(c_last, c_first + 1024) + 1):
                        codes.add(c)
                    i += 3
                else:
                    break
    else:
        d = font.get_cos_object()
        fc = d.get_dictionary_object(COSName.get_pdf_name("FirstChar"))
        lc = d.get_dictionary_object(COSName.get_pdf_name("LastChar"))
        if isinstance(fc, COSNumber) and isinstance(lc, COSNumber):
            first, last = fc.int_value(), lc.int_value()
            for c in range(first, min(last, first + 255) + 1):
                codes.add(c)
    return sorted(codes)


def _py_facts(pdf: Path) -> dict[str, _CffFacts]:
    out: dict[str, _CffFacts] = {}
    doc = PDDocument.load(str(pdf))
    try:
        for pi, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                key_name = name.get_name() if hasattr(name, "get_name") else str(name)
                key = f"{pi}/{key_name.lstrip('/')}"
                f = out.setdefault(key, _CffFacts())
                base = font.get_name() or ""
                f.base_font = base
                f.sub_type = font.get_sub_type()
                f.has_prefix = bool(
                    len(base) >= 7 and base[:6].isalpha() and base[:6].isupper()
                    and base[6] == "+"
                )
                is_type0 = isinstance(font, PDType0Font)
                data, sub = _ff3_bytes_and_subtype(font)
                f.ff3_sub_type = sub if data is not None else "NONE"
                f.ff3_len = len(data) if data is not None else 0
                if data is not None:
                    try:
                        cff = CFFParser().parse(data)[0]
                        f.is_cid = cff.is_cid_font()
                        f.glyph_count = cff.get_num_char_strings()
                    except Exception:  # noqa: BLE001 — parse failure -> sentinel
                        f.is_cid = None
                        f.glyph_count = None
                fd = font.get_font_descriptor()
                f.flags = fd.get_flags() if fd is not None else None
                if is_type0:
                    desc = font.get_descendant_font()
                    wcos = (
                        desc.get_cos_object().get_dictionary_object(
                            COSName.get_pdf_name("W")
                        )
                        if desc is not None
                        else None
                    )
                    f.w_len = str(wcos.size()) if isinstance(wcos, COSArray) else "0"
                else:
                    f.w_len = "NA"
                for code in _used_codes(font, is_type0):
                    f.widths[code] = font.get_width_from_font(code)
    finally:
        doc.close()
    return out


def _assert_structural_parity(pdf: Path, probe_name: str) -> None:
    java = _parse_probe(run_probe_text("CffSubsetProbe", "read", str(pdf)))
    py = _py_facts(pdf)
    assert set(py) == set(java), f"font key sets differ: py={set(py)} java={set(java)}"
    for key, jf in java.items():
        pf = py[key]
        # Subset prefix present on both (both are real subset programs).
        assert pf.has_prefix and jf.has_prefix, key
        # /FontFile3 /Subtype matches.
        assert pf.ff3_sub_type == jf.ff3_sub_type, (key, pf.ff3_sub_type, jf.ff3_sub_type)
        # Decoded /FontFile3 program length matches (same embedded bytes).
        assert pf.ff3_len == jf.ff3_len, (key, pf.ff3_len, jf.ff3_len)
        # Both parse as valid CFF with the same retained glyph count.
        assert pf.glyph_count is not None, f"{key}: pypdfbox failed to parse CFF"
        assert jf.glyph_count is not None, f"{key}: PDFBox failed to parse CFF"
        assert pf.glyph_count == jf.glyph_count, (key, pf.glyph_count, jf.glyph_count)
        # CID-keyed flag matches.
        assert pf.is_cid == jf.is_cid, (key, pf.is_cid, jf.is_cid)
        # /FontDescriptor /Flags matches.
        assert pf.flags == jf.flags, (key, pf.flags, jf.flags)
        # Type0 descendant /W length matches.
        assert pf.w_len == jf.w_len, (key, pf.w_len, jf.w_len)
        # Per-code getWidthFromFont matches at whole-1/1000-em resolution
        # (PDFBox's float matrix transform emits sub-unit noise like .0001).
        assert set(pf.widths) == set(jf.widths), (
            key,
            "addressed-code sets differ",
        )
        for code, jw in jf.widths.items():
            assert round(pf.widths[code]) == round(jw), (
                key,
                code,
                pf.widths[code],
                jw,
            )


# --------------------------------------------------------------------------- #
# Differential tests.
# --------------------------------------------------------------------------- #


@requires_oracle
def test_cid_keyed_cff_subset_structure_matches_pdfbox() -> None:
    """Type0 + descendant /FontFile3 /CIDFontType0C subset: structure +
    per-CID widths match Apache PDFBox 3.0.7."""
    _assert_structural_parity(_CID_PDF, "CffSubsetProbe")


@requires_oracle
def test_type1c_simple_cff_subset_structure_matches_pdfbox() -> None:
    """Simple Type1 /FontFile3 /Type1C subset: structure + per-code widths
    match Apache PDFBox 3.0.7 (exercises the embedded CFF built-in encoding
    and the .notdef-width fallback for codes absent from the subset)."""
    _assert_structural_parity(_T1C_PDF, "CffSubsetProbe")


@requires_oracle
def test_cff_program_is_valid_cff_on_both_engines() -> None:
    """Sanity: every embedded /FontFile3 in both fixtures parses as a valid
    CFF font via fontbox CFFParser (charset == charstrings count, name
    present) — the structural-equivalence invariant the byte-level subset
    comparison stands in for."""
    for pdf in (_CID_PDF, _T1C_PDF):
        doc = PDDocument.load(str(pdf))
        try:
            for page in doc.get_pages():
                res = page.get_resources()
                if res is None:
                    continue
                for name in res.get_font_names():
                    font = res.get_font(name)
                    data, _ = _ff3_bytes_and_subtype(font)
                    assert data is not None
                    cff = CFFParser().parse(data)[0]
                    assert cff.get_name()
                    assert cff.get_num_char_strings() == len(cff.get_charset())
                    assert cff.get_num_char_strings() > 0
        finally:
            doc.close()
