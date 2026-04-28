from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_action import PDAction

_TA: COSName = COSName.get_pdf_name("TA")
_V: COSName = COSName.get_pdf_name("V")


class PDActionGoTo3DView(PDAction):
    """Go-To-3D-View action. Mirrors the ``GoTo3DView`` action type from
    PDF 32000-1 §12.6.4.16 / Table 211.

    The action sets the current view of a 3D annotation. It carries:

    - ``/TA`` — required, indirect reference to a 3D annotation dictionary
      whose view shall be set.
    - ``/V`` — optional, identifies the view to use. May be a named view
      (``/F`` for first / default, ``/L`` for last, ``/N`` for next,
      ``/P`` for previous), an integer (zero-based index into the 3D
      stream's ``/VA`` array), a string (matches the ``/IN`` internal
      name of an entry in ``/VA``), or a 3D view dictionary directly.

    Note: not present in upstream Apache PDFBox 3.0.x; added here for
    spec parity with PDF 32000-1. Recorded in ``CHANGES.md``.
    """

    SUB_TYPE = "GoTo3DView"

    # Named /V values per Table 211.
    VIEW_FIRST = "F"
    VIEW_LAST = "L"
    VIEW_NEXT = "N"
    VIEW_PREVIOUS = "P"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # ---------- /TA — target 3D annotation ----------

    def get_target_annotation(self) -> COSBase | None:
        """Return the raw ``/TA`` 3D annotation dictionary entry, or
        ``None`` when absent."""
        return self._action.get_dictionary_object(_TA)

    def set_target_annotation(self, annotation: COSBase | None) -> None:
        """Write the ``/TA`` entry. ``None`` removes the entry; otherwise
        the value is stored as-is (typically an indirect reference to a
        3D annotation dictionary)."""
        if annotation is None:
            self._action.remove_item(_TA)
            return
        self._action.set_item(_TA, annotation)

    # Raw alias mirroring the entry key.
    def get_ta(self) -> COSBase | None:
        return self.get_target_annotation()

    def set_ta(self, annotation: COSBase | None) -> None:
        self.set_target_annotation(annotation)

    # ---------- /V — view selector ----------

    def get_v(self) -> COSBase | None:
        """Return the raw ``/V`` view-selector entry, or ``None`` when
        absent. May be a name (``/F``/``/L``/``/N``/``/P``), integer,
        string, or 3D view dictionary."""
        return self._action.get_dictionary_object(_V)

    def set_v(self, view: COSBase | str | int | None) -> None:
        """Write the ``/V`` entry. Accepts a raw ``COSBase`` (stored as-is),
        a ``str`` (stored as a name when it matches one of the four
        single-letter named-view selectors, otherwise as a string),
        an ``int`` (stored as integer), or ``None`` to remove the entry."""
        if view is None:
            self._action.remove_item(_V)
            return
        if isinstance(view, str):
            if view in (
                self.VIEW_FIRST,
                self.VIEW_LAST,
                self.VIEW_NEXT,
                self.VIEW_PREVIOUS,
            ):
                self._action.set_name(_V, view)
            else:
                self._action.set_string(_V, view)
            return
        if isinstance(view, bool):
            # bool is a subclass of int in Python — reject to avoid
            # silently writing 0/1 when the caller meant something else.
            raise TypeError("set_v does not accept bool")
        if isinstance(view, int):
            self._action.set_int(_V, view)
            return
        self._action.set_item(_V, view)


__all__ = ["PDActionGoTo3DView"]
