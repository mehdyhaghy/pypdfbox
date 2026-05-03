from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSNull

from .pd_page_destination import PDPageDestination


class PDPageXYZDestination(PDPageDestination):
    """XYZ page destination. Mirrors PDFBox ``PDPageXYZDestination``.

    Per PDF 32000-1 §12.3.2.2 (Table 151), an ``/XYZ`` destination is the
    five-slot array ``[page /XYZ left top zoom]``. Any of ``left``,
    ``top`` or ``zoom`` may be ``null`` (or, in upstream Java, the
    sentinel ``-1``) meaning *retain the current viewer value for that
    coordinate*. The :data:`UNSET` constant exposes this sentinel for
    callers that want to write the upstream-style ``-1``.
    """

    TYPE = "XYZ"

    #: Upstream-parity sentinel for the "use the current viewer value"
    #: convention. ``getLeft()``/``getTop()``/``getZoom()`` in the Java
    #: API return ``-1`` when the slot is missing; ``setLeft(-1)`` writes
    #: a ``COSNull`` to mark the slot as unset.
    UNSET: int = -1

    #: Slot indices into the ``/D`` array (page slot is 0, type-name is 1).
    _SLOT_LEFT: int = 2
    _SLOT_TOP: int = 3
    _SLOT_ZOOM: int = 4

    def __init__(self, array: COSArray | None = None) -> None:
        super().__init__(array)
        if array is None:
            self._set_type(self.TYPE)

    def get_left(self) -> float | None:
        return self._get_float(self._SLOT_LEFT)

    def set_left(self, left: float | None) -> None:
        self._set_float(self._SLOT_LEFT, left)

    def get_top(self) -> float | None:
        return self._get_float(self._SLOT_TOP)

    def set_top(self, top: float | None) -> None:
        self._set_float(self._SLOT_TOP, top)

    def get_zoom(self) -> float | None:
        return self._get_float(self._SLOT_ZOOM)

    def set_zoom(self, zoom: float | None) -> None:
        self._set_float(self._SLOT_ZOOM, zoom)

    # ---------- predicate helpers ----------

    def _is_slot_unset(self, slot: int) -> bool:
        """Return ``True`` when ``slot`` is missing from the underlying
        ``/D`` array (out-of-range, ``COSNull``, or a non-numeric
        placeholder). Mirrors upstream's ``-1`` sentinel semantics."""
        arr = self.get_cos_array()
        if slot >= arr.size():
            return True
        value = arr.get_object(slot)
        return not isinstance(value, (COSInteger, COSFloat))

    def is_left_unset(self) -> bool:
        """``True`` when the ``left`` x-coordinate is missing or null.

        Equivalent to ``get_left() is None`` but spelled as a predicate
        so callers don't have to bind the value into a temporary just
        to ask the question.
        """
        return self._is_slot_unset(self._SLOT_LEFT)

    def is_top_unset(self) -> bool:
        """``True`` when the ``top`` y-coordinate is missing or null."""
        return self._is_slot_unset(self._SLOT_TOP)

    def is_zoom_unset(self) -> bool:
        """``True`` when the zoom factor is missing or null.

        Note: a zoom value of ``0`` means *retain the current zoom*
        per PDF 32000-1, but ``0`` is still an explicitly written value
        on the array — this predicate returns ``False`` in that case.
        """
        return self._is_slot_unset(self._SLOT_ZOOM)

    def is_complete(self) -> bool:
        """``True`` when all three coordinates (``left``, ``top``, ``zoom``)
        are explicitly set on the underlying array.

        Convenience predicate for callers that want to know whether the
        destination fully pins the viewer state versus inheriting some
        coordinates from the current view.
        """
        return not (
            self.is_left_unset()
            or self.is_top_unset()
            or self.is_zoom_unset()
        )

    def clear_left(self) -> None:
        """Clear the ``left`` slot to ``COSNull``.

        Convenience helper that's equivalent to ``set_left(None)`` but
        spelled as a verb for callers who think in terms of "unsetting"
        the slot rather than passing a sentinel value.
        """
        self.get_cos_array().grow_to_size(self._SLOT_LEFT + 1, COSNull.NULL)
        self.get_cos_array().set(self._SLOT_LEFT, COSNull.NULL)

    def clear_top(self) -> None:
        """Clear the ``top`` slot to ``COSNull``."""
        self.get_cos_array().grow_to_size(self._SLOT_TOP + 1, COSNull.NULL)
        self.get_cos_array().set(self._SLOT_TOP, COSNull.NULL)

    def clear_zoom(self) -> None:
        """Clear the ``zoom`` slot to ``COSNull``."""
        self.get_cos_array().grow_to_size(self._SLOT_ZOOM + 1, COSNull.NULL)
        self.get_cos_array().set(self._SLOT_ZOOM, COSNull.NULL)


__all__ = ["PDPageXYZDestination"]
