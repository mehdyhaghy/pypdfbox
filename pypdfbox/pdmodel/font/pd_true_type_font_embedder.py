"""TrueType embedder for :class:`PDTrueTypeFont`.

Mirrors ``org.apache.pdfbox.pdmodel.font.PDTrueTypeFontEmbedder`` (PDFBox
3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/
PDTrueTypeFontEmbedder.java`` lines 43-135).

Populates a :class:`PDTrueTypeFont` dictionary from a TTF: wires up the
``/Subtype /TrueType`` entry, attaches the encoding, builds the width
array via the cmap, and embeds the font program through the inherited
:class:`TrueTypeEmbedder` plumbing.

The class is ``final`` upstream and only used by :class:`PDTrueTypeFont`
to build the dictionary from a real TTF — there is no subset path here
(``buildSubset`` raises ``UnsupportedOperationException``).
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName

from .encoding.encoding import Encoding
from .true_type_embedder import TrueTypeEmbedder

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


class PDTrueTypeFontEmbedder(TrueTypeEmbedder):
    """TrueType embedder that produces a :class:`PDTrueTypeFont` dictionary.

    Mirrors upstream Java line 43-135.
    """

    def __init__(
        self,
        document: PDDocument,
        dict_: COSDictionary,
        ttf: Any,
        encoding: Encoding,
    ) -> None:
        # Upstream constructor (Java line 56-73). ``embed_subset=False``
        # — see ``buildSubset`` below: subsetting routes through
        # PDType0Font/PDCIDFontType2Embedder.
        super().__init__(document, dict_, ttf, embed_subset=False)
        dict_.set_item(COSName.SUBTYPE, COSName.get_pdf_name("TrueType"))
        self._font_encoding: Encoding = encoding
        cos_encoding = encoding.get_cos_object()
        if cos_encoding is not None:
            dict_.set_item(COSName.ENCODING, cos_encoding)
        self.font_descriptor.set_symbolic(False)
        self.font_descriptor.set_non_symbolic(True)
        dict_.set_item(COSName.FONT_DESC, self.font_descriptor.get_cos_object())
        self.set_widths(dict_)

    def get_font_encoding(self) -> Encoding:
        """Return the active encoding.

        Mirrors upstream ``getFontEncoding`` (Java line 123-126).
        """
        return self._font_encoding

    def build_subset(
        self,
        ttf_subset: io.BufferedIOBase,
        tag: str,
        gid_to_cid: dict[int, int],
    ) -> None:
        """Reject subset builds — upstream uses PDType0Font instead.

        Mirrors upstream ``buildSubset`` (Java line 128-134).
        """
        del ttf_subset, tag, gid_to_cid
        raise NotImplementedError(
            "TrueType subsetting routes through PDType0Font"
        )

    # ---------- helpers ----------

    def set_widths(self, font: COSDictionary) -> None:
        """Compute the ``/FirstChar`` / ``/LastChar`` / ``/Widths`` arrays.

        Mirrors upstream ``setWidths`` (Java line 78-118).
        """
        # Library-first: fontTools exposes ``cmap``, ``head``, ``hmtx``.
        try:
            head = self._ttf["head"]
            hmtx = self._ttf["hmtx"]
        except KeyError:
            return
        units_per_em = int(getattr(head, "unitsPerEm", 1000) or 1000)
        scaling = 1000.0 / units_per_em
        try:
            from pypdfbox.fontbox.encoding.glyph_list import GlyphList

            glyph_list = GlyphList.get_adobe_glyph_list()
        except (ImportError, AttributeError):
            glyph_list = None
        code_to_name: dict[int, str] = self._font_encoding.get_code_to_name_map()
        if not code_to_name:
            return
        codes = list(code_to_name.keys())
        first_char = min(codes)
        last_char = max(codes)
        widths: list[int] = [0] * (last_char - first_char + 1)
        cmap = self._get_unicode_cmap()
        for code, name in code_to_name.items():
            if first_char <= code <= last_char:
                gid = 0
                if glyph_list is not None:
                    uni = glyph_list.to_unicode(name)
                    if uni:
                        gid = cmap.get(ord(uni[0]), 0)
                if gid > 0 or name != ".notdef":
                    try:
                        advance, _lsb = hmtx[self._ttf.getGlyphName(gid)]
                        widths[code - first_char] = round(advance * scaling)
                    except (AttributeError, KeyError, TypeError):
                        widths[code - first_char] = 0
        font.set_int(COSName.FIRST_CHAR, first_char)
        font.set_int(COSName.LAST_CHAR, last_char)
        cos_widths = COSArray()
        for w in widths:
            cos_widths.add(COSInteger(int(w)))
        font.set_item(COSName.WIDTHS, cos_widths)

    def _get_unicode_cmap(self) -> dict[int, int]:
        """Return a Unicode codepoint -> GID mapping from the TTF cmap."""
        try:
            cmap_table = self._ttf["cmap"]
            best_cmap = cmap_table.getBestCmap()
            if best_cmap is None:
                return {}
            # Best-cmap maps codepoint -> glyph name; convert to GID.
            getglyphid = self._ttf.getGlyphID
            return {
                cp: int(getglyphid(name) or 0)
                for cp, name in best_cmap.items()
                if name is not None
            }
        except (KeyError, AttributeError):
            return {}


__all__ = ["PDTrueTypeFontEmbedder"]
