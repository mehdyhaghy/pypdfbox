"""Wave-1341 coverage-boost tests for
:mod:`pypdfbox.pdmodel.font.pd_type1_font`.

Targets the residual uncovered branches:

* ``_get_type1_font`` returning ``None`` when descriptor lacks
  ``/FontFile`` (lines 135-136);
* ``get_glyph_width`` Standard-14 fallback via the typed encoding
  (line 198);
* ``get_glyph_path`` Standard-14 fallback paths — typed encoding
  hit (line 341), Standard-encoding default (line 360), ``.notdef``
  short-circuit (line 362);
* ``get_height`` AFM path when the font has no ``/Encoding`` (line 524);
* ``generate_bounding_box`` falling through to the embedded program's
  ``/FontBBox`` (lines 749-753);
* ``get_font_matrix`` using the program's matrix when present
  (lines 771-774);
* ``repair_length1`` short-buffer + brute-force second pass branches
  (lines 807, 811);
* ``read_encoding_from_font`` surfacing an embedded program's encoding
  via :class:`Type1Encoding` (lines 911-916).
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.fontbox.type1.type1_font import Type1Font
from pypdfbox.pdmodel.font import PDFontDescriptor, PDType1Font

_BASE_FONT = COSName.get_pdf_name("BaseFont")
_ENCODING = COSName.get_pdf_name("Encoding")
_WIN_ANSI = COSName.get_pdf_name("WinAnsiEncoding")


class _FakeT1Program(Type1Font):
    """Minimal Type1Font subclass that overrides every accessor pd_type1_font
    reads. Subclassing keeps the ``isinstance(self._t1, Type1Font)`` guard
    in :meth:`_get_type1_font` happy without a real PostScript parse."""

    def __init__(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        matrix: list[float] | None = None,
        encoding: dict[int, str] | None = None,
    ) -> None:
        super().__init__()
        self._bbox_override = bbox
        self._matrix_override = matrix
        self._encoding_override = encoding or {}

    def get_font_bbox(self) -> tuple[float, float, float, float] | None:
        return self._bbox_override

    def get_font_matrix(self) -> list[float] | None:  # type: ignore[override]
        return self._matrix_override

    def get_encoding(self) -> dict[int, str]:
        return self._encoding_override

    def get_path(self, name: str) -> list:  # type: ignore[override]  # noqa: ARG002
        return []


# ---------- _get_type1_font: descriptor without /FontFile ----------------


def test_get_type1_font_returns_none_when_descriptor_lacks_font_file() -> None:
    """A descriptor present but with no ``/FontFile`` flips the lazy
    cache to ``False`` and returns ``None`` (lines 135-136)."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "MyType1")
    # Attach a descriptor with no /FontFile.
    descriptor = PDFontDescriptor()
    font.set_font_descriptor(descriptor)
    assert font._get_type1_font() is None  # noqa: SLF001
    # Cached sentinel — subsequent call hits the fast path.
    assert font._get_type1_font() is None  # noqa: SLF001


# ---------- get_glyph_width: Standard-14 typed-encoding path -------------


def test_get_glyph_width_uses_typed_encoding_for_standard14_lookup() -> None:
    """A Standard-14 font with an explicit ``/Encoding`` resolves the
    glyph name via the typed encoding (line 198) and returns the AFM
    width."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    font.get_cos_object().set_item(_ENCODING, _WIN_ANSI)
    # Code 0x41 = 'A' under WinAnsiEncoding — Helvetica's AFM advance
    # is 667 (or similar non-zero).
    width = font.get_glyph_width(0x41)
    assert width > 0


# ---------- get_glyph_path: Standard-14 fallback paths ---------------


def test_get_glyph_path_uses_typed_encoding_when_present() -> None:
    """Standard-14 font, no embedded program, with ``/Encoding`` →
    resolves glyph name via the typed encoding (line 341)."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    font.get_cos_object().set_item(_ENCODING, _WIN_ANSI)
    # 'A' under WinAnsiEncoding maps to glyph "A" — Liberation Sans
    # supplies an outline.
    path = font.get_glyph_path(0x41)
    assert isinstance(path, list)


def test_get_glyph_path_uses_standard_encoding_default() -> None:
    """Standard-14 non-Symbol/Zapf font without ``/Encoding`` falls back
    to ``StandardEncoding`` (line 360)."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    # No /Encoding — exercise the StandardEncoding branch.
    path = font.get_glyph_path(0x41)
    assert isinstance(path, list)


def test_get_glyph_path_returns_empty_for_notdef_code() -> None:
    """When the resolved glyph name is ``.notdef`` the helper returns
    ``[]`` without going to the AFM (line 362)."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    # A non-embedded Standard-14 Helvetica defaults to WinAnsiEncoding (the
    # Acrobat default, verified against the live PDFBox oracle), under which
    # control codes 0x00-0x1F are ``.notdef``. Code 0x01 therefore resolves
    # to ``.notdef`` and the helper returns ``[]``.
    path = font.get_glyph_path(0x01)
    assert path == []


def test_get_glyph_path_handles_symbol_font_family() -> None:
    """Standard-14 Symbol font without ``/Encoding`` uses
    ``SymbolEncoding`` (covers the canonical Symbol branch alongside
    the StandardEncoding default)."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Symbol")
    path = font.get_glyph_path(0x41)
    assert isinstance(path, list)


def test_get_glyph_path_handles_zapf_dingbats_family() -> None:
    """Standard-14 ZapfDingbats font without ``/Encoding`` uses
    ``ZapfDingbatsEncoding``."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "ZapfDingbats")
    path = font.get_glyph_path(0x21)
    assert isinstance(path, list)


# ---------- get_height: AFM hit with no /Encoding ------------------------


def test_get_height_returns_afm_height_via_default_encoding() -> None:
    """A Standard-14 font with an AFM resolves the glyph name through its
    default (WinAnsi) encoding and returns the AFM character height.

    Verified against the live PDFBox oracle: Helvetica ``getHeight(0x41)``
    (code 'A') is 718.0, and a ``.notdef`` code (a control code under
    WinAnsi) yields 0.0 because the AFM returns 0 for unknown names."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "Helvetica")
    assert font.get_height(0x41) == 718.0
    # Control codes are .notdef under WinAnsi; the AFM returns 0 for them.
    assert font.get_height(0x01) == 0.0


# ---------- generate_bounding_box from embedded program ------------------


def test_generate_bounding_box_uses_program_when_descriptor_missing_bbox() -> None:
    """Descriptor without /FontBBox + embedded program with bbox →
    bbox from the program (lines 749-753)."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "MyEmbedded")
    descriptor = PDFontDescriptor()
    font.set_font_descriptor(descriptor)
    # Inject a fake program with a font_bbox.
    font.set_font_program(_FakeT1Program(bbox=(-100.0, -200.0, 1000.0, 2000.0)))  # type: ignore[arg-type]
    bbox = font.generate_bounding_box()
    assert bbox is not None
    assert bbox.get_lower_left_x() == -100.0
    assert bbox.get_upper_right_y() == 2000.0


def test_generate_bounding_box_returns_none_when_program_has_no_bbox() -> None:
    """Descriptor without /FontBBox + program without bbox → ``None``
    (line 750-751)."""
    font = PDType1Font()
    font.get_cos_object().set_name(_BASE_FONT, "MyEmbedded")
    descriptor = PDFontDescriptor()
    font.set_font_descriptor(descriptor)
    font.set_font_program(_FakeT1Program(bbox=None))  # type: ignore[arg-type]
    assert font.generate_bounding_box() is None


# ---------- get_font_matrix from program ---------------------------------


def test_get_font_matrix_uses_program_matrix_when_present() -> None:
    """Embedded program's font_matrix wins over the simple-font default
    (lines 771-774)."""
    font = PDType1Font()
    font.set_font_program(  # type: ignore[arg-type]
        _FakeT1Program(matrix=[0.0005, 0.0, 0.0, 0.0005, 0.0, 0.0])
    )
    matrix = font.get_font_matrix()
    assert matrix == [0.0005, 0.0, 0.0, 0.0005, 0.0, 0.0]
    # Result is cached — subsequent calls return the same content.
    assert font.get_font_matrix() == [0.0005, 0.0, 0.0, 0.0005, 0.0, 0.0]


# ---------- repair_length1 short-buffer + brute-force second pass --------


def test_repair_length1_short_buffer_falls_back_to_end() -> None:
    """When the declared ``length1`` already exceeds buffer size minus 4,
    the helper resets the scan to ``len(buf) - 4`` (line 807)."""
    font = PDType1Font()
    # Buffer with a single ``exec`` token near the end + trailing CR.
    buf = b"x" * 16 + b"exec\r" + b"y" * 8
    # length1 far past the buffer — exercises the ``offset > len(buf)-4``
    # branch on line 807.
    repaired = font.repair_length1(buf, 9999)
    # Must point past the ``exec`` + CR.
    assert repaired == buf.index(b"exec") + 4 + 1


def test_repair_length1_brute_force_second_pass() -> None:
    """When the first scan from ``length1 - 4`` finds nothing but a
    second scan from the buffer end does, the helper returns the
    second-pass offset (line 811)."""
    font = PDType1Font()
    pad_head = b"a" * 5
    exec_token = b"exec"
    pad_tail = b"b" * 100
    buf = pad_head + exec_token + pad_tail
    # length1 = 5 → first-pass start offset = max(0, 1) = 1. Backward
    # scan from offset 1 covers positions 0..1 only — never reaches the
    # ``exec`` at offset 5, so the first pass returns 0. That triggers
    # the brute-force second pass starting from ``len(buf) - 4 = 105``,
    # which finds the exec and returns ``5 + 4 = 9``.
    repaired = font.repair_length1(buf, 5)
    assert repaired == len(pad_head) + len(exec_token)


# ---------- read_encoding_from_font: embedded program with /Encoding ----


def test_read_encoding_from_font_returns_type1_encoding_for_program() -> None:
    """Embedded program with a non-empty ``get_encoding()`` map yields
    a :class:`Type1Encoding` — upstream ``readEncodingFromFont`` builds the
    embedded-Type1 branch via ``Type1Encoding.fromFontBox(...)``, not a
    ``BuiltInEncoding`` (verified against the live PDFBox oracle, which
    reports ``Type1Encoding`` for a /FontFile font without an /Encoding
    dict)."""
    from pypdfbox.pdmodel.font.encoding.type1_encoding import Type1Encoding

    font = PDType1Font()
    # No /BaseFont matching a Standard-14, so we skip the AFM branch and
    # hit the program path. Also need is_embedded() True — attach a
    # descriptor + dummy stream so is_embedded() returns True.
    from pypdfbox.cos import COSStream

    descriptor = PDFontDescriptor()
    descriptor.set_font_file(COSStream())
    font.set_font_descriptor(descriptor)
    # Inject a duck-typed program with an encoding map; this also
    # short-circuits ``_get_type1_font`` so the dummy /FontFile bytes
    # never get parsed.
    program_encoding = {0x41: "A", 0x42: "B", 0x43: "C"}
    font.set_font_program(_FakeT1Program(encoding=program_encoding))  # type: ignore[arg-type]
    encoding = font.read_encoding_from_font()
    assert isinstance(encoding, Type1Encoding)
    assert encoding.get_name(0x41) == "A"


def test_read_encoding_from_font_returns_standard_when_program_encoding_empty() -> None:
    """Embedded program with empty ``get_encoding()`` falls through to
    :class:`StandardEncoding` (line 917)."""
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel.font.encoding.standard_encoding import StandardEncoding

    font = PDType1Font()
    descriptor = PDFontDescriptor()
    descriptor.set_font_file(COSStream())
    font.set_font_descriptor(descriptor)
    font.set_font_program(_FakeT1Program(encoding={}))  # type: ignore[arg-type]
    encoding = font.read_encoding_from_font()
    assert encoding is StandardEncoding.INSTANCE
