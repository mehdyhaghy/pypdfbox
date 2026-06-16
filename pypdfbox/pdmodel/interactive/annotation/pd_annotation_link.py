from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSName,
    COSString,
)

from .pd_annotation import PDAnnotation

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.action import PDAction
    from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
        PDDestination,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument

    from .handlers.pd_appearance_handler import PDAppearanceHandler
    from .pd_border_style_dictionary import PDBorderStyleDictionary

_A: COSName = COSName.get_pdf_name("A")
_DEST: COSName = COSName.get_pdf_name("Dest")
_H: COSName = COSName.get_pdf_name("H")
_BS: COSName = COSName.get_pdf_name("BS")
_PA: COSName = COSName.get_pdf_name("PA")
_QUAD_POINTS: COSName = COSName.get_pdf_name("QuadPoints")
_S: COSName = COSName.get_pdf_name("S")
_URI_NAME: COSName = COSName.get_pdf_name("URI")


class PDAnnotationLink(PDAnnotation):
    """
    Link annotation — ``/Subtype /Link``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink``.

    Either ``/A`` (action) or ``/Dest`` (destination) carries the target —
    not both, per PDF 32000-1:2008 §12.5.6.5 Table 173.
    """

    SUB_TYPE: str = "Link"

    HIGHLIGHT_MODE_NONE: str = "N"
    HIGHLIGHT_MODE_INVERT: str = "I"  # PDF spec default
    HIGHLIGHT_MODE_OUTLINE: str = "O"
    HIGHLIGHT_MODE_PUSH: str = "P"

    #: All four ``/H`` highlight-mode values defined by PDF 32000-1:2008
    #: §12.5.6.5 Table 173 — the values a conforming reader recognises.
    #: Non-standard ``/H`` values are permitted but their effect is
    #: reader-defined. Useful for validating ``/H`` against the spec set.
    STANDARD_HIGHLIGHT_MODES: frozenset[str] = frozenset(
        {
            HIGHLIGHT_MODE_NONE,
            HIGHLIGHT_MODE_INVERT,
            HIGHLIGHT_MODE_OUTLINE,
            HIGHLIGHT_MODE_PUSH,
        }
    )

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        self._custom_appearance_handler: PDAppearanceHandler | None = None
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /A (action) ----------

    def get_action(self) -> PDAction | None:
        from pypdfbox.pdmodel.interactive.action import PDAction

        value = self._dict.get_dictionary_object(_A)
        if isinstance(value, COSDictionary):
            return PDAction.create(value)
        return None

    def set_action(self, action: PDAction | COSDictionary | None) -> None:
        if action is None:
            self._dict.remove_item(_A)
            return
        self._dict.set_item(
            _A,
            action.get_cos_object() if hasattr(action, "get_cos_object") else action,
        )

    def has_action(self) -> bool:
        """Return ``True`` if ``/A`` is present and resolves to a dictionary.

        Cheaper than ``get_action() is not None`` because it skips the
        ``PDAction.create`` factory dispatch.
        """
        return isinstance(
            self._dict.get_dictionary_object(_A), COSDictionary
        )

    # ---------- /Dest (destination) ----------

    def get_destination(self) -> PDDestination | str | None:
        """Return ``/Dest`` dispatched to its appropriate type:

        - :class:`PDDestination` subclass for explicit page-target
          ``COSArray`` form, or for a named destination encoded as
          ``COSName`` / ``COSString`` (returned as :class:`PDNamedDestination`);
        - ``None`` when ``/Dest`` is absent.

        The ``str`` arm of the return type is reserved for raw named-string
        callers — :meth:`PDDestination.create` normally wraps those for us.
        """
        value = self._dict.get_dictionary_object(_DEST)
        if value is None:
            return None
        from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
            PDDestination,
        )

        return PDDestination.create(value)

    def set_destination(
        self, dest: PDDestination | str | COSBase | None
    ) -> None:
        """Write ``/Dest`` from a typed destination, a named-destination
        string, a raw ``COSBase``, or ``None`` (which removes the entry)."""
        if dest is None:
            self._dict.remove_item(_DEST)
            return
        if isinstance(dest, str):
            self._dict.set_item(_DEST, COSString(dest))
            return
        self._dict.set_item(
            _DEST,
            dest.get_cos_object() if hasattr(dest, "get_cos_object") else dest,
        )

    def has_destination(self) -> bool:
        """Return ``True`` if ``/Dest`` is present (any spec-allowed form:
        explicit page-target ``COSArray``, ``COSName``, or ``COSString``).

        Cheaper than ``get_destination() is not None`` because it skips the
        ``PDDestination.create`` factory dispatch.
        """
        return isinstance(
            self._dict.get_dictionary_object(_DEST), (COSArray, COSName, COSString)
        )

    # ---------- /H (highlight mode) ----------

    def get_highlight_mode(self) -> str:
        """Default per spec is INVERT (``I``).

        Mirrors upstream ``getHighlightMode()`` (PDAnnotationLink.java) which
        reads ``getNameAsString(COSName.H, "I")`` — a ``/H`` stored as a
        ``COSString`` (malformed but parseable) is returned as text rather
        than falling through to the default.
        """
        value = self._dict.get_name_as_string(_H)
        return value if value is not None else self.HIGHLIGHT_MODE_INVERT

    def set_highlight_mode(self, mode: str | None) -> None:
        if mode is None:
            self._dict.remove_item(_H)
            return
        self._dict.set_name(_H, mode)

    def has_highlight_mode(self) -> bool:
        """Return ``True`` if an explicit ``/H`` entry is present.

        Lets callers distinguish "explicit ``/H /I``" (the spec default
        written out) from "no ``/H`` entry" — both return
        ``HIGHLIGHT_MODE_INVERT`` via :meth:`get_highlight_mode`.

        Mirrors :meth:`get_highlight_mode`'s ``getNameAsString`` leniency: a
        ``/H`` stored as a name or a string both count as present.
        """
        return self._dict.get_name_as_string(_H) is not None

    def is_standard_highlight_mode(self) -> bool:
        """Return ``True`` if the resolved ``/H`` value is one of the four
        spec-defined modes in :data:`STANDARD_HIGHLIGHT_MODES`.

        The spec default ``HIGHLIGHT_MODE_INVERT`` (returned when ``/H`` is
        absent) is treated as standard. Non-standard ``/H`` values are
        permitted by the spec but their behaviour is reader-defined.
        """
        return self.get_highlight_mode() in self.STANDARD_HIGHLIGHT_MODES

    # ---------- /BS (border style) ----------

    def get_border_style(self) -> PDBorderStyleDictionary | None:
        from .pd_border_style_dictionary import PDBorderStyleDictionary

        value = self._dict.get_dictionary_object(_BS)
        if isinstance(value, COSDictionary):
            return PDBorderStyleDictionary(value)
        return None

    def set_border_style(
        self, bs: PDBorderStyleDictionary | COSDictionary | None
    ) -> None:
        if bs is None:
            self._dict.remove_item(_BS)
            return
        self._dict.set_item(
            _BS,
            bs.get_cos_object() if hasattr(bs, "get_cos_object") else bs,
        )

    def has_border_style(self) -> bool:
        """Return ``True`` if ``/BS`` is present and resolves to a
        dictionary. Cheaper than ``get_border_style() is not None``
        because it skips the ``PDBorderStyleDictionary`` wrapper
        construction.
        """
        return isinstance(
            self._dict.get_dictionary_object(_BS), COSDictionary
        )

    # ---------- /QuadPoints ----------

    def get_quad_points(self) -> list[float] | None:
        """Return ``/QuadPoints`` as a flat list of floats (``8 * n``
        entries describing ``n`` quadrilaterals), or ``None`` when absent.
        Mirrors upstream ``getQuadPoints()`` which returns ``float[]``."""
        value = self._dict.get_dictionary_object(_QUAD_POINTS)
        if isinstance(value, COSArray):
            return value.to_float_array()
        return None

    def set_quad_points(
        self,
        quad_points: list[float] | tuple[float, ...] | COSArray | None,
    ) -> None:
        """Write ``/QuadPoints`` from a list/tuple of floats, a raw
        ``COSArray``, or ``None`` (which removes the entry). Mirrors
        upstream ``setQuadPoints(float[])``."""
        if quad_points is None:
            self._dict.remove_item(_QUAD_POINTS)
            return
        if isinstance(quad_points, COSArray):
            self._dict.set_item(_QUAD_POINTS, quad_points)
            return
        arr = COSArray([COSFloat(float(v)) for v in quad_points])
        self._dict.set_item(_QUAD_POINTS, arr)

    def has_quad_points(self) -> bool:
        """Return ``True`` if a ``/QuadPoints`` array is present (even if
        empty).

        Useful predicate for callers that want to know whether the link
        annotation has been wired up with hit-testing geometry without
        materialising the full float list.
        """
        return isinstance(
            self._dict.get_dictionary_object(_QUAD_POINTS), COSArray
        )

    def quad_point_count(self) -> int:
        """Return the number of quadrilaterals encoded in ``/QuadPoints``.

        Each quadrilateral is described by 8 floats (4 corner points), so
        this is ``len(/QuadPoints) // 8``. Returns 0 when ``/QuadPoints``
        is absent or not a ``COSArray``. A trailing partial quadrilateral
        (length not a multiple of 8) is rounded down — same convention
        used by :class:`PDAnnotationTextMarkup` and upstream readers.
        """
        value = self._dict.get_dictionary_object(_QUAD_POINTS)
        if isinstance(value, COSArray):
            return value.size() // 8
        return 0

    # ---------- /PA (previewer action) ----------

    def get_p_a(self) -> PDAction | None:
        """``/PA`` — URI action invoked when the cursor enters the
        annotation's active area, used by previewers (PDF 32000-1 Table
        173). Mirrors upstream ``getPA()``."""
        from pypdfbox.pdmodel.interactive.action import PDAction

        value = self._dict.get_dictionary_object(_PA)
        if isinstance(value, COSDictionary):
            return PDAction.create(value)
        return None

    def set_p_a(self, action: PDAction | COSDictionary | None) -> None:
        """Mirrors upstream ``setPA(PDAction)``."""
        if action is None:
            self._dict.remove_item(_PA)
            return
        self._dict.set_item(
            _PA,
            action.get_cos_object() if hasattr(action, "get_cos_object") else action,
        )

    def get_previous_uri(self) -> PDAction | None:
        """Upstream-named accessor for ``/PA``. Mirrors
        ``getPreviousURI()`` — returns the previous URI action."""
        return self.get_p_a()

    def set_previous_uri(self, action: PDAction | COSDictionary | None) -> None:
        """Upstream-named setter for ``/PA``. Mirrors
        ``setPreviousURI(PDActionURI)``."""
        self.set_p_a(action)

    def has_p_a(self) -> bool:
        """Return ``True`` if ``/PA`` is present and resolves to a
        dictionary. Cheaper than ``get_p_a() is not None`` because it
        skips the ``PDAction.create`` factory dispatch.
        """
        return isinstance(
            self._dict.get_dictionary_object(_PA), COSDictionary
        )

    def has_previous_uri(self) -> bool:
        """Upstream-named alias for :meth:`has_p_a`."""
        return self.has_p_a()

    # ---------- convenience: extract URL from /A when /Subtype /URI ----------

    def is_uri_action(self) -> bool:
        """Return ``True`` if ``/A`` is present, is a dictionary, and
        carries ``/S /URI`` (PDF 32000-1 §12.6.4.7). Useful before
        calling :meth:`get_url_uri` if the caller wants to distinguish
        "no action", "non-URI action" and "URI action with empty
        ``/URI`` string".
        """
        action = self._dict.get_dictionary_object(_A)
        if not isinstance(action, COSDictionary):
            return False
        return action.get_name(_S) == "URI"

    def get_url_uri(self) -> str | None:
        """Return the ``/URI`` string from ``/A`` when the action is a URI
        action (``/A << /S /URI /URI (...) >>``), else ``None``. Pure
        convenience accessor without instantiating the action wrapper."""
        action = self._dict.get_dictionary_object(_A)
        if not isinstance(action, COSDictionary):
            return None
        if action.get_name(_S) != "URI":
            return None
        return action.get_string(_URI_NAME)

    # ---------- appearance construction ----------

    def set_custom_appearance_handler(
        self, appearance_handler: PDAppearanceHandler | None
    ) -> None:
        """Set the custom appearance handler used by
        :meth:`construct_appearances`.

        Mirrors upstream ``setCustomAppearanceHandler``
        (``PDAnnotationLink.java`` line ~209). Pass ``None`` to clear the
        custom handler and restore the default construction path.
        """
        self._custom_appearance_handler = appearance_handler

    def get_custom_appearance_handler(self) -> PDAppearanceHandler | None:
        """Return the custom appearance handler previously set via
        :meth:`set_custom_appearance_handler`, or ``None`` when the default
        construction path is in use. No upstream getter exists (the field is
        package-private in Java); this is the Pythonic accessor used by
        tests and downstream code that needs to inspect the wired handler.
        """
        return self._custom_appearance_handler

    def construct_appearances(self, document: PDDocument | None = None) -> None:
        """Generate link annotation appearances.

        Mirrors upstream ``constructAppearances(PDDocument)``
        (``PDAnnotationLink.java`` lines 236-247). When no custom handler is
        configured, the built-in ``PDLinkAppearanceHandler`` is wired and its
        appearance streams are generated; otherwise the custom handler is
        invoked exactly as upstream does.
        """
        if self._custom_appearance_handler is None:
            from .handlers.pd_link_appearance_handler import (
                PDLinkAppearanceHandler,
            )

            appearance_handler = PDLinkAppearanceHandler(self, document)
            appearance_handler.generate_appearance_streams()
            return None
        self._custom_appearance_handler.generate_appearance_streams()
        return None


__all__ = ["PDAnnotationLink"]
