"""Type 1 PFB embedder — populates :class:`PDType1Font` dictionaries.

Mirrors ``org.apache.pdfbox.pdmodel.font.PDType1FontEmbedder`` (PDFBox
3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/
PDType1FontEmbedder.java`` lines 44-178).

The class wires a Type 1 PFB into a PDF font dictionary:

* Parses the PFB structure (segments 1/2/3 -> ASCII/binary/footer).
* Builds a :class:`PDFontDescriptor` from the font header.
* Computes ``/FirstChar`` / ``/LastChar`` / ``/Widths`` arrays.
* Stores the segmented font program as a ``/FontFile`` stream with the
  ``/Length1`` / ``/Length2`` / ``/Length3`` markers PDF requires.

Library-first: fontTools' :class:`t1Lib.T1Font` handles the PFB parse
end-to-end. We don't reimplement EEXEC decryption or eexec-block
parsing.

Two factory ``build_font_descriptor`` overloads exist upstream — one for
a parsed Type 1 font, one for an AFM ``FontMetrics`` (used only by the
Standard 14 path). We surface both as static methods.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.common import PDStream

from .encoding.encoding import Encoding
from .encoding.type1_encoding import Type1Encoding
from .pd_font_descriptor import PDFontDescriptor

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


# Three PFB segment markers (Type 1 spec §F).
_PFB_MARKER = 0x80
_PFB_ASCII = 1
_PFB_BINARY = 2
_PFB_EOF = 3


def _parse_pfb_segments(pfb_bytes: bytes) -> tuple[bytes, list[int]]:
    """Strip PFB segment headers, returning concatenated bytes + lengths.

    Mirrors what upstream ``PfbParser`` does (Java imports from
    ``fontbox.pfb``). The return is ``(concatenated, [len1, len2, len3])``
    suitable for writing to ``/Length1`` / ``/Length2`` / ``/Length3``.
    """
    pos = 0
    lengths: list[int] = []
    out = bytearray()
    while pos < len(pfb_bytes):
        if pfb_bytes[pos] != _PFB_MARKER:
            # Plain PFA (ASCII-only) — return whole buffer as a single segment.
            return bytes(pfb_bytes), [len(pfb_bytes), 0, 0]
        kind = pfb_bytes[pos + 1]
        if kind == _PFB_EOF:
            break
        length = int.from_bytes(
            pfb_bytes[pos + 2 : pos + 6], "little", signed=False
        )
        pos += 6
        segment = pfb_bytes[pos : pos + length]
        out.extend(segment)
        lengths.append(length)
        pos += length
    while len(lengths) < 3:
        lengths.append(0)
    return bytes(out), lengths


class PDType1FontEmbedder:
    """Build a :class:`PDType1Font` dictionary from PFB bytes.

    Mirrors upstream Java line 44-178.
    """

    def __init__(
        self,
        document: PDDocument,
        dict_: COSDictionary,
        pfb_stream: io.BufferedIOBase | bytes,
        encoding: Encoding | None,
    ) -> None:
        # Upstream constructor (Java line 57-103). ``pfb_stream`` accepts
        # bytes or any read()-able BinaryIO for ergonomics.
        dict_.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
        if isinstance(pfb_stream, (bytes, bytearray)):
            pfb_bytes = bytes(pfb_stream)
        else:
            pfb_bytes = pfb_stream.read()
        try:
            from fontTools.t1Lib import T1Font
        except ImportError as ex:
            raise OSError("fontTools is required for Type 1 embedding") from ex
        t1_buffer = io.BytesIO(pfb_bytes)
        try:
            type1 = T1Font(t1_buffer)
        except OSError:
            type1 = None
        self._type1: Any = type1
        if encoding is None and type1 is not None:
            self._font_encoding: Encoding = Type1Encoding.from_font_box(
                _Type1EncodingAdapter(type1)
            )
        elif encoding is None:
            self._font_encoding = Type1Encoding()
        else:
            self._font_encoding = encoding
        # Font descriptor
        fd = self.build_font_descriptor(type1) if type1 is not None else PDFontDescriptor()
        # Font file stream — write the concatenated PFB minus markers.
        concatenated, lengths = _parse_pfb_segments(pfb_bytes)
        font_stream = PDStream(document, io.BytesIO(concatenated), COSName.FLATE_DECODE)
        for i, length in enumerate(lengths):
            font_stream.get_cos_object().set_int(f"Length{i + 1}", int(length))
        fd.set_font_file(font_stream)
        dict_.set_item(COSName.FONT_DESC, fd.get_cos_object())
        if type1 is not None:
            base_font = self._get_type1_name(type1)
            if base_font:
                dict_.set_name(COSName.BASE_FONT, base_font)
        # Widths
        widths = COSArray()
        for code in range(256):
            name = self._font_encoding.get_name(code)
            width = 0
            if type1 is not None and name and name != ".notdef":
                try:
                    width = round(self._get_type1_width(type1, name))
                except (AttributeError, TypeError, ValueError):
                    width = 0
            widths.add(COSInteger(int(width)))
        dict_.set_int(COSName.FIRST_CHAR, 0)
        dict_.set_int(COSName.LAST_CHAR, 255)
        dict_.set_item(COSName.WIDTHS, widths)
        cos_encoding = (
            encoding.get_cos_object() if encoding is not None else None
        )
        if cos_encoding is not None:
            dict_.set_item(COSName.ENCODING, cos_encoding)
        self._font_descriptor: PDFontDescriptor = fd

    # ---------- accessors ----------

    def get_font_encoding(self) -> Encoding:
        """Return the active encoding.

        Mirrors upstream ``getFontEncoding`` (Java line 156-161).
        """
        return self._font_encoding

    def get_glyph_list(self) -> Any:
        """Return the Adobe Glyph List singleton.

        Mirrors upstream ``getGlyphList`` (Java line 164-168).
        """
        from pypdfbox.fontbox.encoding.glyph_list import GlyphList

        return GlyphList.get_adobe_glyph_list()

    def get_type1_font(self) -> Any:
        """Return the parsed Type 1 font.

        Mirrors upstream ``getType1Font`` (Java line 171-176).
        """
        return self._type1

    # ---------- descriptor builders ----------

    @staticmethod
    def build_font_descriptor(type1: Any) -> PDFontDescriptor:
        """Construct a :class:`PDFontDescriptor` from a Type 1 font.

        Mirrors upstream ``buildFontDescriptor(Type1Font)`` (Java line
        110-127).
        """
        fd = PDFontDescriptor()
        name = PDType1FontEmbedder._get_type1_name(type1)
        if name:
            fd.set_font_name(name)
        family = type1.font.get("FamilyName") if isinstance(type1.font, dict) else None
        if family:
            from pypdfbox.cos import COSString

            fd.get_cos_object().set_item(
                COSName.get_pdf_name("FontFamily"), COSString(str(family))
            )
        font_info = (
            type1.font.get("FontInfo", {}) if isinstance(type1.font, dict) else {}
        )
        bbox = type1.font.get("FontBBox") if isinstance(type1.font, dict) else None
        if bbox is not None and len(bbox) >= 4:
            from pypdfbox.pdmodel.pd_rectangle import PDRectangle

            rect = PDRectangle()
            rect.set_lower_left_x(float(bbox[0]))
            rect.set_lower_left_y(float(bbox[1]))
            rect.set_upper_right_x(float(bbox[2]))
            rect.set_upper_right_y(float(bbox[3]))
            fd.set_font_bounding_box(rect)
            fd.set_ascent(float(bbox[3]))
            fd.set_descent(float(bbox[1]))
        encoding_obj = type1.font.get("Encoding") if isinstance(type1.font, dict) else None
        is_symbolic = encoding_obj is None or (
            isinstance(encoding_obj, str) and encoding_obj == "FontSpecific"
        )
        fd.set_symbolic(is_symbolic)
        fd.set_non_symbolic(not is_symbolic)
        italic_angle = (
            font_info.get("ItalicAngle", 0) if isinstance(font_info, dict) else 0
        )
        fd.set_italic_angle(float(italic_angle))
        fd.set_stem_v(0.0)
        return fd

    @staticmethod
    def build_font_descriptor_from_metrics(metrics: Any) -> PDFontDescriptor:
        """Construct a :class:`PDFontDescriptor` from AFM metrics.

        Mirrors upstream ``buildFontDescriptor(FontMetrics)`` (Java line
        134-153). Used by the Standard 14 path.
        """
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle

        fd = PDFontDescriptor()
        is_symbolic = (
            metrics.get_encoding_scheme() == "FontSpecific"
            if hasattr(metrics, "get_encoding_scheme")
            else False
        )
        fd.set_font_name(metrics.get_font_name())
        try:
            from pypdfbox.cos import COSString

            family = metrics.get_family_name()
            if family:
                fd.get_cos_object().set_item(
                    COSName.get_pdf_name("FontFamily"), COSString(str(family))
                )
        except AttributeError:
            pass
        fd.set_non_symbolic(not is_symbolic)
        fd.set_symbolic(is_symbolic)
        try:
            bbox = metrics.get_font_bbox()
            rect = PDRectangle()
            rect.set_lower_left_x(float(bbox[0]))
            rect.set_lower_left_y(float(bbox[1]))
            rect.set_upper_right_x(float(bbox[2]))
            rect.set_upper_right_y(float(bbox[3]))
            fd.set_font_bounding_box(rect)
        except (AttributeError, TypeError, IndexError):
            pass
        for accessor, setter in (
            ("get_italic_angle", "set_italic_angle"),
            ("get_ascender", "set_ascent"),
            ("get_descender", "set_descent"),
            ("get_cap_height", "set_cap_height"),
            ("get_x_height", "set_x_height"),
            ("get_average_character_width", "set_average_width"),
        ):
            try:
                value = getattr(metrics, accessor)()
                getattr(fd, setter)(float(value))
            except (AttributeError, TypeError, ValueError):
                continue
        try:
            cs = metrics.get_character_set()
            if cs:
                fd.set_character_set(cs)
        except AttributeError:
            pass
        fd.set_stem_v(0.0)
        return fd

    # ---------- helpers ----------

    @staticmethod
    def _get_type1_name(type1: Any) -> str | None:
        if isinstance(type1.font, dict):
            return type1.font.get("FontName")
        return None

    @staticmethod
    def _get_type1_width(type1: Any, name: str) -> float:
        # fontTools T1Font exposes a CharStrings map; widths come from
        # the parsed Private dict + CharStrings. Use the public
        # ``getGlyphSet()[name].width`` accessor when available.
        try:
            glyph_set = type1.getGlyphSet()
            glyph = glyph_set[name]
            return float(getattr(glyph, "width", 0) or 0)
        except (AttributeError, KeyError):
            return 0.0


class _Type1EncodingAdapter:
    """Adapts a fontTools T1Font's encoding to the FontBox encoding shape.

    fontTools exposes the Type 1 Encoding as either an array of glyph
    names or the literal string ``"StandardEncoding"``. The
    :class:`Type1Encoding.from_font_box` factory expects an object with
    ``get_code_to_name_map() -> dict[int, str]``.
    """

    def __init__(self, type1: Any) -> None:
        self._type1 = type1

    def get_code_to_name_map(self) -> dict[int, str]:
        encoding = (
            self._type1.font.get("Encoding")
            if isinstance(self._type1.font, dict)
            else None
        )
        if isinstance(encoding, (list, tuple)):
            return {i: name for i, name in enumerate(encoding) if isinstance(name, str)}
        # ``StandardEncoding`` etc — return empty; caller falls back to
        # the bundled StandardEncoding singleton via Type1Encoding().
        return {}


__all__ = ["PDType1FontEmbedder"]
