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

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
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

    # ---------- /H (highlight mode) ----------

    def get_highlight_mode(self) -> str:
        """Default per spec is INVERT (``I``)."""
        value = self._dict.get_name(_H)
        return value if value is not None else self.HIGHLIGHT_MODE_INVERT

    def set_highlight_mode(self, mode: str | None) -> None:
        if mode is None:
            self._dict.remove_item(_H)
            return
        self._dict.set_name(_H, mode)

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

    # ---------- convenience: extract URL from /A when /Subtype /URI ----------

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


__all__ = ["PDAnnotationLink"]
