"""Ported upstream tests for ``TestFontEncoding`` (font-level encoding glue).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/TestFontEncoding.java``
(PDFBox 3.0.x). Three upstream methods:

* ``testAdd`` — ``WinAnsiEncoding`` / ``MacRomanEncoding`` ``space`` →
  code 32 round-trip (PDFBOX-3332).
* ``testOverwrite`` — ``DictionaryEncoding`` differences array overwrites
  a base-encoding slot: code 32 reassigned from ``space`` to ``a``
  (PDFBOX-3332).
* ``testPDFBox3884`` — end-to-end PDF round-trip that exercises the
  ``glyphlist.txt`` "multiple names per codepoint" path (tilde /
  asciitilde). Skipped here because it requires the ``PDFTextStripper``
  text-extraction pipeline.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.fontbox.encoding.mac_roman_encoding import MacRomanEncoding
from pypdfbox.fontbox.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.encoding.dictionary_encoding import DictionaryEncoding


def test_add() -> None:
    """Port of upstream ``testAdd`` (PDFBOX-3332).

    The bug was a use-after-free where the cached ``name_to_code`` map
    was wiped when a derived encoding overlaid a base. The two
    encoding singletons must continue to advertise ``space`` → 32.
    """
    assert WinAnsiEncoding.INSTANCE.get_name_to_code_map().get("space") == 32
    assert MacRomanEncoding.INSTANCE.get_name_to_code_map().get("space") == 32


def test_overwrite() -> None:
    """Port of upstream ``testOverwrite`` (PDFBOX-3332).

    A ``DictionaryEncoding`` with a one-entry ``/Differences`` array
    ``[32 /a]`` must replace the base ``WinAnsiEncoding`` slot at code
    32 — the old ``space`` name no longer maps to 32, and ``a`` does.
    """
    dict_encoding_dict = COSDictionary()
    dict_encoding_dict.set_item(COSName.TYPE, COSName.ENCODING)
    dict_encoding_dict.set_item(
        COSName.get_pdf_name("BaseEncoding"), COSName.WIN_ANSI_ENCODING
    )
    differences = COSArray()
    differences.add(COSInteger.get(32))
    differences.add(COSName.get_pdf_name("a"))
    dict_encoding_dict.set_item(COSName.get_pdf_name("Differences"), differences)

    dict_encoding = DictionaryEncoding(font_encoding=dict_encoding_dict)
    name_to_code = dict_encoding.get_name_to_code_map()
    # The base-encoding "space" → 32 mapping is shadowed by /Differences.
    assert name_to_code.get("space") is None
    # /Differences [32 /a] re-maps code 32 to glyph name "a".
    assert name_to_code.get("a") == 32


@pytest.mark.skip(
    reason="upstream's testPDFBox3884 builds a full PDF with PDPageContentStream"
    " + PDFTextStripper and verifies the extracted text is '~˜' (asciitilde + tilde)"
    " — this exercises the rendering / text-extraction pipeline which is not yet"
    " in scope for parity round-out. The underlying GlyphList multi-name lookup"
    " is covered by tests/fontbox/encoding/upstream/test_glyph_list.py."
)
def test_pdf_box_3884() -> None: ...
