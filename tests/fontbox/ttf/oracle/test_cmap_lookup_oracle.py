"""Live PDFBox differential parity for TrueType cmap subtable selection and
glyph-id resolution.

Two surfaces are exercised against Apache PDFBox 3.0.7
(``oracle/probes/CmapLookupProbe.java``):

1. **FontBox cmap API** (``ttf`` mode) — load a TTF program directly and walk
   its native ``CmapTable``: ``get_subtable(platform, encoding)`` for each of
   the canonical PDFBox priority pairs ((3,1) Win-Unicode-BMP, (3,0) Win-Symbol,
   (1,0) Mac-Roman, (0,3) Unicode-2.0-BMP, (3,10) Win-Unicode-Full,
   (0,4) Unicode-2.0-Full) plus ``subtable.get_glyph_id(codepoint)`` for a fixed
   codepoint set, and the subtable PDFBox's own priority resolver
   (``get_unicode_cmap_lookup``) picks. This covers format-0/4/6/12 segment
   search and the platform/encoding constant table.

2. **PD-font code -> GID** (``pdf`` mode) — embed the font as both a
   non-symbolic WinAnsi simple TrueType and a symbolic (3,0)-cmap TrueType, then
   assert ``PDTrueTypeFont.code_to_gid(code)`` matches PDFBox's ``codeToGID``
   for codes 0..255. The symbolic font isolates the (3,0) symbol ``0xF0xx``
   fallback; the non-symbolic font isolates the ``/Encoding`` glyph-name path.

pypdfbox delegates font-program parsing to fontTools but exposes the
FontBox-compatible native ``CmapTable`` / ``CmapSubtable`` byte parser; this
test verifies the subtable selection + GID resolution match PDFBox exactly.

Fonts used:
  * ``DejaVuSans`` — (3,1) fmt-4, (3,10) fmt-12, (0,3) fmt-4, (0,10) fmt-12,
    (1,0) fmt-6 Mac-Roman. Richest priority case; PDFBox's resolver picks the
    (3,10) format-12 full-Unicode subtable.
  * ``LiberationSans-Regular`` — (3,1) fmt-4, (0,3) fmt-4, (1,0) fmt-6. No
    full-Unicode subtable, so the (3,1)/(0,4) priority order is exercised.
  * a synthetic symbol font — DejaVuSans rewritten to carry only a (3,0)
    Windows-Symbol format-4 cmap mapping ``0xF020..0xF0FE`` (the classic symbol
    convention). Forces the (3,0) selection and the ``0xF0xx`` fallback.

The synthetic symbol font and the two embedding PDFs are generated into a
tempdir at runtime (deterministic bytes; nothing committed) and the same files
are fed to both the Java probe and the pypdfbox reproducer, so a divergence
shows up as a single differing line.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos.cos_name import COSName
from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.fontbox.ttf.cmap_table import CmapTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF_DIR = Path(__file__).resolve().parents[4] / "pypdfbox" / "resources" / "ttf"

# Mirror the probe's PAIRS / CODEPOINTS exactly.
_PAIRS = [(3, 1), (3, 0), (1, 0), (0, 3), (3, 10), (0, 4)]
_CODEPOINTS = [
    0x20, 0x41, 0x61, 0x7A, 0x80, 0xE9, 0x2122, 0x20AC, 0x1F600,
    0xF020, 0xF041, 0xF061,
]

# Flag bit 3 (value 4) = Symbolic in the /FontDescriptor /Flags bitfield.
_FLAG_SYMBOLIC = 4


def _make_symbol_font(djv_bytes: bytes) -> bytes:
    """Rewrite DejaVuSans to carry ONLY a (3,0) Windows-Symbol format-4 cmap.

    Maps ``0xF000 + c`` to the glyph DejaVu's (3,1) BMP cmap assigns to ``c``
    for ``c`` in ``0x20..0xFE`` — the classic symbol-font ``0xF0xx`` convention.
    Dropping every Unicode subtable forces both the (3,0) ``get_subtable`` hit
    and the symbolic ``0xF0xx`` code->GID fallback.
    """
    from fontTools.ttLib import TTFont  # noqa: PLC0415
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable as FTSub  # noqa: PLC0415

    tt = TTFont(io.BytesIO(djv_bytes))
    try:
        bmp = tt["cmap"].getcmap(3, 1)
        sym = FTSub.getSubtableClass(4)(4)
        sym.platformID = 3
        sym.platEncID = 0
        sym.format = 4
        sym.language = 0
        sym.cmap = {
            0xF000 + c: bmp.cmap[c] for c in range(0x20, 0xFF) if c in bmp.cmap
        }
        tt["cmap"].tables = [sym]
        buf = io.BytesIO()
        tt.save(buf)
        return buf.getvalue()
    finally:
        tt.close()


def _build_nonsymbolic_pdf(font_bytes: bytes, dest: Path) -> None:
    """Embed ``font_bytes`` as a non-symbolic WinAnsi simple TrueType."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = PDTrueTypeFont.load(doc, font_bytes, WinAnsiEncoding.INSTANCE)
        res = page.get_resources()
        res.put(
            COSName.get_pdf_name("Font"),
            COSName.get_pdf_name("F1"),
            font.get_cos_object(),
        )
        page.set_resources(res)
        doc.save(str(dest))
    finally:
        doc.close()


def _build_symbolic_pdf(font_bytes: bytes, dest: Path) -> None:
    """Embed ``font_bytes`` as a symbolic TrueType with no /Encoding.

    Sets /Flags Symbolic and removes /Encoding so the code->GID path takes the
    symbolic branch (direct (3,0) cmap + ``0xF0xx`` fallback).
    """
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        font = PDTrueTypeFont.load(doc, font_bytes)
        descriptor = font.get_font_descriptor()
        descriptor.set_flags(_FLAG_SYMBOLIC)
        font.get_cos_object().set_item(COSName.get_pdf_name("Encoding"), None)
        res = page.get_resources()
        res.put(
            COSName.get_pdf_name("Font"),
            COSName.get_pdf_name("F1"),
            font.get_cos_object(),
        )
        page.set_resources(res)
        doc.save(str(dest))
    finally:
        doc.close()


def _py_ttf_lines(ttf_path: Path) -> str:
    """Reconstruct ``CmapLookupProbe ttf`` output from pypdfbox.

    Builds the native :class:`CmapTable` from the font's raw ``cmap`` bytes and
    walks ``get_subtable`` / ``get_glyph_id`` for each priority pair, then the
    priority Unicode resolver (``get_unicode_cmap_subtable`` /
    ``get_unicode_cmap_lookup``).
    """
    lines: list[str] = []
    ttf = TrueTypeFont.from_bytes(ttf_path.read_bytes())
    try:
        num_glyphs = ttf.get_number_of_glyphs()
        raw = ttf.get_table_bytes("cmap")
        assert raw is not None

        class _Font:
            def get_number_of_glyphs(self) -> int:
                return num_glyphs

        cmap = CmapTable()
        cmap.read(_Font(), MemoryTTFDataStream(raw))
        for plat, enc in _PAIRS:
            sub = cmap.get_subtable(plat, enc)
            if sub is None:
                lines.append(f"SUBTABLE\t{plat}\t{enc}\tNONE\t-")
                continue
            lines.append(
                f"SUBTABLE\t{plat}\t{enc}\t"
                f"{sub.get_platform_id()}\t{sub.get_platform_encoding_id()}"
            )
            for cp in _CODEPOINTS:
                lines.append(f"GID\t{plat}\t{enc}\t{cp}\t{sub.get_glyph_id(cp)}")
        uni = ttf.get_unicode_cmap_subtable()
        if uni is None:
            lines.append("UNICODE\tNONE\t-")
        else:
            lines.append(
                f"UNICODE\t{uni.get_platform_id()}\t{uni.get_platform_encoding_id()}"
            )
            look = ttf.get_unicode_cmap_lookup()
            assert look is not None
            for cp in _CODEPOINTS:
                lines.append(f"UGID\t{cp}\t{look.get_glyph_id(cp)}")
    finally:
        ttf.close()
    return "\n".join(lines) + "\n"


def _py_pdf_lines(pdf_path: Path) -> str:
    """Reconstruct ``CmapLookupProbe pdf`` output from pypdfbox."""
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
                if not isinstance(font, PDTrueTypeFont):
                    continue
                key = name.name if hasattr(name, "name") else str(name)
                descriptor = font.get_font_descriptor()
                symbolic = bool(descriptor.is_symbolic()) if descriptor else False
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{font.get_name()}\t"
                    f"{str(symbolic).lower()}"
                )
                for code in range(256):
                    try:
                        gid = font.code_to_gid(code)
                    except Exception:
                        gid = -1
                    lines.append(f"CGID\t{code}\t{gid}")
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


def _assert_parity(java: str, py: str, label: str) -> None:
    j = java.splitlines()
    p = py.splitlines()
    assert len(j) == len(p), (
        f"line-count mismatch for {label}: java={len(j)} py={len(p)}\n"
        f"first java: {j[:3]}\nfirst py:   {p[:3]}"
    )
    diffs = [
        f"  line {i}: java={a!r} py={b!r}"
        for i, (a, b) in enumerate(zip(j, p, strict=True))
        if a != b
    ]
    assert not diffs, f"cmap parity broken for {label}:\n" + "\n".join(diffs[:40])


@requires_oracle
@pytest.mark.parametrize(
    "ttf_name",
    ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"],
)
def test_cmap_subtable_selection_and_gid_matches_pdfbox(ttf_name: str) -> None:
    """Native ``CmapTable.get_subtable`` selection (platform/encoding) and
    ``CmapSubtable.get_glyph_id`` per codepoint, plus the priority Unicode
    resolver, must match Apache PDFBox 3.0.7 for bundled fonts carrying
    format-4 / format-6 / format-12 subtables.
    """
    ttf_path = _TTF_DIR / ttf_name
    assert ttf_path.is_file(), f"missing bundled font: {ttf_path}"
    java = run_probe_text("CmapLookupProbe", "ttf", str(ttf_path))
    py = _py_ttf_lines(ttf_path)
    _assert_parity(java, py, f"ttf:{ttf_name}")


@requires_oracle
def test_symbol_cmap_30_selection_and_f0xx_fallback_matches_pdfbox(
    tmp_path: Path,
) -> None:
    """A (3,0) Windows-Symbol format-4 cmap must be selected over the absent
    Unicode subtables, and ``get_glyph_id(0xF0xx)`` must resolve to the symbol
    glyphs exactly as PDFBox does (the symbolic-font priority case).
    """
    djv = (_TTF_DIR / "DejaVuSans.ttf").read_bytes()
    sym_path = tmp_path / "Sym30.ttf"
    sym_path.write_bytes(_make_symbol_font(djv))
    java = run_probe_text("CmapLookupProbe", "ttf", str(sym_path))
    py = _py_ttf_lines(sym_path)
    _assert_parity(java, py, "ttf:Sym30")


@requires_oracle
def test_nonsymbolic_embedded_code_to_gid_matches_pdfbox(tmp_path: Path) -> None:
    """Non-symbolic WinAnsi simple-TrueType ``code_to_gid(code)`` (the
    /Encoding glyph-name -> Unicode -> (3,1) cmap path) must match PDFBox's
    ``codeToGID`` for codes 0..255.
    """
    djv = (_TTF_DIR / "DejaVuSans.ttf").read_bytes()
    pdf_path = tmp_path / "nonsym.pdf"
    _build_nonsymbolic_pdf(djv, pdf_path)
    java = run_probe_text("CmapLookupProbe", "pdf", str(pdf_path))
    py = _py_pdf_lines(pdf_path)
    _assert_parity(java, py, "pdf:nonsymbolic")


@requires_oracle
def test_symbolic_embedded_code_to_gid_matches_pdfbox(tmp_path: Path) -> None:
    """Symbolic (3,0)-cmap simple-TrueType ``code_to_gid(code)`` (direct (3,0)
    lookup + ``0xF0xx`` fallback) must match PDFBox's ``codeToGID`` for codes
    0..255.
    """
    djv = (_TTF_DIR / "DejaVuSans.ttf").read_bytes()
    sym_bytes = _make_symbol_font(djv)
    pdf_path = tmp_path / "sym.pdf"
    _build_symbolic_pdf(sym_bytes, pdf_path)
    java = run_probe_text("CmapLookupProbe", "pdf", str(pdf_path))
    py = _py_pdf_lines(pdf_path)
    _assert_parity(java, py, "pdf:symbolic")
