"""Second-wave parity tests for the encoding cluster.

Covers gaps spotted while comparing the pdmodel/font/encoding surface
against upstream PDFBox 3.0:

- ``DictionaryEncoding.getEncodingName()`` ordering matches upstream
  (``"<base> with differences"`` rather than the inverse).
- Predefined ``Encoding.getCOSObject()`` returns the spec ``COSName``
  directly — mirrors the upstream override on each subclass.
- Constructor parity: an invalid base encoding name in the writer-path
  constructor raises (upstream throws ``IllegalArgumentException``).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.encoding import (
    DictionaryEncoding,
    MacRomanEncoding,
    StandardEncoding,
    WinAnsiEncoding,
)

# ---------- DictionaryEncoding.get_encoding_name parity -------------------


def test_dictionary_encoding_name_matches_upstream_ordering():
    # Upstream returns "<baseName> with differences", not the inverse.
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    assert enc.get_encoding_name() == "WinAnsiEncoding with differences"


def test_dictionary_encoding_name_with_standard_base():
    enc = DictionaryEncoding(base_encoding=COSName.STANDARD_ENCODING)  # type: ignore[attr-defined]
    assert enc.get_encoding_name() == "StandardEncoding with differences"


def test_dictionary_encoding_name_type3_no_base():
    # Without a base encoding (Type 3 path) the differences array is the
    # complete encoding — upstream returns the literal string "differences".
    from pypdfbox.cos import COSDictionary

    font_enc = COSDictionary()
    font_enc.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    enc = DictionaryEncoding(font_encoding=font_enc)
    assert enc.get_encoding_name() == "differences"


# ---------- predefined get_cos_object overrides ---------------------------


def test_win_ansi_get_cos_object_returns_interned_cos_name():
    cos = WinAnsiEncoding.INSTANCE.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.name == "WinAnsiEncoding"
    # Interned: same instance on repeated calls.
    assert cos is COSName.get_pdf_name("WinAnsiEncoding")


def test_standard_get_cos_object_returns_interned_cos_name():
    cos = StandardEncoding.INSTANCE.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.name == "StandardEncoding"
    assert cos is COSName.STANDARD_ENCODING  # type: ignore[attr-defined]


def test_mac_roman_get_cos_object_returns_interned_cos_name():
    cos = MacRomanEncoding.INSTANCE.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.name == "MacRomanEncoding"
    assert cos is COSName.get_pdf_name("MacRomanEncoding")


# ---------- DictionaryEncoding constructor validation --------------------


def test_dictionary_encoding_writer_rejects_invalid_base_name():
    # Upstream throws IllegalArgumentException for an unrecognised /BaseEncoding.
    bogus = COSName.get_pdf_name("DoesNotExistEncoding")
    with pytest.raises(ValueError, match="Invalid encoding"):
        DictionaryEncoding(base_encoding=bogus)
