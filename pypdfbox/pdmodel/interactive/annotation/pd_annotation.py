from __future__ import annotations

import datetime as _dt
from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)

from ...pd_rectangle import PDRectangle

if TYPE_CHECKING:
    from ...graphics.pd_property_list import PDPropertyList
    from ...pd_document import PDDocument
    from .pd_appearance_dictionary import PDAppearanceDictionary


# Names referenced by PDAnnotation. Several are only relevant to subclasses
# but they live on the base wrapper so the dispatch table can read /Subtype
# without round-tripping through a subclass first.
_TYPE: COSName = COSName.get_pdf_name("Type")
_ANNOT: COSName = COSName.get_pdf_name("Annot")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_RECT: COSName = COSName.get_pdf_name("Rect")
_CONTENTS: COSName = COSName.get_pdf_name("Contents")
_M: COSName = COSName.get_pdf_name("M")
_F: COSName = COSName.get_pdf_name("F")
_NM: COSName = COSName.get_pdf_name("NM")
_T: COSName = COSName.get_pdf_name("T")
_BORDER: COSName = COSName.get_pdf_name("Border")
_C: COSName = COSName.get_pdf_name("C")
_AP: COSName = COSName.get_pdf_name("AP")
_AS: COSName = COSName.get_pdf_name("AS")
_P: COSName = COSName.get_pdf_name("P")
_STRUCT_PARENT: COSName = COSName.get_pdf_name("StructParent")
_OC: COSName = COSName.get_pdf_name("OC")


class PDAnnotation:
    """
    Abstract base for PDF annotations. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation``.

    Annotation dictionaries always carry ``/Type /Annot`` and a
    ``/Subtype`` that identifies the concrete annotation class. Use
    :meth:`create` to dispatch a raw ``COSDictionary`` to the right
    subclass.

    pdmodel cluster #5 lite ships only the base + Link, Text, Square,
    Circle, Unknown subclasses. Heavy subclasses (Widget for forms,
    FreeText with appearance streams, etc.) are deferred — the factory
    falls back to :class:`PDAnnotationUnknown` for any subtype the
    truncated dispatch table doesn't recognise.
    """

    # ---------- /F flag bits (PDF 32000-1:2008 Table 165) ----------

    FLAG_INVISIBLE: int = 1 << 0
    FLAG_HIDDEN: int = 1 << 1
    FLAG_PRINTED: int = 1 << 2
    FLAG_NO_ZOOM: int = 1 << 3
    FLAG_NO_ROTATE: int = 1 << 4
    FLAG_NO_VIEW: int = 1 << 5
    FLAG_READ_ONLY: int = 1 << 6
    FLAG_LOCKED: int = 1 << 7
    FLAG_TOGGLE_NO_VIEW: int = 1 << 8
    FLAG_LOCKED_CONTENTS: int = 1 << 9

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        if annotation_dict is None:
            self._dict = COSDictionary()
            self._dict.set_item(_TYPE, _ANNOT)
        else:
            if not isinstance(annotation_dict, COSDictionary):
                raise TypeError(
                    "PDAnnotation requires a COSDictionary or None; got "
                    f"{type(annotation_dict).__name__}"
                )
            self._dict = annotation_dict
            # Mirror upstream PDAnnotation(COSDictionary): if the dict
            # has no /Type entry, default it to /Annot. Existing /Type
            # values that aren't /Annot are left alone (upstream just
            # logs a warning and proceeds).
            existing_type = self._dict.get_dictionary_object(_TYPE)
            if existing_type is None:
                self._dict.set_item(_TYPE, _ANNOT)

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Subtype ----------

    def get_subtype(self) -> str | None:
        return self._dict.get_name(_SUBTYPE)

    def set_subtype(self, subtype: str | None) -> None:
        """Public ``/Subtype`` setter. Upstream PDFBox keeps this protected
        but exposing it here is harmless and useful for callers that want
        to repurpose a base wrapper around an existing dictionary."""
        if subtype is None:
            self._dict.remove_item(_SUBTYPE)
            return
        self._dict.set_item(_SUBTYPE, COSName.get_pdf_name(subtype))

    def _set_subtype(self, subtype: str) -> None:
        """Protected upstream — subclasses set this in their constructor."""
        self._dict.set_item(_SUBTYPE, COSName.get_pdf_name(subtype))

    # ---------- factory ----------

    @staticmethod
    def create_annotation(base: COSBase) -> PDAnnotation:
        """Upstream-named factory mirroring Java's static
        :code:`createAnnotation(COSBase)`.

        Identical behaviour to :meth:`create` except it raises
        :class:`OSError` (the mapping for upstream :code:`IOException`)
        when ``base`` is not a :class:`COSDictionary`. Upstream throws
        ``IOException("Error: Unknown annotation type ...")`` in that
        case; we follow the same shape so call-sites that check for
        I/O-style failures still work."""
        if not isinstance(base, COSDictionary):
            raise OSError(
                f"Error: Unknown annotation type {type(base).__name__}"
            )
        return PDAnnotation.create(base)

    @staticmethod
    def create(cos_dict: COSBase) -> PDAnnotation:
        """Dispatch a raw annotation dict to the appropriate subclass.

        Mirrors upstream's static ``createAnnotation``. Subtypes the
        cluster #5 lite truncated table doesn't recognise (Widget, FreeText,
        FileAttachment, Line, Popup, RubberStamp, Polygon, Polyline, Ink,
        Highlight, Underline, Strikeout, Squiggly, Caret, Sound, …) all fall
        back to :class:`PDAnnotationUnknown` rather than raising — a parser
        round-trip should never lose data.
        """
        if not isinstance(cos_dict, COSDictionary):
            raise TypeError(
                f"PDAnnotation.create expects a COSDictionary, got "
                f"{type(cos_dict).__name__}"
            )
        # Local imports avoid a circular import at module-load time.
        from .pd_annotation_caret import PDAnnotationCaret
        from .pd_annotation_file_attachment import PDAnnotationFileAttachment
        from .pd_annotation_free_text import PDAnnotationFreeText
        from .pd_annotation_highlight import PDAnnotationHighlight
        from .pd_annotation_ink import PDAnnotationInk
        from .pd_annotation_line import PDAnnotationLine
        from .pd_annotation_link import PDAnnotationLink
        from .pd_annotation_movie import PDAnnotationMovie
        from .pd_annotation_polygon import PDAnnotationPolygon
        from .pd_annotation_polyline import PDAnnotationPolyline
        from .pd_annotation_popup import PDAnnotationPopup
        from .pd_annotation_printer_mark import PDAnnotationPrinterMark
        from .pd_annotation_redact import PDAnnotationRedact
        from .pd_annotation_rubber_stamp import PDAnnotationRubberStamp
        from .pd_annotation_screen import PDAnnotationScreen
        from .pd_annotation_sound import PDAnnotationSound
        from .pd_annotation_square_circle import (
            PDAnnotationCircle,
            PDAnnotationSquare,
        )
        from .pd_annotation_squiggly import PDAnnotationSquiggly
        from .pd_annotation_strikeout import PDAnnotationStrikeout
        from .pd_annotation_text import PDAnnotationText
        from .pd_annotation_three_d import PDAnnotation3D
        from .pd_annotation_trap_net import PDAnnotationTrapNet
        from .pd_annotation_underline import PDAnnotationUnderline
        from .pd_annotation_unknown import PDAnnotationUnknown
        from .pd_annotation_watermark import PDAnnotationWatermark
        from .pd_annotation_widget import PDAnnotationWidget

        subtype = cos_dict.get_name(_SUBTYPE)
        if subtype is None:
            return PDAnnotationUnknown(cos_dict)
        if subtype == PDAnnotationLink.SUB_TYPE:
            return PDAnnotationLink(cos_dict)
        if subtype == PDAnnotationText.SUB_TYPE:
            return PDAnnotationText(cos_dict)
        if subtype == PDAnnotationSquare.SUB_TYPE:
            return PDAnnotationSquare(cos_dict)
        if subtype == PDAnnotationCircle.SUB_TYPE:
            return PDAnnotationCircle(cos_dict)
        if subtype == PDAnnotationWidget.SUB_TYPE:
            return PDAnnotationWidget(cos_dict)
        if subtype == PDAnnotationLine.SUB_TYPE:
            return PDAnnotationLine(cos_dict)
        if subtype == PDAnnotationFreeText.SUB_TYPE:
            return PDAnnotationFreeText(cos_dict)
        if subtype == PDAnnotationFileAttachment.SUB_TYPE:
            return PDAnnotationFileAttachment(cos_dict)
        if subtype == PDAnnotationRubberStamp.SUB_TYPE:
            return PDAnnotationRubberStamp(cos_dict)
        if subtype == PDAnnotationPopup.SUB_TYPE:
            return PDAnnotationPopup(cos_dict)
        if subtype == PDAnnotationHighlight.SUB_TYPE:
            return PDAnnotationHighlight(cos_dict)
        if subtype == PDAnnotationUnderline.SUB_TYPE:
            return PDAnnotationUnderline(cos_dict)
        if subtype == PDAnnotationStrikeout.SUB_TYPE:
            return PDAnnotationStrikeout(cos_dict)
        if subtype == PDAnnotationSquiggly.SUB_TYPE:
            return PDAnnotationSquiggly(cos_dict)
        if subtype == PDAnnotationCaret.SUB_TYPE:
            return PDAnnotationCaret(cos_dict)
        if subtype == PDAnnotationInk.SUB_TYPE:
            return PDAnnotationInk(cos_dict)
        if subtype == PDAnnotationPolygon.SUB_TYPE:
            return PDAnnotationPolygon(cos_dict)
        if subtype == PDAnnotationPolyline.SUB_TYPE:
            return PDAnnotationPolyline(cos_dict)
        if subtype == PDAnnotationMovie.SUB_TYPE:
            return PDAnnotationMovie(cos_dict)
        if subtype == PDAnnotationSound.SUB_TYPE:
            return PDAnnotationSound(cos_dict)
        if subtype == PDAnnotationScreen.SUB_TYPE:
            return PDAnnotationScreen(cos_dict)
        if subtype == PDAnnotationRedact.SUB_TYPE:
            return PDAnnotationRedact(cos_dict)
        if subtype == PDAnnotation3D.SUB_TYPE:
            return PDAnnotation3D(cos_dict)
        if subtype == PDAnnotationWatermark.SUB_TYPE:
            return PDAnnotationWatermark(cos_dict)
        if subtype == PDAnnotationPrinterMark.SUB_TYPE:
            return PDAnnotationPrinterMark(cos_dict)
        if subtype == PDAnnotationTrapNet.SUB_TYPE:
            return PDAnnotationTrapNet(cos_dict)
        return PDAnnotationUnknown(cos_dict)

    # ---------- /Rect ----------

    def get_rectangle(self) -> PDRectangle | None:
        value = self._dict.get_dictionary_object(_RECT)
        if isinstance(value, COSArray) and value.size() >= 4:
            return PDRectangle.from_cos_array(value)
        return None

    def set_rectangle(self, rectangle: PDRectangle | None) -> None:
        if rectangle is None:
            self._dict.remove_item(_RECT)
            return
        self._dict.set_item(_RECT, rectangle.to_cos_array())

    def get_rect(self) -> PDRectangle | None:
        """Alias for :meth:`get_rectangle`. Some upstream call-sites use the
        shorter ``getRect`` form even though the canonical method is
        ``getRectangle``."""
        return self.get_rectangle()

    def has_rectangle(self) -> bool:
        """Predicate: is a parsable ``/Rect`` entry present?

        No upstream equivalent — useful for callers that want to test
        for a rectangle without forcing a :class:`PDRectangle`
        construction. Mirrors the ``getRectangle() != null`` idiom."""
        return self.get_rectangle() is not None

    def has_contents(self) -> bool:
        """Predicate: is a non-empty ``/Contents`` string present?

        No upstream equivalent — saves callers an extra null/empty
        check."""
        contents = self.get_contents()
        return contents is not None and contents != ""

    # ---------- /Contents ----------

    def get_contents(self) -> str | None:
        return self._dict.get_string(_CONTENTS)

    def set_contents(self, value: str | None) -> None:
        self._dict.set_string(_CONTENTS, value)

    # ---------- /M (modification date) ----------

    def get_modified_date(self) -> str | None:
        """Return the raw /M string. Upstream returns the unparsed string;
        callers run it through DateConverter when they need a structured
        value. We follow that — date parsing already lives in
        ``pd_document_information`` and we don't duplicate it here."""
        return self._dict.get_string(_M)

    def set_modified_date(self, value: str | _dt.datetime | None) -> None:
        if value is None:
            self._dict.remove_item(_M)
            return
        if isinstance(value, _dt.datetime):
            # Match the format used by PDDocumentInformation.
            base = value.strftime("D:%Y%m%d%H%M%S")
            offset = value.utcoffset()
            if offset is None or int(offset.total_seconds()) == 0:
                formatted = base + "Z00'00'"
            else:
                total_seconds = int(offset.total_seconds())
                sign = "+" if total_seconds > 0 else "-"
                total_seconds = abs(total_seconds)
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                formatted = f"{base}{sign}{hours:02d}'{minutes:02d}'"
            self._dict.set_item(_M, COSString(formatted))
            return
        self._dict.set_string(_M, value)

    # ---------- /F (annotation flags) ----------

    def get_annotation_flags(self) -> int:
        return self._dict.get_int(_F, 0)

    def set_annotation_flags(self, flags: int) -> None:
        self._dict.set_int(_F, int(flags))

    def _is_flag(self, flag: int) -> bool:
        return (self.get_annotation_flags() & flag) == flag

    def _set_flag(self, flag: int, value: bool) -> None:
        current = self.get_annotation_flags()
        new = current | flag if value else current & ~flag
        self.set_annotation_flags(new)

    def is_invisible(self) -> bool:
        return self._is_flag(self.FLAG_INVISIBLE)

    def set_invisible(self, value: bool) -> None:
        self._set_flag(self.FLAG_INVISIBLE, value)

    def is_hidden(self) -> bool:
        return self._is_flag(self.FLAG_HIDDEN)

    def set_hidden(self, value: bool) -> None:
        self._set_flag(self.FLAG_HIDDEN, value)

    def is_printed(self) -> bool:
        return self._is_flag(self.FLAG_PRINTED)

    def set_printed(self, value: bool) -> None:
        self._set_flag(self.FLAG_PRINTED, value)

    def is_no_zoom(self) -> bool:
        return self._is_flag(self.FLAG_NO_ZOOM)

    def set_no_zoom(self, value: bool) -> None:
        self._set_flag(self.FLAG_NO_ZOOM, value)

    def is_no_rotate(self) -> bool:
        return self._is_flag(self.FLAG_NO_ROTATE)

    def set_no_rotate(self, value: bool) -> None:
        self._set_flag(self.FLAG_NO_ROTATE, value)

    def is_no_view(self) -> bool:
        return self._is_flag(self.FLAG_NO_VIEW)

    def set_no_view(self, value: bool) -> None:
        self._set_flag(self.FLAG_NO_VIEW, value)

    def is_read_only(self) -> bool:
        return self._is_flag(self.FLAG_READ_ONLY)

    def set_read_only(self, value: bool) -> None:
        self._set_flag(self.FLAG_READ_ONLY, value)

    def is_locked(self) -> bool:
        return self._is_flag(self.FLAG_LOCKED)

    def set_locked(self, value: bool) -> None:
        self._set_flag(self.FLAG_LOCKED, value)

    def is_toggle_no_view(self) -> bool:
        return self._is_flag(self.FLAG_TOGGLE_NO_VIEW)

    def set_toggle_no_view(self, value: bool) -> None:
        self._set_flag(self.FLAG_TOGGLE_NO_VIEW, value)

    def is_locked_contents(self) -> bool:
        return self._is_flag(self.FLAG_LOCKED_CONTENTS)

    def set_locked_contents(self, value: bool) -> None:
        self._set_flag(self.FLAG_LOCKED_CONTENTS, value)

    # ---------- /NM (annotation name) ----------

    def get_annotation_name(self) -> str | None:
        return self._dict.get_string(_NM)

    def set_annotation_name(self, value: str | None) -> None:
        self._dict.set_string(_NM, value)

    # ---------- /T (text label / title) ----------

    def get_title_popup(self) -> str | None:
        """Upstream calls this ``getTitlePopup`` on PDAnnotationMarkup. The
        cluster #5 lite scope hasn't ported PDAnnotationMarkup yet, but /T
        is a generic-enough field that base-class accessors are useful for
        Link/Text/Square/Circle round-trips."""
        return self._dict.get_string(_T)

    def set_title_popup(self, value: str | None) -> None:
        self._dict.set_string(_T, value)

    # ---------- /Border ----------

    def get_border(self) -> COSArray:
        """Default /Border is ``[0 0 1]`` per spec — match upstream which
        synthesises the default rather than returning ``null``.

        When the stored array has fewer than three elements, mirror
        upstream behaviour (Adobe Reader treats missing entries as 0):
        copy the array (so we don't mutate the persisted PDF) and pad
        with ``COSInteger.ZERO`` until it has three elements."""
        value = self._dict.get_dictionary_object(_BORDER)
        if isinstance(value, COSArray):
            if value.size() < 3:
                padded = COSArray()
                for i in range(value.size()):
                    padded.add(value.get(i))
                while padded.size() < 3:
                    padded.add(COSInteger.get(0))
                return padded
            return value
        default = COSArray(
            [COSInteger.get(0), COSInteger.get(0), COSInteger.get(1)]
        )
        return default

    def set_border(self, border_array: COSArray | None) -> None:
        if border_array is None:
            self._dict.remove_item(_BORDER)
            return
        self._dict.set_item(_BORDER, border_array)

    # ---------- /C (color components) ----------

    def get_color(self) -> COSArray | None:
        """Cluster #5 lite returns the raw ``COSArray`` of color components.
        The typed PDColor wrapper lands with the rendering cluster (PRD
        §6.12). See ``CHANGES.md``."""
        value = self._dict.get_dictionary_object(_C)
        if isinstance(value, COSArray):
            return value
        return None

    def set_color(
        self,
        color: COSArray | list[float] | tuple[float, ...] | object | None,
    ) -> None:
        """Set ``/C``. Accepts ``None`` to clear, a raw ``COSArray``, a
        sequence of floats, or a typed :class:`PDColor` (any object
        exposing :meth:`to_cos_array`).

        Mirrors upstream :code:`setColor(PDColor)` while keeping the
        looser pypdfbox surface that predates the rendering cluster — see
        ``CHANGES.md``."""
        if color is None:
            self._dict.remove_item(_C)
            return
        if isinstance(color, COSArray):
            self._dict.set_item(_C, color)
            return
        if isinstance(color, (list, tuple)):
            self._dict.set_item(
                _C, COSArray([COSFloat(float(c)) for c in color])
            )
            return
        # Duck-typed PDColor support — any object exposing
        # ``to_cos_array()`` (the canonical PDColor serializer) is
        # accepted to avoid pulling the rendering cluster into the
        # annotation import graph.
        to_cos_array = getattr(color, "to_cos_array", None)
        if callable(to_cos_array):
            value = to_cos_array()
            if isinstance(value, COSArray):
                self._dict.set_item(_C, value)
                return
        raise TypeError(
            "set_color expects None, COSArray, list, tuple, or PDColor; "
            f"got {type(color).__name__}"
        )

    def has_color(self) -> bool:
        """Predicate: is a ``/C`` color array present?

        No upstream equivalent — saves callers from writing the
        ``get_color() is not None`` boilerplate."""
        return self.get_color() is not None

    def _get_color(self, item_name: COSName) -> COSArray | None:
        """Protected helper mirroring upstream
        :code:`protected PDColor getColor(COSName itemName)` (Java line
        811).

        Returns the raw color ``COSArray`` for a given dictionary entry
        (typically ``/C`` for stroke or ``/IC`` for interior color on
        markup annotations), or ``None`` when absent. Cluster #5 lite
        returns the bare array — the typed PDColor wrapper lands with
        the rendering cluster (see ``CHANGES.md`` and the divergence
        note on :meth:`get_color`).

        Subclasses such as ``PDAnnotationMarkup`` use this to expose
        ``getInteriorColor()`` / ``getColor()`` over their own keys
        without duplicating the lookup logic."""
        value = self._dict.get_dictionary_object(item_name)
        if isinstance(value, COSArray):
            return value
        return None

    def set_color_components(self, components: list[float] | tuple[float, ...]) -> None:
        """Convenience alternative to ``set_color`` taking raw floats — no
        upstream equivalent (upstream takes a ``PDColor``). Useful before
        the rendering cluster lands."""
        arr = COSArray([COSFloat(float(c)) for c in components])
        self._dict.set_item(_C, arr)

    # ---------- /AP (appearance dictionary) ----------

    def get_appearance_dictionary(self) -> PDAppearanceDictionary | None:
        from .pd_appearance_dictionary import PDAppearanceDictionary

        value = self._dict.get_dictionary_object(_AP)
        if isinstance(value, COSDictionary):
            return PDAppearanceDictionary(value)
        return None

    def set_appearance_dictionary(
        self, ap: PDAppearanceDictionary | COSDictionary | None
    ) -> None:
        if ap is None:
            self._dict.remove_item(_AP)
            return
        self._dict.set_item(
            _AP,
            ap.get_cos_object() if hasattr(ap, "get_cos_object") else ap,
        )

    def get_appearance(self) -> PDAppearanceDictionary | None:
        """Upstream-canonical alias for :meth:`get_appearance_dictionary`.

        Java :code:`PDAnnotation.getAppearance()` is the canonical name
        upstream; ``get_appearance_dictionary`` is the historical pypdfbox
        spelling. Both are supported."""
        return self.get_appearance_dictionary()

    def set_appearance(
        self, ap: PDAppearanceDictionary | COSDictionary | None
    ) -> None:
        """Upstream-canonical alias for :meth:`set_appearance_dictionary`.

        Mirrors :code:`PDAnnotation.setAppearance(PDAppearanceDictionary)`
        upstream."""
        self.set_appearance_dictionary(ap)

    def has_appearance(self) -> bool:
        """Predicate: is an ``/AP`` entry present and a dictionary?

        No upstream equivalent — useful for callers that want to check
        the presence of an appearance without forcing a typed wrapper
        construction."""
        value = self._dict.get_dictionary_object(_AP)
        return isinstance(value, COSDictionary)

    def get_normal_appearance_stream(self):  # type: ignore[no-untyped-def]
        """Return the active normal appearance stream, if any.

        Mirrors upstream :code:`PDAnnotation.getNormalAppearanceStream()`:
        looks up the ``/AP /N`` entry, then either returns the direct
        appearance stream or — when ``/N`` is a state-mapped
        subdictionary — looks up the entry keyed by the current
        ``/AS`` state name. Returns ``None`` when ``/AP`` is absent,
        ``/N`` is missing, or the resolved entry is not a stream.

        Return type is :class:`PDAppearanceStream | None` but the
        annotation un-stringified to keep the import graph local."""
        appearance_dict = self.get_appearance_dictionary()
        if appearance_dict is None:
            return None
        normal = appearance_dict.get_normal_appearance()
        if normal is None:
            return None
        if normal.is_sub_dictionary():
            state = self.get_appearance_state()
            sub = normal.get_sub_dictionary()
            if state is None:
                return None
            return sub.get(state)
        return normal.get_appearance_stream()

    # ---------- /AS (appearance state) ----------

    def get_appearance_state(self) -> str | None:
        """Return the active appearance state name (``/AS``) — used together
        with state-based ``/AP /N`` subdictionaries (checkbox on/off,
        radio button selected, …). ``None`` when absent."""
        return self._dict.get_name(_AS)

    def set_appearance_state(self, value: str | COSName | None) -> None:
        """Set the active appearance state name (``/AS``).

        Mirrors upstream's two overloads — ``setAppearanceState(String)``
        and ``setAppearanceState(COSName)`` — by accepting either a
        string or a pre-built :class:`COSName`. Pass ``None`` to clear."""
        if value is None:
            self._dict.remove_item(_AS)
            return
        if isinstance(value, COSName):
            self._dict.set_item(_AS, value)
            return
        self._dict.set_item(_AS, COSName.get_pdf_name(value))

    # ---------- /P (parent page back-pointer) ----------

    def get_p(self) -> COSDictionary | None:
        """Return the raw ``/P`` page-dictionary back-pointer.

        Upstream returns a ``PDPage``; we return the raw ``COSDictionary``
        here to avoid pulling ``PDPage`` into the import graph of every
        annotation. Callers that want a typed wrapper can call
        ``PDPage(get_p())``."""
        value = self._dict.get_dictionary_object(_P)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_p(self, page: object) -> None:
        """Set the ``/P`` parent page back-pointer.

        Accepts ``None``, a ``COSDictionary``, or any object exposing
        ``get_cos_object()`` (e.g. a ``PDPage``)."""
        if page is None:
            self._dict.remove_item(_P)
            return
        if isinstance(page, COSDictionary):
            self._dict.set_item(_P, page)
            return
        if hasattr(page, "get_cos_object"):
            cos = page.get_cos_object()
            if not isinstance(cos, COSDictionary):
                raise TypeError(
                    "set_p expects a page whose COS object is a "
                    "COSDictionary"
                )
            self._dict.set_item(_P, cos)
            return
        raise TypeError(
            "set_p expects None, COSDictionary, or an object with "
            f"get_cos_object(); got {type(page).__name__}"
        )

    def get_page(self) -> COSDictionary | None:
        """Upstream-named accessor for the parent page back-pointer.

        Java's :code:`PDAnnotation.getPage()` returns a ``PDPage``; we
        return the raw ``COSDictionary`` to keep ``PDPage`` out of every
        annotation's import graph. Callers that want a typed wrapper can
        construct ``PDPage(get_page())`` themselves."""
        return self.get_p()

    def set_page(self, page: object) -> None:
        """Upstream-named setter for the parent page back-pointer.

        Mirrors :code:`PDAnnotation.setPage(PDPage)` upstream. Delegates
        to :meth:`set_p` for the actual write."""
        self.set_p(page)

    # ---------- /StructParent ----------

    def get_struct_parent(self) -> int:
        """Return the ``/StructParent`` integer key into the structure
        parent tree. Default ``-1`` when absent (mirrors upstream)."""
        return self._dict.get_int(_STRUCT_PARENT, -1)

    def set_struct_parent(self, value: int) -> None:
        self._dict.set_int(_STRUCT_PARENT, int(value))

    # ---------- /OC (optional content) ----------

    def get_optional_content(self) -> PDPropertyList | None:
        """Return the ``/OC`` optional content dictionary as a typed
        :class:`PDPropertyList` (PDOptionalContentGroup or
        PDOptionalContentMembershipDictionary). ``None`` when absent or
        unrecognised."""
        from ...graphics.pd_property_list import PDPropertyList

        value = self._dict.get_dictionary_object(_OC)
        if isinstance(value, COSDictionary):
            return PDPropertyList.create(value)
        return None

    def set_optional_content(
        self, oc: PDPropertyList | COSDictionary | None
    ) -> None:
        if oc is None:
            self._dict.remove_item(_OC)
            return
        if isinstance(oc, COSDictionary):
            self._dict.set_item(_OC, oc)
            return
        if hasattr(oc, "get_cos_object"):
            cos = oc.get_cos_object()
            if not isinstance(cos, COSDictionary):
                raise TypeError(
                    "set_optional_content expects a COSDictionary-backed "
                    "PDPropertyList"
                )
            self._dict.set_item(_OC, cos)
            return
        raise TypeError(
            "set_optional_content expects None, COSDictionary, or "
            f"PDPropertyList; got {type(oc).__name__}"
        )

    # ---------- appearance construction ----------

    def construct_appearances(self, document: PDDocument | None = None) -> None:
        """Create appearance entries for this annotation.

        Mirrors upstream ``constructAppearances()`` and
        ``constructAppearances(PDDocument)``. The base implementation is a
        no-op; subclasses with concrete appearance handlers override it.
        """
        return None

    # ---------- equality / repr ----------

    def equals(self, other: object) -> bool:
        """Upstream-named equality.

        Mirrors Java :code:`PDAnnotation.equals(Object)`: two annotations
        are equal when they wrap the same backing :class:`COSDictionary`
        (upstream invokes :code:`COSDictionary.equals` which falls back
        to ``Object.equals``, i.e. reference identity, since we don't
        override dict equality)."""
        if other is self:
            return True
        if not isinstance(other, PDAnnotation):
            return False
        return other._dict is self._dict

    def hash_code(self) -> int:
        """Upstream-named hash mirror of :meth:`__hash__`.

        Java :code:`PDAnnotation.hashCode()` returns
        :code:`Objects.hash(dictionary)`; we hash the dict identity
        for the same one-bucket-per-instance behaviour."""
        return self.__hash__()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PDAnnotation):
            return self._dict is other._dict
        return NotImplemented

    def __hash__(self) -> int:
        return id(self._dict)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(subtype={self.get_subtype()!r})"


__all__ = ["PDAnnotation"]
