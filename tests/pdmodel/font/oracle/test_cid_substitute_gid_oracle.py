"""Live PDFBox differential parity for the NON-EMBEDDED CIDFontType2
model-layer contract — the ``/FontFile2``-less substitute-font path.

Wave 1488. When a Type0/CIDFontType2's descriptor carries no embedded font
program (no ``/FontFile2`` / ``/FontFile3`` / ``/FontFile``), upstream
``PDCIDFontType2.codeToGID`` resolves the GID through a *substitute* TrueType
font located via the platform ``FontMapper`` (PDFBOX-1422 / PDFBOX-2560 /
PDFBOX-5612): it round-trips the code through ``/ToUnicode`` (or the parent
CMap) into a unicode codepoint, then asks the substitute font's cmap for the
glyph. **That GID is machine-dependent** — it depends on which TrueType the
host OS (or the bundled fallback) happens to offer for the requested name. The
oracle run on this dev box logs e.g. ``Using fallback font LiberationSans for
CID-keyed TrueType font DejaVuSans`` and resolves GIDs against *that* font.

pypdfbox deliberately keeps the substitute-font GID resolution in the renderer
(see ``PDCIDFontType2.cid_to_gid``'s non-embedded fall-through, which returns
the identity ``cid`` because the model layer has no parsed program), so the
substitute GID is **not** a deterministic model-layer differential surface and
is intentionally NOT pinned here. See CHANGES.md.

What this oracle pins is the machine-independent contract for the same fixture:

* ``isEmbedded() == false`` once ``/FontFile2`` is stripped,
* the descriptor exposes no embedded program (no FontFile2/3/Font),
* ``/CIDToGIDMap`` kind + ``/DW`` default width are read identically,
* ``PDType0Font.codeToCID(code)`` (driven by the parent encoding CMap +
  ``/ToUnicode`` round-trip — independent of any substitute program), and
* ``PDType0Font.getWidth(code)`` (the ``/W`` array displacement — independent
  of the substitute glyph's own hmtx advance).

The fixture is hand-authored: embed ``DejaVuSans.ttf`` (subset OFF) as a
Type0/CIDFontType2 under Identity-H with a ``/ToUnicode`` CMap, then *strip*
the descriptor's ``/FontFile2`` so the saved PDF carries no embedded program
— exactly the ``/FontFile2``-less CID document the substitute path is for.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

_FONT = (
    Path(__file__).resolve().parents[4]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "DejaVuSans.ttf"
)

# Identity-H => the on-wire 2-byte code IS the CID. Codes we exercise:
#   0   -> .notdef,
#   3,5,7,9 -> real CIDs with non-zero /W advances,
#   65535   -> a high CID beyond any real glyph (still identity through codeToCID
#              under Identity-H; width falls back to /DW).
_CONTENT_CIDS = (3, 5, 7, 9)
_PROBE_CODES = (0, 3, 5, 7, 9, 65535)


def _build(out: Path) -> Path:
    """Embed ``DejaVuSans.ttf`` (subset OFF) as a Type0/CIDFontType2 under
    Identity-H, then strip the descriptor's ``/FontFile2`` so the saved PDF
    has NO embedded program — the non-embedded substitute-font path."""
    doc = PDDocument()
    try:
        while doc.get_number_of_pages() > 0:
            doc.remove_page(0)
        page = PDPage(PDRectangle(0.0, 0.0, 200.0, 60.0))
        doc.add_page(page)

        font = PDType0Font.load(doc, str(_FONT), embed_subset=False)
        descendant = font.get_descendant_font()
        assert isinstance(descendant, PDCIDFontType2)

        # Strip the embedded program → /FontFile2-less descriptor.
        fd = descendant.get_font_descriptor()
        assert fd is not None
        assert fd.get_font_file2() is not None  # present before strip
        fd.set_font_file2(None)

        res = PDResources()
        res.put(COSName.get_pdf_name("F1"), font)
        page.set_resources(res)

        codes = b"".join(struct.pack(">H", c) for c in _CONTENT_CIDS)
        cs = COSStream()
        cs.set_data(
            b"BT\n/F1 24 Tf\n10 20 Td\n<%s> Tj\nET\n"
            % codes.hex().encode("ascii")
        )
        page.set_contents(cs)
        doc.save(str(out))
    finally:
        doc.close()
    return out


def _reload(pdf_path: Path) -> tuple[PDDocument, PDType0Font, PDCIDFontType2]:
    doc = PDDocument.load(pdf_path)
    for page in doc.get_pages():
        res = page.get_resources()
        if res is None:
            continue
        for name in res.get_font_names():
            font = res.get_font(name)
            if not isinstance(font, PDType0Font):
                continue
            descendant = font.get_descendant_font()
            if isinstance(descendant, PDCIDFontType2):
                return doc, font, descendant
    doc.close()
    raise AssertionError("no CIDFontType2 descendant in fixture")


# ---------------------------------------------------------------------------
# fixture proof: the saved PDF really is /FontFile2-less and non-embedded
# ---------------------------------------------------------------------------


def test_fixture_is_non_embedded(tmp_path: Path) -> None:
    fixture = _build(tmp_path / "cid_substitute.pdf")
    assert b"FontFile2" not in fixture.read_bytes()
    doc, font, descendant = _reload(fixture)
    try:
        assert not font.is_embedded()
        assert not descendant.is_embedded()
        assert descendant.get_true_type_font() is None
        fd = descendant.get_font_descriptor()
        assert fd is not None
        assert fd.get_font_file2() is None
        assert fd.get_font_file3() is None
        assert fd.get_font_file() is None
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# differential: the machine-independent contract matches PDFBox exactly
# ---------------------------------------------------------------------------


@requires_oracle
def test_non_embedded_contract_matches_pdfbox(tmp_path: Path) -> None:
    """The deterministic, substitute-font-independent fields the model layer
    exposes for a ``/FontFile2``-less CIDFontType2 must match Apache PDFBox:
    ``isEmbedded``, the descriptor's lack of an embedded program, the
    ``/CIDToGIDMap`` kind, the ``/DW`` default width, and per-code
    ``codeToCID`` + ``getWidth``. The substitute GID itself is deliberately
    NOT compared (it is platform-FontMapper dependent upstream — see module
    docstring / CHANGES.md)."""
    fixture = _build(tmp_path / "cid_substitute.pdf")

    args = [
        "CidSubstituteGidProbe",
        str(fixture),
        *(str(c) for c in _PROBE_CODES),
    ]
    java = run_probe_text(*args).splitlines()

    head = java[0].split("\t")
    assert head[0] == "HEAD"
    (
        _tag,
        j_embedded,
        j_subtype,
        j_kind,
        j_ff2,
        j_ff3,
        j_ff,
        j_dw,
    ) = head
    assert j_embedded == "false"
    assert j_subtype == "CIDFontType2"
    assert j_ff2 == "false"
    assert j_ff3 == "false"
    assert j_ff == "false"

    doc, font, descendant = _reload(fixture)
    try:
        assert not font.is_embedded()
        # /CIDToGIDMap kind reported identically.
        if descendant.is_identity_cid_to_gid_map():
            assert j_kind in ("name:Identity", "Identity(absent)")
        else:
            assert j_kind == "stream"
        # /DW default width.
        assert float(j_dw) == pytest.approx(descendant.get_default_width())

        java_codes: dict[int, tuple[str, str]] = {}
        for line in java[1:]:
            tag, code_s, cid_s, width_s = line.split("\t")
            assert tag == "CODE"
            java_codes[int(code_s)] = (cid_s, width_s)

        for code in _PROBE_CODES:
            j_cid, j_width = java_codes[code]
            assert font.code_to_cid(code) == int(j_cid), (
                f"code {code}: codeToCID diverges"
            )
            assert font.get_width(code) == pytest.approx(
                float(j_width), rel=1e-4
            ), f"code {code}: getWidth diverges"
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# value pin (no oracle): documents the renderer-delegated GID divergence
# ---------------------------------------------------------------------------


def test_non_embedded_model_layer_gid_is_identity(tmp_path: Path) -> None:
    """Pin pypdfbox's *documented divergence*: with no embedded program the
    model-layer ``cid_to_gid`` / ``code_to_gid`` fall through to the identity
    ``cid`` (the substitute-font GID is the renderer's job). This is NOT
    PDFBox's value — upstream returns the substitute font's GID — and the
    divergence is recorded in CHANGES.md. The test exists so a future change
    to the fall-through is a conscious one."""
    fixture = _build(tmp_path / "cid_substitute.pdf")
    doc, _font, descendant = _reload(fixture)
    try:
        assert not descendant.is_embedded()
        for cid in (0, 3, 5, 7, 9, 65535):
            assert descendant.cid_to_gid(cid) == cid
            assert descendant.code_to_gid(cid) == cid
        # Negative CID is still clamped to 0 (defensive guard, embedded or not).
        assert descendant.cid_to_gid(-1) == 0
    finally:
        doc.close()
