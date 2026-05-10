"""Ported upstream tests for ``PDFont`` (abstract base class).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDFontTest.java``
(PDFBox 3.0.x). Most upstream tests in that file are end-to-end tests that
load real ``.ttf`` / ``.pfb`` font files, build a ``PDDocument``, render
pages, and run ``PDFTextStripper`` round-trips — they exercise concrete
subclasses (``PDTrueTypeFont``, ``PDType0Font``, ``PDType1Font``) rather
than the abstract base. Those tests are tracked under their respective
subclass test files.

Listed below are the upstream methods and the per-test disposition:

- ``testPDFBox988`` / ``testPDFBOX5486`` / ``testPDFBox3747`` /
  ``testPDFBox3826`` / ``testPDFBOX4115`` / ``testPDFox4318`` /
  ``testFullEmbeddingTTC`` / ``testPDFox5048`` / ``testDeleteFont`` /
  ``testSoftHyphen`` / ``testPDFBox5484`` / ``PDFBOX5920Type0`` /
  ``PDFBOX5920TrueType`` / ``testSymbol`` —
  end-to-end tests; require full PDF rendering / ``PDFTextStripper`` and
  binary font fixtures. Tracked at the subclass level (see
  ``tests/pdmodel/font/upstream/test_pd_type0_font.py``,
  ``tests/pdmodel/font/upstream/test_pd_type1_font.py``).

The cases in this file are the *base-class invariants* the upstream
suite implies but does not assert directly: the COS surface of the
abstract ``PDFont`` (type / subtype / descriptor / ``/ToUnicode`` cmap
plumbing). Hand-written counterparts live in
``tests/pdmodel/font/test_pd_font.py`` and
``tests/pdmodel/font/test_pd_font_base_parity.py``.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font import PDType1Font


def test_pd_font_get_type_returns_font_constant() -> None:
    """Upstream ``PDFont.getType()`` is documented to "always return Font".
    Our base ``PDFont.__init__`` writes ``/Type = /Font`` on a fresh dict.
    """
    font = PDType1Font()
    assert font.get_type() == "Font"


def test_pd_font_get_sub_type_reflects_dict_subtype() -> None:
    """Upstream ``PDFont.getSubType()`` returns the ``/Subtype`` name.
    Verified via the ``Type1`` subclass which sets ``/Subtype = /Type1``."""
    font = PDType1Font()
    assert font.get_sub_type() == "Type1"


def test_pd_font_cos_object_round_trip() -> None:
    """Upstream ``PDFont.getCOSObject()`` returns the underlying dict so
    callers can re-wrap. Verified by wrapping a custom dict and checking
    pointer identity."""
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    font = PDType1Font(raw)
    assert font.get_cos_object() is raw


def test_pd_font_equals_uses_cos_dict_identity() -> None:
    """Upstream ``PDFont.equals`` compares ``getCOSObject() ==`` (Java
    reference identity). Two wrappers over the same dict are equal; two
    wrappers over distinct-but-identical dicts are not."""
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    a = PDType1Font(raw)
    b = PDType1Font(raw)
    assert a == b
    # Distinct dicts — even with the same /Subtype — are not equal.
    other_raw = COSDictionary()
    other_raw.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    c = PDType1Font(other_raw)
    assert a != c


def test_pd_font_hash_matches_equality() -> None:
    """``PDFont.hashCode`` upstream returns ``getCOSObject().hashCode()``;
    two equal fonts must hash the same."""
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    a = PDType1Font(raw)
    b = PDType1Font(raw)
    assert hash(a) == hash(b)


def test_pd_font_to_string_includes_class_and_base_font() -> None:
    """Upstream ``PDFont.toString()`` returns ``"<ClassName> <BaseFont>"``."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    assert str(font) == "PDType1Font Helvetica"


def test_pd_font_read_c_map_predefined_name() -> None:
    """Upstream ``PDFont.readCMap(COSBase)`` resolves a predefined CMap
    name (``COSName``) to its parsed ``CMap``."""
    font = PDType1Font()
    cmap = font.read_c_map(COSName.get_pdf_name("Identity-H"))
    assert cmap is not None


def test_pd_font_equals_java_spelling_matches_dict_identity() -> None:
    """Upstream ``PDFont.equals(Object)`` (PDFont.java lines 672-676) is
    Java reference identity over ``getCOSObject()``. Snake_case mirror
    ``equals(...)`` must match this contract."""
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    a = PDType1Font(raw)
    b = PDType1Font(raw)
    assert a.equals(b) is True
    other = COSDictionary()
    other.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    c = PDType1Font(other)
    assert a.equals(c) is False
    # Non-PDFont arguments must return False, not raise.
    assert a.equals("not a font") is False


def test_pd_font_hash_code_java_spelling_matches_hash_builtin() -> None:
    """Upstream ``PDFont.hashCode()`` (PDFont.java lines 678-682) returns
    ``getCOSObject().hashCode()``. The snake_case ``hash_code()`` mirror
    must agree with the Python ``hash(font)`` builtin."""
    font = PDType1Font()
    assert font.hash_code() == hash(font)


def test_pd_font_to_string_java_spelling_matches_str() -> None:
    """Upstream ``PDFont.toString()`` (PDFont.java lines 684-688) returns
    ``getClass().getSimpleName() + " " + getName()``. Snake_case mirror
    ``to_string()`` must agree with ``str(font)``."""
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    assert font.to_string() == "PDType1Font Helvetica"
    assert font.to_string() == str(font)
