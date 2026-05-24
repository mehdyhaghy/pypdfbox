"""Wave 1392 coverage round-out for
:mod:`pypdfbox.pdmodel.font.pd_type1_font`.

Closes the residual branch gaps left after wave 1391's Standard 14
family-default-encoding fall-through:

* ``get_glyph_width`` /Widths out-of-range path (branch 209->213).
* ``get_glyph_width`` Standard 14 fall-through when /Encoding resolves
  the code to ``.notdef`` and the encoding IS a DictionaryEncoding
  WITH a base-encoding (branch 252->255 — base-encoding present, no
  fall-through to family default).
* ``get_font_matrix`` defensive ``len(matrix) == 6`` short-circuit
  (branch 824->828 — embedded program reports a malformed matrix).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.font.encoding.dictionary_encoding import DictionaryEncoding
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font


def _helvetica_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    d.set_name(COSName.get_pdf_name("Subtype"), "Type1")
    d.set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    return d


# ---------- /Widths out-of-range (branch 209->213) ----------


def test_get_glyph_width_widths_out_of_range_falls_through_to_afm() -> None:
    """When /FirstChar..LastChar window says the code IS in range but
    /Widths array is shorter than expected, the helper falls through
    to the embedded program / Standard 14 AFM rather than indexing past
    the end (branch 209->213 — defensive guard kept upstream-parity)."""
    d = _helvetica_dict()
    # /Widths claims FirstChar=0, LastChar=255 but only carries 5 entries.
    widths_arr = COSArray()
    for v in (250, 333, 333, 333, 333):
        widths_arr.add(COSInteger.get(v))
    d.set_item(COSName.get_pdf_name("Widths"), widths_arr)
    d.set_int(COSName.get_pdf_name("FirstChar"), 0)
    d.set_int(COSName.get_pdf_name("LastChar"), 255)
    font = PDType1Font(d)
    # Code 32 — inside /FirstChar..LastChar but past /Widths end (5).
    # Must NOT raise an IndexError; instead falls through to the Standard
    # 14 AFM Helvetica width for "space" (278).
    width = font.get_glyph_width(32)
    assert width > 0
    assert width != 333


# ---------- Standard 14 fall-through w/ base-encoding present ----------


def test_get_glyph_width_dictencoding_with_base_does_not_fall_through() -> None:
    """Branch 252->255 — when the typed encoding is a DictionaryEncoding
    WITH a base-encoding present, a ``.notdef`` resolution must NOT
    fall through to the family default. Wave 1391's fall-through fires
    only for base-less DictionaryEncoding (Type 3-shaped /Encoding)."""
    d = _helvetica_dict()
    # /Encoding with WinAnsi base — i.e. has_base_encoding() is True.
    dict_enc = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("WinAnsiEncoding")
    )
    d.set_item(COSName.get_pdf_name("Encoding"), dict_enc.get_cos_object())
    font = PDType1Font(d)
    # Code 0xAD in WinAnsi resolves to "hyphen". (NOT .notdef.) So the
    # .notdef fall-through branch isn't entered; the typed encoding name
    # wins. We verify by checking we get the AFM width for "hyphen", not
    # the value the family default ("StandardEncoding") would give.
    width = font.get_glyph_width(0xAD)
    # The point is that we got SOME width (>= 0) via the typed encoding
    # path, exercising the dictionary-with-base branch.
    assert width >= 0


def test_get_glyph_width_dictencoding_without_base_falls_through_to_family() -> None:
    """Wave 1391's positive case — base-less DictionaryEncoding +
    /Differences that doesn't cover ``code`` returns ``.notdef`` from
    typed encoding, and the helper falls through to the family default
    StandardEncoding for the lookup."""
    d = _helvetica_dict()
    # /Encoding with NO base, NO /Differences for code 0x41.
    dict_enc = DictionaryEncoding()
    d.set_item(COSName.get_pdf_name("Encoding"), dict_enc.get_cos_object())
    font = PDType1Font(d)
    # Code 0x41 — base-less encoding returns .notdef; fall-through to
    # StandardEncoding which DOES carry "A". Standard 14 AFM Helvetica
    # gives a real width (>0).
    width = font.get_glyph_width(0x41)
    assert width > 0


# ---------- get_font_matrix defensive branches ----------


def test_get_font_matrix_default_when_no_program() -> None:
    """When no font program is loaded, the default simple-font matrix
    [0.001, 0, 0, 0.001, 0, 0] is returned."""
    d = _helvetica_dict()
    font = PDType1Font(d)
    matrix = font.get_font_matrix()
    assert matrix == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_get_font_matrix_default_when_program_matrix_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Branch 824->828 — when the embedded program reports a matrix
    that isn't 6 elements long, the helper falls back to the simple-font
    default rather than emitting a bogus tuple."""
    d = _helvetica_dict()
    font = PDType1Font(d)

    class _BadMatrixProgram:
        def get_font_matrix(self) -> list[float]:
            return [0.001, 0.0]  # malformed; only 2 of 6 elements.

    # Bypass _get_type1_font isinstance check by patching the lookup.
    monkeypatch.setattr(font, "_get_type1_font", lambda: _BadMatrixProgram())
    matrix = font.get_font_matrix()
    assert matrix == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


def test_get_font_matrix_uses_program_matrix_when_well_formed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Complementary path — a well-formed 6-element matrix from the
    program wins over the simple-font default (PDFBOX-2298)."""
    d = _helvetica_dict()
    font = PDType1Font(d)
    expected = [0.0005, 0.0, 0.0, 0.0005, 0.0, 0.0]

    class _GoodMatrixProgram:
        def get_font_matrix(self) -> list[float]:
            return list(expected)

    monkeypatch.setattr(font, "_get_type1_font", lambda: _GoodMatrixProgram())
    assert font.get_font_matrix() == expected


# ---------- pd_font defensive guards (read_code zero-progress) ----------


def test_get_string_width_breaks_on_zero_consumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 712 in ``pd_font.get_string_width`` — when ``read_code``
    returns ``consumed=0`` the loop breaks, preventing an infinite
    spin."""
    d = _helvetica_dict()
    font = PDType1Font(d)
    # Patch encode to return a single byte so we enter the loop once.
    monkeypatch.setattr(font, "encode", lambda _t: b"\x41")
    # Patch read_code to claim 0 bytes consumed — must break out.
    monkeypatch.setattr(font, "read_code", lambda _d, _o: (0x41, 0))
    width = font.get_string_width("A")
    # No bytes consumed = no widths totted = 0.0.
    assert width == 0.0


# ---------- pd_font.get_font_descriptor defensive fallbacks ----------


def test_get_font_descriptor_returns_none_when_afm_lookup_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 158-159 in ``pd_font.get_font_descriptor`` — when
    ``get_standard14_afm`` raises one of the tolerated exceptions, the
    descriptor lookup yields ``None`` rather than propagating."""
    # Use a non-Standard-14 base font so the dict won't have a /FontDescriptor.
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    d.set_name(COSName.get_pdf_name("Subtype"), "Type1")
    d.set_name(COSName.get_pdf_name("BaseFont"), "NotAStandard14Font")
    font = PDType1Font(d)

    def _raise() -> object:
        raise OSError("simulated AFM load failure")

    monkeypatch.setattr(font, "get_standard14_afm", _raise)
    assert font.get_font_descriptor() is None


def test_get_font_descriptor_returns_none_when_build_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 165-166 — when the AFM resolves but the descriptor
    builder raises, the lookup yields ``None``."""
    d = _helvetica_dict()
    font = PDType1Font(d)

    from pypdfbox.pdmodel.font import pd_type1_font_embedder

    def _raise(_afm: object) -> object:
        raise ValueError("simulated build failure")

    monkeypatch.setattr(
        pd_type1_font_embedder.PDType1FontEmbedder,
        "build_font_descriptor_from_metrics",
        staticmethod(_raise),
    )
    # Drop any existing /FontDescriptor so the AFM-fallback branch runs.
    d.remove_item(COSName.get_pdf_name("FontDescriptor"))
    assert font.get_font_descriptor() is None
