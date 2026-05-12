from __future__ import annotations

import datetime as _dt

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSName,
    COSNumber,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_TYPE: COSName = COSName.get_pdf_name("Type")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_ANNOT: COSName = COSName.get_pdf_name("Annot")
_PAGE: COSName = COSName.get_pdf_name("Page")
_NM: COSName = COSName.get_pdf_name("NM")
_CONTENTS: COSName = COSName.get_pdf_name("Contents")
_T: COSName = COSName.get_pdf_name("T")
_RECT: COSName = COSName.get_pdf_name("Rect")
_C: COSName = COSName.get_pdf_name("C")
_F: COSName = COSName.get_pdf_name("F")
_NAME: COSName = COSName.get_pdf_name("Name")
_M: COSName = COSName.get_pdf_name("M")
_CA: COSName = COSName.get_pdf_name("CA")
_SUBJ: COSName = COSName.get_pdf_name("Subj")
_IT: COSName = COSName.get_pdf_name("IT")
_RC: COSName = COSName.get_pdf_name("RC")
_BS: COSName = COSName.get_pdf_name("BS")
_BE: COSName = COSName.get_pdf_name("BE")
_CREATION_DATE: COSName = COSName.get_pdf_name("CreationDate")

# Annotation flag bits — match upstream FDFAnnotation.FLAG_* constants.
_FLAG_INVISIBLE: int = 1
_FLAG_HIDDEN: int = 1 << 1
_FLAG_PRINTED: int = 1 << 2
_FLAG_NO_ZOOM: int = 1 << 3
_FLAG_NO_ROTATE: int = 1 << 4
_FLAG_NO_VIEW: int = 1 << 5
_FLAG_READ_ONLY: int = 1 << 6
_FLAG_LOCKED: int = 1 << 7
_FLAG_TOGGLE_NO_VIEW: int = 1 << 8
_FLAG_LOCKED_CONTENTS: int = 1 << 9


# RGB colour: an (r, g, b) float triple in [0,1]. Mirrors java.awt.Color usage
# at the FDFAnnotation API boundary.
ColorTuple = tuple[float, float, float]


class FDFAnnotation:
    """Base class for an FDF annotation entry inside ``/Annots``.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFAnnotation``. Subtype-specific
    classes (``FDFAnnotationText``, ``FDFAnnotationFreeText``, etc.) extend
    this base; the base exposes the entries shared by every FDF annotation
    dictionary (``/Page``, ``/NM``, ``/Contents``, ``/T`` author, ``/Rect``,
    ``/C`` colour, ``/F`` flags, ``/Name``, ``/M`` modified, ``/CA`` opacity,
    ``/Subj`` subject, ``/IT`` intent, ``/RC`` rich contents, ``/BS`` border
    style, ``/BE`` border effect, ``/CreationDate``).
    """

    def __init__(self, annot: COSDictionary | None = None) -> None:
        self._annot: COSDictionary = annot if annot is not None else COSDictionary()
        # Stamp /Type Annot when none present (matches upstream constructor).
        if self._annot.get_dictionary_object(_TYPE) is None:
            self._annot.set_item(_TYPE, _ANNOT)

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._annot

    # ---------- /Page (0-based page index) ----------

    def get_page(self) -> int:
        return self._annot.get_int(_PAGE)

    def has_page(self) -> bool:
        return isinstance(self._annot.get_dictionary_object(_PAGE), COSNumber)

    def clear_page(self) -> None:
        self._annot.remove_item(_PAGE)

    def set_page(self, page: int) -> None:
        self._annot.set_int(_PAGE, page)

    # ---------- /NM unique name ----------

    def get_name(self) -> str | None:
        return self._annot.get_string(_NM)

    def has_name(self) -> bool:
        return self.get_name() is not None

    def clear_name(self) -> None:
        self.set_name(None)

    def set_name(self, name: str | None) -> None:
        self._annot.set_string(_NM, name)

    # ---------- /Contents ----------

    def get_contents(self) -> str | None:
        return self._annot.get_string(_CONTENTS)

    def has_contents(self) -> bool:
        return self.get_contents() is not None

    def clear_contents(self) -> None:
        self.set_contents(None)

    def set_contents(self, contents: str | None) -> None:
        self._annot.set_string(_CONTENTS, contents)

    # ---------- /T (author / title) ----------

    def get_title(self) -> str | None:
        return self._annot.get_string(_T)

    def has_title(self) -> bool:
        return self.get_title() is not None

    def clear_title(self) -> None:
        self.set_title(None)

    def set_title(self, title: str | None) -> None:
        self._annot.set_string(_T, title)

    # ---------- /Subtype ----------

    def get_subtype(self) -> str | None:
        v = self._annot.get_dictionary_object(_SUBTYPE)
        if isinstance(v, COSName):
            return v.name
        return None

    def has_subtype(self) -> bool:
        return self.get_subtype() is not None

    def clear_subtype(self) -> None:
        self.set_subtype(None)

    def set_subtype(self, subtype: str | None) -> None:
        if subtype is None:
            self._annot.remove_item(_SUBTYPE)
        else:
            self._annot.set_item(_SUBTYPE, COSName.get_pdf_name(subtype))

    # ---------- /Rect (4-element float array) ----------

    def get_rectangle(self) -> tuple[float, float, float, float] | None:
        """Return the ``/Rect`` array as a 4-tuple of floats.

        Mirrors upstream ``getRectangle()`` (which returns ``PDRectangle``);
        pypdfbox uses a tuple for the cross-cutting FDF API surface — see
        :meth:`get_rectangle_as_pd_rectangle` for the upstream-shaped form.
        """
        v = self._annot.get_dictionary_object(_RECT)
        if isinstance(v, COSArray) and len(v) == 4:
            values = _float_values(v, 4)
            if values is not None:
                return (values[0], values[1], values[2], values[3])
        return None

    def get_rectangle_as_pd_rectangle(self) -> PDRectangle | None:
        """Return the ``/Rect`` array as a :class:`PDRectangle`.

        Mirrors upstream ``getRectangle()`` exactly; the tuple form provided
        by :meth:`get_rectangle` is the pypdfbox-native variant.
        """
        v = self._annot.get_dictionary_object(_RECT)
        if isinstance(v, COSArray) and len(v) == 4:
            try:
                return PDRectangle.from_cos_array(v)
            except (TypeError, ValueError):
                return None
        return None

    def has_rectangle(self) -> bool:
        return self.get_rectangle() is not None

    def clear_rectangle(self) -> None:
        self.set_rectangle(None)

    def set_rectangle(
        self,
        rect: PDRectangle | tuple[float, float, float, float] | None,
    ) -> None:
        if rect is None:
            self._annot.remove_item(_RECT)
            return
        if isinstance(rect, PDRectangle):
            self._annot.set_item(_RECT, rect.to_cos_array())
            return
        arr = COSArray()
        for v in rect:
            arr.add(COSFloat(float(v)))
        self._annot.set_item(_RECT, arr)

    # ---------- /C colour (3-element RGB float array) ----------

    def get_color(self) -> ColorTuple | None:
        return self._get_color(_C)

    def _get_color(self, color_name: COSName) -> ColorTuple | None:
        v = self._annot.get_dictionary_object(color_name)
        if isinstance(v, COSArray) and len(v) >= 3:
            values = _float_values(v, 3)
            if values is not None:
                return (values[0], values[1], values[2])
        return None

    def has_color(self) -> bool:
        return self.get_color() is not None

    def clear_color(self) -> None:
        self.set_color(None)

    def set_color(self, color: ColorTuple | None) -> None:
        if color is None:
            self._annot.remove_item(_C)
            return
        arr = COSArray()
        for v in color:
            arr.add(COSFloat(float(v)))
        self._annot.set_item(_C, arr)

    # ---------- /F flags ----------

    def get_flags(self) -> int:
        return self._annot.get_int(_F, 0)

    def has_flags(self) -> bool:
        return isinstance(self._annot.get_dictionary_object(_F), COSNumber)

    def clear_flags(self) -> None:
        self._annot.remove_item(_F)

    def set_flags(self, flags: int) -> None:
        self._annot.set_int(_F, flags)

    # ---------- individual flag accessors (upstream FDFAnnotation §FLAG_*) ----------

    def is_invisible(self) -> bool:
        return self._annot.get_flag(_F, _FLAG_INVISIBLE)

    def set_invisible(self, invisible: bool) -> None:
        self._annot.set_flag(_F, _FLAG_INVISIBLE, invisible)

    def is_hidden(self) -> bool:
        return self._annot.get_flag(_F, _FLAG_HIDDEN)

    def set_hidden(self, hidden: bool) -> None:
        self._annot.set_flag(_F, _FLAG_HIDDEN, hidden)

    def is_printed(self) -> bool:
        return self._annot.get_flag(_F, _FLAG_PRINTED)

    def set_printed(self, printed: bool) -> None:
        self._annot.set_flag(_F, _FLAG_PRINTED, printed)

    def is_no_zoom(self) -> bool:
        return self._annot.get_flag(_F, _FLAG_NO_ZOOM)

    def set_no_zoom(self, no_zoom: bool) -> None:
        self._annot.set_flag(_F, _FLAG_NO_ZOOM, no_zoom)

    def is_no_rotate(self) -> bool:
        return self._annot.get_flag(_F, _FLAG_NO_ROTATE)

    def set_no_rotate(self, no_rotate: bool) -> None:
        self._annot.set_flag(_F, _FLAG_NO_ROTATE, no_rotate)

    def is_no_view(self) -> bool:
        return self._annot.get_flag(_F, _FLAG_NO_VIEW)

    def set_no_view(self, no_view: bool) -> None:
        self._annot.set_flag(_F, _FLAG_NO_VIEW, no_view)

    def is_read_only(self) -> bool:
        return self._annot.get_flag(_F, _FLAG_READ_ONLY)

    def set_read_only(self, read_only: bool) -> None:
        self._annot.set_flag(_F, _FLAG_READ_ONLY, read_only)

    def is_locked(self) -> bool:
        return self._annot.get_flag(_F, _FLAG_LOCKED)

    def set_locked(self, locked: bool) -> None:
        self._annot.set_flag(_F, _FLAG_LOCKED, locked)

    def is_toggle_no_view(self) -> bool:
        return self._annot.get_flag(_F, _FLAG_TOGGLE_NO_VIEW)

    def set_toggle_no_view(self, toggle_no_view: bool) -> None:
        self._annot.set_flag(_F, _FLAG_TOGGLE_NO_VIEW, toggle_no_view)

    def is_locked_contents(self) -> bool:
        return self._annot.get_flag(_F, _FLAG_LOCKED_CONTENTS)

    def set_locked_contents(self, locked_contents: bool) -> None:
        self._annot.set_flag(_F, _FLAG_LOCKED_CONTENTS, locked_contents)

    # ---------- /Name (icon name etc.) ----------

    def get_name_attribute(self) -> str | None:
        v = self._annot.get_dictionary_object(_NAME)
        if isinstance(v, COSName):
            return v.name
        return None

    def has_name_attribute(self) -> bool:
        return self.get_name_attribute() is not None

    def clear_name_attribute(self) -> None:
        self.set_name_attribute(None)

    def set_name_attribute(self, name: str | None) -> None:
        if name is None:
            self._annot.remove_item(_NAME)
        else:
            self._annot.set_item(_NAME, COSName.get_pdf_name(name))

    # ---------- /M modified date (string) ----------

    def get_date(self) -> str | None:
        """Modification date string (``/M`` entry).

        Mirrors upstream ``getDate()`` which returns the raw string form.
        """
        return self._annot.get_string(_M)

    def set_date(self, date: str | None) -> None:
        self._annot.set_string(_M, date)

    # Pythonic aliases retained for the existing API surface.
    def get_modified_date(self) -> str | None:
        return self.get_date()

    def has_modified_date(self) -> bool:
        return self.get_date() is not None

    def clear_modified_date(self) -> None:
        self.set_date(None)

    def set_modified_date(self, date: str | None) -> None:
        self.set_date(date)

    # ---------- /CreationDate ----------

    def get_creation_date(self) -> _dt.datetime | None:
        """Return ``/CreationDate`` parsed as a timezone-aware datetime.

        Mirrors upstream ``getCreationDate()`` which returns ``Calendar``;
        the Python port returns :class:`datetime.datetime` per the project
        ``DateConverter`` convention.
        """
        raw = self._annot.get_string(_CREATION_DATE)
        if raw is None:
            return None
        from pypdfbox.xmpbox.date_converter import to_calendar

        return to_calendar(raw)

    def set_creation_date(
        self,
        date: _dt.date | _dt.datetime | str | None,
    ) -> None:
        self._annot.set_date(_CREATION_DATE, date)

    # ---------- /CA opacity ----------

    def get_opacity(self) -> float:
        """Return the opacity value, defaulting to 1.0 when /CA is absent."""
        return self._annot.get_float(_CA, 1.0)

    def set_opacity(self, opacity: float) -> None:
        self._annot.set_float(_CA, float(opacity))

    # ---------- /Subj subject ----------

    def get_subject(self) -> str | None:
        return self._annot.get_string(_SUBJ)

    def set_subject(self, subject: str | None) -> None:
        self._annot.set_string(_SUBJ, subject)

    # ---------- /IT intent ----------

    def get_intent(self) -> str | None:
        return self._annot.get_name_as_string(_IT)

    def set_intent(self, intent: str | None) -> None:
        self._annot.set_name(_IT, intent)

    # ---------- /RC rich contents ----------

    @staticmethod
    def rich_contents_to_string(node: object, root: bool = False) -> str:
        """Serialise an XML ``rich-text`` element back to a string.

        Mirrors upstream private
        ``FDFAnnotation.richContentsToString(Node, boolean)`` (line 998
        of ``FDFAnnotation.java``). Walks the node's children and
        re-emits Element / CDATA / Text nodes as XML, escaping ``&`` /
        ``<`` in text and ``"`` in attributes. When ``root`` is ``True``
        only the inner text is returned (matches the upstream contract
        where the outer ``<body>`` wrapper is stripped). Surfaced as a
        public static helper because pypdfbox callers occasionally
        round-trip RC payloads outside of the FDF parser pipeline.

        Accepts any ``xml.dom.minidom`` Node; returns ``""`` when the
        node has no children.
        """
        # Local imports keep the optional dependency on stdlib's xml.dom
        # confined to the call site.
        from xml.dom.minidom import CDATASection, Element, Text  # noqa: PLC0415

        parts: list[str] = []
        children = getattr(node, "childNodes", None) or []
        for child in children:
            if isinstance(child, Element):
                parts.append(FDFAnnotation.rich_contents_to_string(child, False))
            elif isinstance(child, CDATASection):
                parts.append("<![CDATA[")
                parts.append(child.data or "")
                parts.append("]]>")
            elif isinstance(child, Text):
                cdata = child.data
                if cdata is not None:
                    cdata = cdata.replace("&", "&amp;").replace("<", "&lt;")
                    parts.append(cdata)
        body = "".join(parts)
        if root:
            return body
        # Non-root: emit ``<tag attr="…">body</tag>``.
        attrs_text: list[str] = []
        attributes = getattr(node, "attributes", None)
        if attributes is not None:
            for i in range(attributes.length):
                attribute = attributes.item(i)
                value = attribute.nodeValue
                if value is not None:
                    value = value.replace('"', "&quot;")
                attrs_text.append(f' {attribute.nodeName}="{value}"')
        tag = node.nodeName
        return f"<{tag}{''.join(attrs_text)}>{body}</{tag}>"

    def get_rich_contents(self) -> str:
        """Return the rich-text contents stream, or an empty string.

        Mirrors upstream ``getRichContents()`` which delegates to
        ``getStringOrStream`` and returns ``""`` for missing/unknown shapes.
        """
        return self.get_string_or_stream(self._annot.get_dictionary_object(_RC))

    def set_rich_contents(self, rc: str | None) -> None:
        if rc is None:
            self._annot.remove_item(_RC)
            return
        self._annot.set_item(_RC, COSString(rc))

    # ---------- /BS border style ----------

    def get_border_style(self) -> PDBorderStyleDictionary | None:
        bs = self._annot.get_cos_dictionary(_BS)
        return PDBorderStyleDictionary(bs) if bs is not None else None

    def set_border_style(self, bs: PDBorderStyleDictionary | None) -> None:
        if bs is None:
            self._annot.remove_item(_BS)
            return
        self._annot.set_item(_BS, bs.get_cos_object())

    # ---------- /BE border effect ----------

    def get_border_effect(self) -> PDBorderEffectDictionary | None:
        be = self._annot.get_cos_dictionary(_BE)
        return PDBorderEffectDictionary(be) if be is not None else None

    def set_border_effect(self, be: PDBorderEffectDictionary | None) -> None:
        if be is None:
            self._annot.remove_item(_BE)
            return
        self._annot.set_item(_BE, be.get_cos_object())

    # ---------- protected helpers ----------

    def get_string_or_stream(self, base: COSBase | None) -> str:
        """Return text from a COSString or COSStream entry, else empty string.

        Mirrors upstream ``protected final String getStringOrStream(COSBase)``.
        """
        if base is None:
            return ""
        if isinstance(base, COSString):
            return base.get_string()
        if isinstance(base, COSStream):
            return base.to_text_string()
        return ""

    def parse_rectangle_attributes(self, rect: str, error_message: str) -> list[float]:
        """Parse a comma-separated 4-float ``rect`` attribute.

        Mirrors upstream ``final float[] parseRectangleAttributes(String, String)``.
        Raises :class:`OSError` (Python equivalent of Java ``IOException``) when
        the input is not exactly four floats.
        """
        if rect is None:
            raise OSError(error_message)
        rect_values = rect.split(",")
        if len(rect_values) != 4:
            raise OSError(error_message)
        try:
            return [float(v) for v in rect_values]
        except ValueError as exc:
            raise OSError(error_message) from exc

    def parse_floats(self, src_values: list[str]) -> list[float]:
        """Parse a list of decimal-string values into floats.

        Mirrors upstream ``final float[] parseFloats(String[])``.
        """
        return [float(v) for v in src_values]

    def create_rectangle_from_attributes(
        self, rect: str, error_message: str
    ) -> PDRectangle:
        """Build a :class:`PDRectangle` from a comma-separated attribute.

        Mirrors upstream
        ``final PDRectangle createRectangleFromAttributes(String, String)``.
        """
        values = self.parse_rectangle_attributes(rect, error_message)
        rectangle = PDRectangle()
        rectangle.set_lower_left_x(values[0])
        rectangle.set_lower_left_y(values[1])
        rectangle.set_upper_right_x(values[2])
        rectangle.set_upper_right_y(values[3])
        return rectangle

    # ---------- factory ----------

    @classmethod
    def create(cls, annot: COSDictionary) -> FDFAnnotation:
        """Dispatch to the concrete ``FDFAnnotation`` subtype based on
        ``/Subtype``. Mirrors ``FDFAnnotation.create(COSDictionary)`` upstream.

        Falls back to the bare ``FDFAnnotation`` base when the subtype is
        unknown or absent so callers always receive a usable wrapper.
        """
        sub = annot.get_dictionary_object(_SUBTYPE)
        name = sub.name if isinstance(sub, COSName) else None

        # Lazy-import to avoid an import cycle: subtypes import this module.
        if name == "Text":
            from .fdf_annotation_text import FDFAnnotationText

            return FDFAnnotationText(annot)
        if name == "FreeText":
            from .fdf_annotation_free_text import FDFAnnotationFreeText

            return FDFAnnotationFreeText(annot)
        if name == "FileAttachment":
            from .fdf_annotation_file_attachment import FDFAnnotationFileAttachment

            return FDFAnnotationFileAttachment(annot)
        if name == "Square":
            from .fdf_annotation_square import FDFAnnotationSquare

            return FDFAnnotationSquare(annot)
        if name == "Circle":
            from .fdf_annotation_circle import FDFAnnotationCircle

            return FDFAnnotationCircle(annot)
        if name == "Line":
            from .fdf_annotation_line import FDFAnnotationLine

            return FDFAnnotationLine(annot)
        if name == "Polygon":
            from .fdf_annotation_polygon import FDFAnnotationPolygon

            return FDFAnnotationPolygon(annot)
        if name in ("PolyLine", "Polyline"):
            from .fdf_annotation_polyline import FDFAnnotationPolyline

            return FDFAnnotationPolyline(annot)
        if name == "Ink":
            from .fdf_annotation_ink import FDFAnnotationInk

            return FDFAnnotationInk(annot)
        if name == "Stamp":
            from .fdf_annotation_stamp import FDFAnnotationStamp

            return FDFAnnotationStamp(annot)
        if name == "Caret":
            from .fdf_annotation_caret import FDFAnnotationCaret

            return FDFAnnotationCaret(annot)
        if name in ("Highlight", "Underline", "StrikeOut", "Squiggly"):
            from .fdf_annotation_text_markup import FDFAnnotationTextMarkup

            return FDFAnnotationTextMarkup(annot)
        return cls(annot)


def _float_values(array: COSArray, size: int) -> tuple[float, ...] | None:
    values: list[float] = []
    for index in range(size):
        value = array.get_object(index)
        if not isinstance(value, COSNumber):
            return None
        values.append(value.float_value())
    return tuple(values)
