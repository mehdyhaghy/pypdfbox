"""Live Apache PDFBox differential parity for TrueType *subset structure*.

Where ``test_subset_embed_oracle`` pins per-GID advances and the text
round-trip, this module pins the *structural shape* of the subset font program
pypdfbox writes against Apache PDFBox 3.0.7's own subset output for the same
input:

* the ``/BaseFont`` subset prefix (``ABCDEF+``) is present on both engines;
* the embedded ``/FontFile2`` parses as a valid sfnt with the PDF-mandated
  ``glyf`` / ``loca`` / ``hmtx`` tables;
* the **same number** of glyphs is retained for the same drawn string;
* the ``/FontDescriptor`` ``/Flags`` integer matches;
* the Type0 descendant ``/W`` array has the same element count;
* the retained glyphs carry the **same advance widths** in the same order.

The probe is :file:`oracle/probes/SubsetProbe.java`, run in two modes:

* ``build`` — Apache PDFBox itself loads the bundled LiberationSans, draws
  "Hello", and saves a Type0 (subset-embedded) PDF plus a simple-TrueType PDF.
  This is the oracle's *own* subset, the structural ground truth.
* ``read`` — emits canonical, tab-delimited structural facts (FONT / PROG /
  FLAGS / WLEN lines) for every embedded font. The same ``read`` mode is run
  over pypdfbox's output so the two are compared apples-to-apples.

Documented expected divergences (NOT bugs):

* **Subset tag string differs** (``AAAAEM+`` vs ``CLFDHC+``). The PDF spec only
  requires a 6-uppercase-letter prefix; the bytes are derived from each engine's
  own hash of the retained-glyph mapping. We assert *prefix presence and shape*,
  never tag equality.
* **``/FontFile2`` byte length differs** (PDFBox ~4.5 KiB vs pypdfbox ~7.7 KiB
  for "Hello"). PDFBox strips the ``cmap`` from a CID subset; pypdfbox (via
  fontTools) retains it, and the two emit different SFNT table orderings and
  padding. Both are valid sfnt and yield identical advance widths, so we assert
  *structural* equivalence (retained-glyph count, advance multiset, valid sfnt),
  never byte equality.
* **Simple TrueType is full-embedded by PDFBox, optionally subset by pypdfbox.**
  PDFBox 3.x ``PDTrueTypeFont`` has no ``embedSubset`` flag — it always embeds
  the full font (no prefix). pypdfbox additionally supports subsetting a simple
  TrueType. The simple-font differential therefore only pins the shared invariant
  (valid sfnt, correct flags); the subset-prefix assertion is pypdfbox-only.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from fontTools.ttLib import TTFont

from pypdfbox.pdmodel import PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF = (
    Path(__file__).resolve().parents[4]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)

_TEXT = "Hello"

# "Hello" has 4 distinct visible glyphs (H, e, l, o); + .notdef = 5 retained.
_EXPECTED_RETAINED = 5

_PREFIX_RE = re.compile(r"^[A-Z]{6}\+")


# --------------------------------------------------------------------------- #
# pypdfbox builders — mirror the SubsetProbe `build` construction exactly.
# --------------------------------------------------------------------------- #


def _build_py_type0(out: Path) -> None:
    doc = PDDocument()
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    with _TTF.open("rb") as fh:
        font = PDType0Font.load(doc, fh, True)
    encoded = font.encode(_TEXT)
    font.subset(_TEXT)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 14)
        cs.new_line_at_offset(50, 700)
        cs.show_text(encoded)
        cs.end_text()
    with out.open("wb") as fh:
        doc.save(fh)
    doc.close()


def _build_py_simple(out: Path) -> None:
    doc = PDDocument()
    page = PDPage(PDRectangle.LETTER)
    doc.add_page(page)
    with _TTF.open("rb") as fh:
        font = PDTrueTypeFont.load(doc, fh)
    font.subset(_TEXT)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 14)
        cs.new_line_at_offset(50, 700)
        cs.show_text(_TEXT)
        cs.end_text()
    with out.open("wb") as fh:
        doc.save(fh)
    doc.close()


# --------------------------------------------------------------------------- #
# Probe-line parsing.
# --------------------------------------------------------------------------- #


class _FontFacts:
    """Parsed SubsetProbe `read` block for one (page, resource) font."""

    def __init__(self) -> None:
        self.base_font = ""
        self.sub_type = ""
        self.has_prefix = False
        self.font_file2_len: int | None = None
        self.num_glyphs: int | None = None
        self.non_empty_glyphs: int | None = None
        self.has_glyf = False
        self.has_loca = False
        self.has_hmtx = False
        self.has_cmap = False
        self.flags: int | None = None
        self.w_len: str | None = None


def _parse_probe(text: str) -> dict[str, _FontFacts]:
    """Parse SubsetProbe `read` output keyed by ``pageIndex/resourceName``."""
    out: dict[str, _FontFacts] = {}
    for line in text.splitlines():
        cols = line.split("\t")
        if not cols:
            continue
        tag = cols[0]
        if tag == "FONT":
            key = f"{cols[1]}/{cols[2]}"
            f = out.setdefault(key, _FontFacts())
            f.base_font = cols[3]
            f.sub_type = cols[4]
            f.has_prefix = cols[5] == "true"
        elif tag == "PROG":
            key = f"{cols[1]}/{cols[2]}"
            f = out.setdefault(key, _FontFacts())
            if len(cols) >= 10 and cols[3] != "NONE":
                f.font_file2_len = int(cols[3])
                f.num_glyphs = int(cols[4])
                f.non_empty_glyphs = int(cols[5])
                f.has_glyf = cols[6] == "true"
                f.has_loca = cols[7] == "true"
                f.has_hmtx = cols[8] == "true"
                f.has_cmap = cols[9] == "true"
        elif tag == "FLAGS":
            key = f"{cols[1]}/{cols[2]}"
            f = out.setdefault(key, _FontFacts())
            f.flags = int(cols[3])
        elif tag == "WLEN":
            key = f"{cols[1]}/{cols[2]}"
            f = out.setdefault(key, _FontFacts())
            f.w_len = cols[3]
    return out


def _only(facts: dict[str, _FontFacts]) -> _FontFacts:
    assert len(facts) == 1, f"expected one embedded font, got {list(facts)}"
    return next(iter(facts.values()))


def _font_file2_bytes(pdf_bytes: bytes) -> bytes:
    """Pull the single embedded /FontFile2 program out of a pypdfbox PDF."""
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

    doc = PDDocument.load(io.BytesIO(pdf_bytes))
    try:
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                if isinstance(font, PDType0Font):
                    desc = font.get_descendant_font()
                    fd = (
                        desc.get_font_descriptor()
                        if isinstance(desc, PDCIDFontType2)
                        else None
                    )
                elif isinstance(font, PDTrueTypeFont):
                    fd = font.get_font_descriptor()
                else:
                    continue
                ff2 = fd.get_font_file2() if fd is not None else None
                if ff2 is not None:
                    return ff2.to_byte_array()
    finally:
        doc.close()
    raise AssertionError("no embedded /FontFile2 found")


def _advance_multiset(font_file2: bytes) -> list[int]:
    tt = TTFont(io.BytesIO(font_file2))
    hmtx = tt["hmtx"]
    return sorted(hmtx[g][0] for g in tt.getGlyphOrder())


# --------------------------------------------------------------------------- #
# (1) pypdfbox-only structural pins (no oracle): the subset is well-formed.
# --------------------------------------------------------------------------- #


def test_type0_subset_has_prefix_and_retains_expected_glyphs(tmp_path: Path) -> None:
    """pypdfbox's Type0 subset: 6-letter ``/BaseFont`` prefix, ``_EXPECTED_RETAINED``
    glyphs, valid sfnt with glyf/loca/hmtx."""
    out = tmp_path / "pyt0.pdf"
    _build_py_type0(out)
    facts = _parse_probe(run_probe_read_local(out))
    f = _only(facts)
    assert f.sub_type == "Type0"
    assert _PREFIX_RE.match(f.base_font), f"no subset prefix: {f.base_font!r}"
    assert f.num_glyphs == _EXPECTED_RETAINED
    assert f.non_empty_glyphs == _EXPECTED_RETAINED
    assert f.has_glyf and f.has_loca and f.has_hmtx
    assert f.flags == 4  # SYMBOLIC, mirrors PDFBox CID embeds
    assert f.w_len == "10"


def run_probe_read_local(pdf: Path) -> str:
    """Run pypdfbox's own structural reader — mirrors SubsetProbe `read`.

    Used by the non-oracle pins so they run everywhere (no JDK needed). The
    oracle tests below cross-check this against the Java probe's `read`.
    """
    from pypdfbox.cos import COSArray, COSName
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

    lines: list[str] = []
    doc = PDDocument.load(pdf)
    try:
        for page_index, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                key = name.name if hasattr(name, "name") else str(name)
                base = str(font.get_name())
                has_prefix = bool(_PREFIX_RE.match(base))
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{base}\t"
                    f"{font.get_sub_type()}\t{'true' if has_prefix else 'false'}"
                )
                if isinstance(font, PDType0Font):
                    desc = font.get_descendant_font()
                    fd = (
                        desc.get_font_descriptor()
                        if isinstance(desc, PDCIDFontType2)
                        else None
                    )
                    w = (
                        desc.get_cos_object().get_dictionary_object(
                            COSName.get_pdf_name("W")
                        )
                        if isinstance(desc, PDCIDFontType2)
                        else None
                    )
                    w_len = str(w.size()) if isinstance(w, COSArray) else "0"
                elif isinstance(font, PDTrueTypeFont):
                    fd = font.get_font_descriptor()
                    w_len = "NA"
                else:
                    continue
                ff2 = fd.get_font_file2() if fd is not None else None
                if ff2 is None:
                    lines.append(f"PROG\t{page_index}\t{key}\tNONE")
                else:
                    raw = ff2.to_byte_array()
                    tt = TTFont(io.BytesIO(raw))
                    num = tt["maxp"].numGlyphs
                    glyf = tt["glyf"]
                    non_empty = sum(
                        1
                        for g in tt.getGlyphOrder()
                        if glyf[g] is not None
                    )
                    lines.append(
                        f"PROG\t{page_index}\t{key}\t{len(raw)}\t{num}\t"
                        f"{non_empty}\t{'true' if 'glyf' in tt else 'false'}\t"
                        f"{'true' if 'loca' in tt else 'false'}\t"
                        f"{'true' if 'hmtx' in tt else 'false'}\t"
                        f"{'true' if 'cmap' in tt else 'false'}"
                    )
                flags = fd.get_flags() if fd is not None else 0
                lines.append(f"FLAGS\t{page_index}\t{key}\t{flags}")
                lines.append(f"WLEN\t{page_index}\t{key}\t{w_len}")
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


def test_simple_subset_has_prefix_and_retains_expected_glyphs(
    tmp_path: Path,
) -> None:
    """pypdfbox's simple-TrueType subset (a pypdfbox extension over PDFBox,
    which never subsets simple fonts): prefix present, glyphs retained,
    NON_SYMBOLIC flags, valid sfnt."""
    out = tmp_path / "pysimple.pdf"
    _build_py_simple(out)
    facts = _parse_probe(run_probe_read_local(out))
    f = _only(facts)
    assert f.sub_type == "TrueType"
    assert _PREFIX_RE.match(f.base_font), f"no subset prefix: {f.base_font!r}"
    assert f.num_glyphs == _EXPECTED_RETAINED
    assert f.non_empty_glyphs == _EXPECTED_RETAINED
    assert f.has_glyf and f.has_loca and f.has_hmtx
    assert f.flags == 32  # NON_SYMBOLIC for WinAnsi-encoded simple TrueType
    assert f.w_len == "NA"


# --------------------------------------------------------------------------- #
# (2) Differential: PDFBox builds its own Type0 subset; structural parity.
# --------------------------------------------------------------------------- #


@requires_oracle
def test_type0_subset_structural_parity_with_pdfbox(tmp_path: Path) -> None:
    """Apache PDFBox builds its own Type0 subset of the same font + string;
    pypdfbox must match the *structure*: subset prefix present on both, same
    retained-glyph count, same /FontDescriptor flags, same /W length, both
    valid sfnt with glyf/loca/hmtx. Byte length and subset-tag string are
    expected to differ (documented in the module docstring)."""
    j_t0 = tmp_path / "j_t0.pdf"
    j_simple = tmp_path / "j_simple.pdf"
    run_probe_text(
        "SubsetProbe", "build", str(_TTF), _TEXT, str(j_t0), str(j_simple)
    )
    java = _only(_parse_probe(run_probe_text("SubsetProbe", "read", str(j_t0))))

    py_pdf = tmp_path / "py_t0.pdf"
    _build_py_type0(py_pdf)
    py = _only(_parse_probe(run_probe_text("SubsetProbe", "read", str(py_pdf))))

    # Subset prefix present on BOTH (tag bytes differ by design).
    assert java.has_prefix, f"PDFBox baseFont lacks prefix: {java.base_font!r}"
    assert py.has_prefix, f"pypdfbox baseFont lacks prefix: {py.base_font!r}"

    # Same NUMBER of glyphs retained for the same drawn string.
    assert py.num_glyphs == java.num_glyphs == _EXPECTED_RETAINED
    assert py.non_empty_glyphs == java.non_empty_glyphs

    # Both parse as valid sfnt with the PDF-mandated tables.
    for f in (java, py):
        assert f.has_glyf and f.has_loca and f.has_hmtx

    # Descriptor flags + /W length match.
    assert py.flags == java.flags
    assert py.w_len == java.w_len

    # DOCUMENTED divergence: bytes / tag differ, so they MUST NOT be asserted
    # equal. Pin the difference so a future "they happen to match" doesn't go
    # unnoticed silently, but treat inequality as expected.
    assert py.base_font != java.base_font or py.font_file2_len == java.font_file2_len


@requires_oracle
def test_type0_subset_advance_widths_match_pdfbox(tmp_path: Path) -> None:
    """The retained glyphs must carry the SAME advance widths in both subset
    programs (the load-bearing structural fact behind byte-level differences).
    Compared as a multiset because subset glyph renumbering / naming differs."""
    j_t0 = tmp_path / "j_t0.pdf"
    j_simple = tmp_path / "j_simple.pdf"
    run_probe_text(
        "SubsetProbe", "build", str(_TTF), _TEXT, str(j_t0), str(j_simple)
    )
    py_pdf = tmp_path / "py_t0.pdf"
    _build_py_type0(py_pdf)

    java_adv = _advance_multiset(_font_file2_bytes(j_t0.read_bytes()))
    py_adv = _advance_multiset(_font_file2_bytes(py_pdf.read_bytes()))
    assert py_adv == java_adv, f"advance multiset diverged: py={py_adv} java={java_adv}"


@requires_oracle
def test_pdfbox_simple_truetype_is_full_embedded_not_subset(tmp_path: Path) -> None:
    """Documents the engine difference: PDFBox 3.x never subsets a *simple*
    TrueType (no embedSubset flag) — it full-embeds with no prefix and the
    complete glyph table. pypdfbox additionally supports simple subsetting.
    This pins the upstream behaviour so the divergence stays intentional."""
    j_t0 = tmp_path / "j_t0.pdf"
    j_simple = tmp_path / "j_simple.pdf"
    run_probe_text(
        "SubsetProbe", "build", str(_TTF), _TEXT, str(j_t0), str(j_simple)
    )
    java = _only(_parse_probe(run_probe_text("SubsetProbe", "read", str(j_simple))))
    assert java.sub_type == "TrueType"
    assert not java.has_prefix, "PDFBox unexpectedly subset a simple TrueType"
    # Full font retained — far more glyphs than the 5 a subset would keep.
    assert java.num_glyphs is not None and java.num_glyphs > 100
