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
        # De-segment the PFB container once (markers stripped). The
        # concatenated cleartext+eexec+footer bytes are valid raw Type 1
        # font data — both for the /FontFile stream below and for parsing.
        concatenated, lengths = _parse_pfb_segments(pfb_bytes)
        # Library-first: parse via pypdfbox's own :class:`Type1Font`,
        # which wraps fontTools' ``T1Font`` correctly (via ``__new__`` +
        # ``.data``/``.encoding``) instead of fontTools' ``T1Font(path)``
        # constructor — the latter only accepts a file PATH and raises
        # ``TypeError`` on a buffer. ``from_bytes`` routes through
        # fontTools' full PostScript interpreter so per-glyph widths and
        # outlines are available (``create_with_pfb`` uses the in-house
        # header-only parser, which can't render glyphs → width 0).
        from pypdfbox.fontbox.type1.type1_font import Type1Font  # noqa: PLC0415

        # fontTools raises its own ``T1Error`` (a bare ``Exception``) on a
        # malformed PostScript program, alongside the structural errors;
        # treat any parse failure as "no embedded program" so a damaged
        # /FontFile degrades to a name-less descriptor rather than crashing
        # the embed.
        try:
            from fontTools.t1Lib import T1Error  # noqa: PLC0415
        except ImportError:  # pragma: no cover - fontTools always present
            T1Error = ()  # type: ignore[assignment, misc]

        type1: Any
        try:
            type1 = Type1Font.from_bytes(concatenated)
        except (OSError, ValueError, AssertionError, TypeError, IndexError, T1Error):
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
        # Mirrors upstream ``new PDStream(doc, in, COSName.FLATE_DECODE)``
        # which *encodes* the bytes through the filter. pypdfbox's
        # ``PDStream(doc, data, filter)`` overload stores the bytes
        # verbatim and only records ``/Filter`` (it assumes pre-encoded
        # input), so handing it raw bytes would produce a stream tagged
        # FlateDecode whose body is actually uncompressed — unreadable on
        # round-trip. Write through ``create_output_stream(FLATE_DECODE)``
        # so the body is genuinely compressed and ``/Length1..3`` describe
        # the *decoded* segment sizes (per PDF 32000-1 §9.9).
        font_stream = PDStream(document)
        out = font_stream.create_output_stream(COSName.FLATE_DECODE)
        try:
            out.write(concatenated)
        finally:
            out.close()
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
        family = PDType1FontEmbedder._safe_call(type1, "get_family_name")
        if family:
            from pypdfbox.cos import COSString

            fd.get_cos_object().set_item(
                COSName.get_pdf_name("FontFamily"), COSString(str(family))
            )
        bbox = PDType1FontEmbedder._safe_call(type1, "get_font_b_box")
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
        # Symbolic when the font's /Encoding is FontSpecific (built-in) —
        # i.e. not a recoverable standard code->name table. Type1Font
        # resolves a named/array Encoding to a code map and empties it for
        # the FontSpecific/built-in case.
        encoding_map = PDType1FontEmbedder._safe_call(type1, "get_encoding")
        is_symbolic = not encoding_map
        fd.set_symbolic(is_symbolic)
        fd.set_non_symbolic(not is_symbolic)
        italic_angle = PDType1FontEmbedder._safe_call(type1, "get_italic_angle") or 0
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
            bbox = metrics.get_font_b_box()
            # AfmMetrics.get_font_b_box returns a FontBox ``BoundingBox`` object
            # (mirroring FontMetrics.getFontBBox()), not a 4-element sequence.
            # Normalise via its accessors, falling back to subscripting for a
            # plain list/tuple shape.
            if hasattr(bbox, "get_lower_left_x"):
                coords = (
                    bbox.get_lower_left_x(),
                    bbox.get_lower_left_y(),
                    bbox.get_upper_right_x(),
                    bbox.get_upper_right_y(),
                )
            else:
                coords = (bbox[0], bbox[1], bbox[2], bbox[3])
            rect = PDRectangle()
            rect.set_lower_left_x(float(coords[0]))
            rect.set_lower_left_y(float(coords[1]))
            rect.set_upper_right_x(float(coords[2]))
            rect.set_upper_right_y(float(coords[3]))
            fd.set_font_bounding_box(rect)
        except (AttributeError, TypeError, IndexError):
            pass
        # Ascender / descender / cap-height / x-height live on the underlying
        # FontBox ``FontMetrics`` object (mirroring upstream
        # buildFontDescriptor(FontMetrics)); the AfmMetrics wrapper only
        # surfaces them through get_font_metrics_object(). ItalicAngle and the
        # average width are exposed directly on the wrapper.
        font_metrics = None
        try:
            font_metrics = metrics.get_font_metrics_object()
        except AttributeError:
            font_metrics = None
        for source, accessor, setter in (
            (metrics, "get_italic_angle", "set_italic_angle"),
            (font_metrics, "get_ascender", "set_ascent"),
            (font_metrics, "get_descender", "set_descent"),
            (font_metrics, "get_cap_height", "set_cap_height"),
            (font_metrics, "get_x_height", "set_x_height"),
            (metrics, "get_average_width", "set_average_width"),
        ):
            if source is None:
                continue
            try:
                value = getattr(source, accessor)()
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
    def _safe_call(type1: Any, accessor: str) -> Any:
        """Call ``type1.<accessor>()`` returning ``None`` on any failure.

        The parsed font is a pypdfbox :class:`Type1Font`; its accessors
        can raise on damaged programs, so every read is guarded.
        """
        try:
            return getattr(type1, accessor)()
        except (AttributeError, TypeError, ValueError, AssertionError, KeyError):
            return None

    @staticmethod
    def _get_type1_name(type1: Any) -> str | None:
        # pypdfbox Type1Font.get_font_name() returns the /FontName.
        name = PDType1FontEmbedder._safe_call(type1, "get_font_name")
        return str(name) if name else None

    @staticmethod
    def _get_type1_width(type1: Any, name: str) -> float:
        # pypdfbox Type1Font.get_width(name) forces a no-op glyph draw to
        # populate the fontTools advance, so this returns the real width
        # (the previous getGlyphSet()[name].width read was always None
        # pre-draw and silently produced 0 for every glyph).
        try:
            return float(type1.get_width(name))
        except (AttributeError, KeyError, TypeError, ValueError):
            return 0.0


class _Type1EncodingAdapter:
    """Adapts a pypdfbox :class:`Type1Font` encoding to the FontBox shape.

    :class:`Type1Encoding.from_font_box` expects an object exposing
    ``get_code_to_name_map() -> dict[int, str]``. ``Type1Font.get_encoding``
    already returns a resolved ``code -> glyph name`` map (named encodings
    such as ``StandardEncoding`` folded to the Adobe table, ``.notdef``
    slots dropped), so we forward it directly.
    """

    def __init__(self, type1: Any) -> None:
        self._type1 = type1

    def get_code_to_name_map(self) -> dict[int, str]:
        try:
            mapping = self._type1.get_encoding()
        except (AttributeError, TypeError, ValueError, AssertionError, KeyError):
            return {}
        if isinstance(mapping, dict):
            return {
                int(code): str(name)
                for code, name in mapping.items()
                if isinstance(name, str)
            }
        return {}


__all__ = ["PDType1FontEmbedder"]
