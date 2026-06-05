"""Live PDFBox differential parity for the PARENT ``PDType0Font`` WRITE side.

Complement of ``test_type0_read_width_oracle`` (which drives the decode + width
read surface). Here we pin the encode roundtrip:

    * ``encode(str)``            — codepoint -> descendant byte sequence (hex)
    * ``get_width(code)``        — per-codepoint advance after encode
    * ``get_string_width(str)``  — total advance for a multi-codepoint sample

The sample codepoints are harvested from the font's own ``/ToUnicode`` CMap so
the characters are ones the font actually covers (otherwise every font would
just substitute / error on encode). For a symbolic subset CIDFontType2 with only
a ``(3,0)`` Microsoft-symbol cmap — or no embedded cmap at all — this exercises
the symbol-cmap / ``/ToUnicode`` fallback in ``PDCIDFontType2.encode`` that the
read path never touches.

The canonical reproducer is ``eu-001.pdf``'s ``JMGKCC+Symbol`` font: PDFBox
encodes U+2022 (bullet) to CID ``0x78`` with advance 459, where the pre-fix
pypdfbox emitted the raw Unicode codepoint ``0x2022`` with advance 1000 (the
wave-1490 / DEFERRED.md reproducer).

The oracle output is produced by ``oracle/probes/Type0EncodeWidthProbe.java``;
the Python side reconstructs the identical line format so a divergence shows up
as a single differing line.

NOTE on the documented leniency divergence: pypdfbox keeps ``encode(str)``'s
lenient ``.notdef`` (CID 0) substitution for genuinely unencodable glyphs
(permanent intentional divergence, CHANGES.md). Every codepoint sampled here is
one the font CAN encode (harvested from ``/ToUnicode``), so the encoded bytes
match upstream exactly — the leniency boundary is not in play.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures"

# Fixtures carrying a Type0 font. eu-001.pdf is the symbolic-subset reproducer
# (JMGKCC+Symbol: embedded /FontFile2 with no cmap table); the others exercise
# the ordinary embedded-cmap encode path so the probe covers both branches.
_FIXTURES_REL = [
    "text/input/eu-001.pdf",
    "multipdf/PDFBOX-4417-001031.pdf",
    "pdfwriter/unencrypted.pdf",
]


def _fmt(v: float) -> str:
    """Match the Java probe's ``String.format(Locale.ROOT, "%.4f", ...)``."""
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _hex(b: bytes) -> str:
    return b.hex().upper()


def _hex_utf16(s: str) -> str:
    out = bytearray()
    for ch in s:
        cp = ord(ch)
        # Mirror the Java probe's char-by-char UTF-16 emission. Codepoints in
        # the BMP are a single char; the probe builds from toUnicode results
        # which (for these fixtures) are all BMP.
        out.append((cp >> 8) & 0xFF)
        out.append(cp & 0xFF)
    return _hex(bytes(out))


def _sample_codepoints(font: PDType0Font) -> list[int]:
    """Mirror ``Type0EncodeWidthProbe.sampleCodepoints``.

    Harvest up to 8 distinct unicode codepoints the font can decode by walking
    low CIDs through ``to_unicode`` (Identity-H: code == CID). Skips .notdef and
    whitespace-only mappings.
    """
    out: list[int] = []
    code = 1
    while code < 65535 and len(out) < 8:
        try:
            u = font.to_unicode(code)
        except Exception:
            u = None
        code += 1
        if not u:
            continue
        cp = ord(u[0])
        if chr(cp).isspace():
            continue
        if cp not in out:
            out.append(cp)
    return out


def _first_code(font: PDType0Font, ch: str) -> int:
    """Encode a single char and fold the bytes into an integer code (-1 on err)."""
    try:
        enc = font.encode(ch)
    except Exception:
        return -1
    code = 0
    for b in enc:
        code = (code << 8) | (b & 0xFF)
    return code


def _py_output(pdf_path: Path) -> str:
    """Reconstruct the Type0EncodeWidthProbe output from pypdfbox, line-for-line."""
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
                lines.append(f"FONT\t{page_index}\t{key}\t{font.get_name()}")

                cps = _sample_codepoints(font)
                sb: list[str] = []
                for cp in cps:
                    ch = chr(cp)
                    sb.append(ch)
                    try:
                        enc_hex = _hex(font.encode(ch))
                    except Exception:
                        enc_hex = "ERR"
                    code = _first_code(font, ch)
                    if code < 0:
                        w = "ERR"
                    else:
                        try:
                            w = _fmt(font.get_width(code))
                        except Exception:
                            w = "ERR"
                    lines.append(
                        f"CHENC\t{page_index}\t{key}\t{cp}\t{enc_hex}\t{w}"
                    )
                sample = "".join(sb)
                try:
                    encoded_hex = _hex(font.encode(sample))
                except Exception:
                    encoded_hex = "ERR"
                try:
                    sw = _fmt(font.get_string_width(sample))
                except Exception:
                    sw = "ERR"
                lines.append(
                    f"ENC\t{page_index}\t{key}\t{_hex_utf16(sample)}\t"
                    f"{encoded_hex}\t{sw}"
                )
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


@requires_oracle
@pytest.mark.parametrize("fixture_rel", _FIXTURES_REL)
def test_type0_encode_width_matches_pdfbox(fixture_rel: str) -> None:
    """Every parent ``PDType0Font`` encode + getStringWidth must match Apache
    PDFBox exactly for codepoints the font can encode.

    Drives the write side: the codepoint -> descendant byte sequence resolution
    (embedded TTF unicode cmap, with the symbolic / ``/ToUnicode`` fallback) and
    the per-codepoint + whole-string advance. No divergence is tolerated.
    """
    pdf_path = _FIXTURES / fixture_rel
    assert pdf_path.is_file(), f"missing fixture: {pdf_path}"
    java = run_probe_text("Type0EncodeWidthProbe", str(pdf_path)).splitlines()
    py = _py_output(pdf_path).splitlines()
    assert len(java) == len(py), (
        f"line-count mismatch for {fixture_rel}: java={len(java)} py={len(py)}\n"
        f"java[:10]={java[:10]}\npy[:10]={py[:10]}"
    )
    diffs = [
        f"  line {i}: java={j!r} py={p!r}"
        for i, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, (
        f"PDType0Font encode/width parity broken for {fixture_rel}:\n"
        + "\n".join(diffs[:40])
    )


@requires_oracle
def test_eu001_symbol_bullet_encodes_to_cid_0x78() -> None:
    """Pin the canonical wave-1490 reproducer: eu-001's JMGKCC+Symbol font
    encodes U+2022 (bullet) to CID 0x78 with advance 459 — the documented
    PDFBox value (pre-fix pypdfbox emitted raw 0x2022 / advance 1000).
    """
    pdf_path = _FIXTURES / "text/input/eu-001.pdf"
    out = run_probe_text("Type0EncodeWidthProbe", str(pdf_path))
    # The probe line for the bullet codepoint (8226 == 0x2022).
    bullet_lines = [
        ln for ln in out.splitlines() if ln.startswith("CHENC\t") and "\t8226\t" in ln
    ]
    assert bullet_lines, f"no bullet CHENC line in probe output:\n{out}"
    # ... CHENC \t page \t key \t 8226 \t 0078 \t 459.0000
    parts = bullet_lines[0].split("\t")
    assert parts[4] == "0078", f"expected PDFBox encode 0078, got {parts[4]}"
    assert parts[5] == "459.0000", f"expected PDFBox width 459, got {parts[5]}"

    # And pypdfbox matches.
    doc = PDDocument.load(pdf_path)
    try:
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                font = res.get_font(name)
                if not isinstance(font, PDType0Font):
                    continue
                bullet = chr(0x2022)
                assert font.encode(bullet) == b"\x00\x78"
                assert font.get_string_width(bullet) == 459.0
    finally:
        doc.close()
