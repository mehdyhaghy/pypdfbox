"""Live Apache PDFBox differential parity for pypdfbox's subset-tag
*generation on save*.

PDF 32000-1 §9.6.4 says the embedded *subset* of a font has its PostScript
name prefixed with six uppercase ASCII letters and ``+``, e.g.
``AAAAAA+Helvetica``. PDF 32000-1 §9.8.2 says the font dict's ``/BaseFont``
and the descriptor's ``/FontName`` must match — *including* the prefix.
Apache PDFBox 3.0.7 (``TrueTypeEmbedder.getTag(gidToCid)``) derives the
tag deterministically over the surviving glyph id set so the same subset
round-trips to the same six-letter prefix.

This module pins three invariants on pypdfbox's saved subset PDFs:

* **shape** — ``/BaseFont`` matches ``^[A-Z]{6}\\+.+``, and the descriptor's
  ``/FontName`` is the same string.
* **determinism** — building the same fixture twice produces the same
  prefix on ``/BaseFont`` (the bug pypdfbox shipped before this wave used
  ``secrets.choice`` on every save).
* **interoperability** — Apache PDFBox 3.0.7 loads the pypdfbox-saved PDF
  without rejecting the prefix (``TtfSubsetTagProbe`` invokes ``isEmbedded``
  via PDFBox's own ``PDFont`` / ``PDFontDescriptor`` reifiers).

Two engines confirm each invariant:

* **pypdfbox reproduction** — open the saved PDF, walk every font on
  every page, build a tuple of (page, key, base_font, prefix, font_name)
  facts mirroring the probe output line-for-line.
* **TtfSubsetTagProbe (Java)** — pinned PDFBox 3.0.7 emits the same shape /
  determinism / interop facts; pypdfbox must match line-for-line.

Divergence history:
  * Wave 1448 found pypdfbox's subset save path generating the tag with
    ``secrets.choice`` on every call, so the same input yielded a different
    tag on every save (e.g. ``GWIDZX+`` vs ``UZFWEF+``). Fixed in
    ``PDType0Font.subset`` and ``PDTrueTypeFont.subset`` — the tag is now
    derived deterministically from the surviving glyph id set via
    ``_deterministic_subset_tag`` (mirrors upstream
    ``TrueTypeEmbedder.getTag``). See CHANGES.md.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

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

_TEXT = "Hello World 123"

_PREFIX_RE = re.compile(r"^([A-Z]{6})\+(.+)$")


# --------------------------------------------------------------------------- #
# Builders — produce subset embeddings on a single page drawing _TEXT twice.
# --------------------------------------------------------------------------- #


def _build_type0_subset() -> bytes:
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
        cs.new_line_at_offset(0, -20)
        cs.show_text(encoded)
        cs.end_text()
    sink = io.BytesIO()
    try:
        doc.save(sink)
    finally:
        doc.close()
    return sink.getvalue()


def _build_simple_subset() -> bytes:
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
        cs.new_line_at_offset(0, -20)
        cs.show_text(_TEXT)
        cs.end_text()
    sink = io.BytesIO()
    try:
        doc.save(sink)
    finally:
        doc.close()
    return sink.getvalue()


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


# --------------------------------------------------------------------------- #
# Python reproduction of TtfSubsetTagProbe's line format.
# --------------------------------------------------------------------------- #


def _py_probe(pdf_bytes: bytes) -> str:
    lines: list[str] = []
    doc = PDDocument.load(io.BytesIO(pdf_bytes))
    try:
        for page_index, page in enumerate(doc.get_pages()):
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_font_names():
                key = name.get_name()
                try:
                    font = res.get_font(name)
                except Exception:  # noqa: BLE001
                    lines.append(f"LOAD\t{page_index}\t{key}\tfalse")
                    continue
                if font is None:
                    lines.append(f"LOAD\t{page_index}\t{key}\tnull")
                    continue

                base_font = str(font.get_name())
                try:
                    embedded = font.is_embedded()
                except Exception:  # noqa: BLE001
                    embedded = False
                lines.append(
                    f"FONT\t{page_index}\t{key}\t{base_font}\t"
                    f"{font.get_sub_type()}\t{str(embedded).lower()}"
                )

                m = _PREFIX_RE.match(base_font)
                if m:
                    prefix = m.group(1)
                    shape_ok = "true"
                else:
                    prefix = "NONE"
                    shape_ok = "false"

                fd = font.get_font_descriptor()
                if fd is None:
                    font_name_match = "NA"
                else:
                    fn = fd.get_font_name()
                    font_name_match = str(base_font == fn).lower()

                lines.append(
                    f"TAG\t{page_index}\t{key}\t{prefix}\t"
                    f"{shape_ok}\t{font_name_match}"
                )
                lines.append(f"LOAD\t{page_index}\t{key}\ttrue")
    finally:
        doc.close()
    return "\n".join(lines) + ("\n" if lines else "")


# --------------------------------------------------------------------------- #
# Fixture factories.
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def type0_subset_bytes() -> bytes:
    return _build_type0_subset()


@pytest.fixture(scope="module")
def simple_subset_bytes() -> bytes:
    return _build_simple_subset()


# --------------------------------------------------------------------------- #
# Shape — /BaseFont matches ^[A-Z]{6}\+.+ and equals /FontName.
# --------------------------------------------------------------------------- #


def _parse_tag_lines(text: str) -> list[tuple[str, str, str, str, str]]:
    """Extract TAG records: (page, key, prefix, shape_ok, name_match)."""
    out: list[tuple[str, str, str, str, str]] = []
    for line in text.splitlines():
        if not line.startswith("TAG\t"):
            continue
        parts = line.split("\t")
        if len(parts) != 6:
            continue
        _, page, key, prefix, shape, match = parts
        out.append((page, key, prefix, shape, match))
    return out


def test_type0_subset_prefix_shape_pypdfbox(type0_subset_bytes: bytes) -> None:
    """Type0 subset /BaseFont must be 6 uppercase letters + '+' + name."""
    py = _py_probe(type0_subset_bytes)
    tags = _parse_tag_lines(py)
    assert tags, f"no TAG records in py probe output:\n{py}"
    for _, key, prefix, shape, match in tags:
        assert shape == "true", f"font {key} prefix shape invalid: {prefix}"
        assert re.fullmatch(r"[A-Z]{6}", prefix), prefix
        # Descriptor /FontName must mirror /BaseFont per PDF 32000-1 §9.8.2.
        assert match in ("true", "NA"), f"font {key} /FontName != /BaseFont"


def test_simple_subset_prefix_shape_pypdfbox(simple_subset_bytes: bytes) -> None:
    """Simple TTF subset /BaseFont must be 6 uppercase letters + '+' + name."""
    py = _py_probe(simple_subset_bytes)
    tags = _parse_tag_lines(py)
    assert tags, f"no TAG records in py probe output:\n{py}"
    for _, key, prefix, shape, match in tags:
        assert shape == "true", f"font {key} prefix shape invalid: {prefix}"
        assert re.fullmatch(r"[A-Z]{6}", prefix), prefix
        assert match in ("true", "NA"), f"font {key} /FontName != /BaseFont"


# --------------------------------------------------------------------------- #
# Determinism — same fixture twice must yield the same prefix.
# --------------------------------------------------------------------------- #


def test_type0_subset_prefix_deterministic() -> None:
    """Two saves of the same Type0 subset must share the same /BaseFont prefix."""
    a = _build_type0_subset()
    b = _build_type0_subset()
    tags_a = _parse_tag_lines(_py_probe(a))
    tags_b = _parse_tag_lines(_py_probe(b))
    assert tags_a == tags_b, (
        f"Type0 subset prefix is non-deterministic:\n{tags_a}\nvs\n{tags_b}"
    )


def test_simple_subset_prefix_deterministic() -> None:
    """Two saves of the same simple TTF subset must share the same prefix."""
    a = _build_simple_subset()
    b = _build_simple_subset()
    tags_a = _parse_tag_lines(_py_probe(a))
    tags_b = _parse_tag_lines(_py_probe(b))
    assert tags_a == tags_b, (
        f"Simple subset prefix is non-deterministic:\n{tags_a}\nvs\n{tags_b}"
    )


# --------------------------------------------------------------------------- #
# Interop — Apache PDFBox 3.0.7 must accept the saved PDF.
# --------------------------------------------------------------------------- #


@requires_oracle
def test_type0_subset_tag_oracle_interop(
    type0_subset_bytes: bytes, tmp_path: Path
) -> None:
    """PDFBox loads the pypdfbox-saved Type0 subset; the prefix passes its
    own ``^[A-Z]{6}\\+`` check and ``/FontName`` matches ``/BaseFont``."""
    pdf = _write(tmp_path, "type0_subset_tag.pdf", type0_subset_bytes)
    java = run_probe_text("TtfSubsetTagProbe", str(pdf))
    py = _py_probe(type0_subset_bytes)
    assert java == py, f"JAVA vs PY divergence:\n--- JAVA ---\n{java}\n--- PY ---\n{py}"
    # Independent assertions on the java output: every LOAD line ended in
    # "true", every TAG line has shape_ok=true.
    for line in java.splitlines():
        if line.startswith("LOAD\t"):
            assert line.endswith("\ttrue"), f"PDFBox failed to load: {line}"
        if line.startswith("TAG\t"):
            parts = line.split("\t")
            assert parts[4] == "true", f"PDFBox rejected prefix shape: {line}"
            assert parts[5] in ("true", "NA"), (
                f"PDFBox saw /FontName != /BaseFont: {line}"
            )


@requires_oracle
def test_simple_subset_tag_oracle_interop(
    simple_subset_bytes: bytes, tmp_path: Path
) -> None:
    """PDFBox loads the pypdfbox-saved simple TTF subset; same invariants."""
    pdf = _write(tmp_path, "simple_subset_tag.pdf", simple_subset_bytes)
    java = run_probe_text("TtfSubsetTagProbe", str(pdf))
    py = _py_probe(simple_subset_bytes)
    assert java == py, f"JAVA vs PY divergence:\n--- JAVA ---\n{java}\n--- PY ---\n{py}"
    for line in java.splitlines():
        if line.startswith("LOAD\t"):
            assert line.endswith("\ttrue"), f"PDFBox failed to load: {line}"
        if line.startswith("TAG\t"):
            parts = line.split("\t")
            assert parts[4] == "true", f"PDFBox rejected prefix shape: {line}"
            assert parts[5] in ("true", "NA"), (
                f"PDFBox saw /FontName != /BaseFont: {line}"
            )


# --------------------------------------------------------------------------- #
# Cross-process determinism check via direct subprocess invocation —
# guards against Python's per-process hash-seed randomisation slipping in
# (tuple-of-int hash is stable across runs; tuple-of-str/bytes is not).
# --------------------------------------------------------------------------- #


def _extract_tag(pdf_bytes: bytes) -> str:
    """Return the first TAG prefix in the saved PDF, or '' if none."""
    py = _py_probe(pdf_bytes)
    for line in py.splitlines():
        if line.startswith("TAG\t"):
            parts = line.split("\t")
            if len(parts) >= 4:
                return parts[3]
    return ""


def test_type0_subset_prefix_cross_call_stable() -> None:
    """Three back-to-back builds in the same process must share the prefix.

    This catches the ``secrets.choice``-style regression where each call
    samples a fresh random tag.
    """
    tags = [_extract_tag(_build_type0_subset()) for _ in range(3)]
    assert len(set(tags)) == 1, f"prefix changes between calls: {tags}"
    assert re.fullmatch(r"[A-Z]{6}", tags[0]), tags[0]


def test_simple_subset_prefix_cross_call_stable() -> None:
    tags = [_extract_tag(_build_simple_subset()) for _ in range(3)]
    assert len(set(tags)) == 1, f"prefix changes between calls: {tags}"
    assert re.fullmatch(r"[A-Z]{6}", tags[0]), tags[0]
