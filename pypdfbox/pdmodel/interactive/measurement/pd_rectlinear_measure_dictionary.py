from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_measure_dictionary import PDMeasureDictionary
from .pd_number_format_dictionary import PDNumberFormatDictionary

_R: COSName = COSName.get_pdf_name("R")
_X: COSName = COSName.get_pdf_name("X")
_Y: COSName = COSName.get_pdf_name("Y")
_D: COSName = COSName.get_pdf_name("D")
_A: COSName = COSName.get_pdf_name("A")
_T: COSName = COSName.get_pdf_name("T")
_S: COSName = COSName.get_pdf_name("S")
_O: COSName = COSName.get_pdf_name("O")
_CYX: COSName = COSName.get_pdf_name("CYX")


class PDRectlinearMeasureDictionary(PDMeasureDictionary):
    """This class represents a rectlinear measure dictionary.

    Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.interactive.measurement.PDRectlinearMeasureDictionary``.

    The dictionary describes how to translate between PDF default units
    and the user's measurement units along the x/y axes (``/X``, ``/Y``),
    distances (``/D``), areas (``/A``), angles (``/T``), line slopes
    (``/S``) plus the coordinate-system origin (``/O``) and the y/x
    aspect-ratio scale factor (``/CYX``).
    """

    #: The ``/Subtype`` value of the rectlinear measure dictionary.
    SUBTYPE: str = "RL"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            super().__init__()
            self._set_subtype(self.SUBTYPE)
        else:
            super().__init__(dictionary)

    # ------------------------------------------------------------------ /R (scale ratio)
    def get_scale_ratio(self) -> str | None:
        """Return the scale ratio (``/R``)."""
        return self._dict.get_string(_R)

    def set_scale_ratio(self, scale_ratio: str | None) -> None:
        """Set the scale ratio (``/R``)."""
        self._dict.set_string(_R, scale_ratio)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _array_to_number_formats(
        arr: COSArray,
    ) -> list[PDNumberFormatDictionary]:
        # Upstream ``PDRectlinearMeasureDictionary.arrayToNumberFormat`` casts
        # every array member straight to ``COSDictionary``
        # (``(COSDictionary) array.getObject(i)``) with no type guard, so a
        # malformed array containing a non-dictionary member raises a
        # ``ClassCastException``. We mirror that exactly — a defensive
        # ``isinstance`` skip would silently drop the bad member and diverge
        # from PDFBox (verified against the live oracle, MeasureDictFuzzProbe
        # ``d.mixed`` case). ``TypeError`` is Python's ``ClassCastException``.
        retval: list[PDNumberFormatDictionary] = []
        for i in range(arr.size()):
            entry = arr.get_object(i)
            if not isinstance(entry, COSDictionary):
                raise TypeError(
                    f"{type(entry).__name__} cannot be cast to COSDictionary"
                )
            retval.append(PDNumberFormatDictionary(entry))
        return retval

    @staticmethod
    def _number_formats_to_array(
        items: list[PDNumberFormatDictionary] | tuple[PDNumberFormatDictionary, ...],
    ) -> COSArray:
        arr = COSArray()
        for nf in items:
            arr.add(nf.get_cos_object())
        return arr

    def _get_number_format_array(
        self, key: COSName
    ) -> list[PDNumberFormatDictionary] | None:
        value = self._dict.get_dictionary_object(key)
        if isinstance(value, COSArray):
            return self._array_to_number_formats(value)
        return None

    # ------------------------------------------------------------------ /X (changes along x-axis)
    def get_change_xs(self) -> list[PDNumberFormatDictionary] | None:
        """Return the changes along the x-axis (``/X``)."""
        return self._get_number_format_array(_X)

    def set_change_xs(
        self,
        change_xs: list[PDNumberFormatDictionary] | tuple[PDNumberFormatDictionary, ...],
    ) -> None:
        """Set the changes along the x-axis (``/X``)."""
        self._dict.set_item(_X, self._number_formats_to_array(change_xs))

    # ------------------------------------------------------------------ /Y (changes along y-axis)
    def get_change_ys(self) -> list[PDNumberFormatDictionary] | None:
        """Return the changes along the y-axis (``/Y``)."""
        return self._get_number_format_array(_Y)

    def set_change_ys(
        self,
        change_ys: list[PDNumberFormatDictionary] | tuple[PDNumberFormatDictionary, ...],
    ) -> None:
        """Set the changes along the y-axis (``/Y``)."""
        self._dict.set_item(_Y, self._number_formats_to_array(change_ys))

    # ------------------------------------------------------------------ /D (distances)
    def get_distances(self) -> list[PDNumberFormatDictionary] | None:
        """Return the distances (``/D``)."""
        return self._get_number_format_array(_D)

    def set_distances(
        self,
        distances: list[PDNumberFormatDictionary] | tuple[PDNumberFormatDictionary, ...],
    ) -> None:
        """Set the distances (``/D``)."""
        self._dict.set_item(_D, self._number_formats_to_array(distances))

    # ------------------------------------------------------------------ /A (areas)
    def get_areas(self) -> list[PDNumberFormatDictionary] | None:
        """Return the areas (``/A``)."""
        return self._get_number_format_array(_A)

    def set_areas(
        self,
        areas: list[PDNumberFormatDictionary] | tuple[PDNumberFormatDictionary, ...],
    ) -> None:
        """Set the areas (``/A``)."""
        self._dict.set_item(_A, self._number_formats_to_array(areas))

    # ------------------------------------------------------------------ /T (angles)
    def get_angles(self) -> list[PDNumberFormatDictionary] | None:
        """Return the angles (``/T``)."""
        return self._get_number_format_array(_T)

    def set_angles(
        self,
        angles: list[PDNumberFormatDictionary] | tuple[PDNumberFormatDictionary, ...],
    ) -> None:
        """Set the angles (``/T``)."""
        self._dict.set_item(_T, self._number_formats_to_array(angles))

    # ------------------------------------------------------------------ /S (line slopes)
    def get_line_sloaps(self) -> list[PDNumberFormatDictionary] | None:
        """Return the slopes of a line (``/S``).

        The misspelling ``Sloaps`` is preserved verbatim from upstream
        ``getLineSloaps()`` for API compatibility.
        """
        return self._get_number_format_array(_S)

    def set_line_sloaps(
        self,
        line_sloaps: list[PDNumberFormatDictionary] | tuple[PDNumberFormatDictionary, ...],
    ) -> None:
        """Set the slopes of a line (``/S``).

        The misspelling ``Sloaps`` is preserved verbatim from upstream
        ``setLineSloaps()`` for API compatibility.
        """
        self._dict.set_item(_S, self._number_formats_to_array(line_sloaps))

    # The upstream spelling ``Sloaps`` is a typo for "Slopes" preserved
    # verbatim above for parity. Expose correctly-spelled aliases that
    # delegate to the same ``/S`` slot — pypdfbox callers writing fresh
    # code should reach for these. Both pairs round-trip through one
    # underlying COS entry; mixing them is safe.
    def get_line_slopes(self) -> list[PDNumberFormatDictionary] | None:
        """Alias for :meth:`get_line_sloaps` using the correct English spelling."""
        return self.get_line_sloaps()

    def set_line_slopes(
        self,
        line_slopes: list[PDNumberFormatDictionary] | tuple[PDNumberFormatDictionary, ...],
    ) -> None:
        """Alias for :meth:`set_line_sloaps` using the correct English spelling."""
        self.set_line_sloaps(line_slopes)

    # ------------------------------------------------------------------ /O (coord-system origin)
    def get_coord_system_origin(self) -> list[float] | None:
        """Return the origin of the coordinate system (``/O``).

        Upstream returns a ``float[]``; we return a ``list[float]`` (or
        ``None`` when the entry is absent), mirroring ``COSArray.toFloatArray()``.
        """
        value = self._dict.get_dictionary_object(_O)
        if isinstance(value, COSArray):
            return value.to_float_array()
        return None

    def set_coord_system_origin(
        self, coord_system_origin: list[float] | tuple[float, ...]
    ) -> None:
        """Set the origin of the coordinate system (``/O``)."""
        arr = COSArray()
        arr.set_float_array(coord_system_origin)
        self._dict.set_item(_O, arr)

    # ------------------------------------------------------------------ /CYX (y/x ratio)
    def get_cyx(self) -> float:
        """Return the CYX factor (``/CYX``).

        Upstream returns ``getFloat(COSName.CYX)`` — pypdfbox's
        ``COSDictionary.get_float`` defaults to ``-1.0`` when the entry is
        missing, matching upstream's ``COSDictionary.getFloat()`` default
        of ``-1``.
        """
        return self._dict.get_float(_CYX)

    def set_cyx(self, cyx: float) -> None:
        """Set the CYX factor (``/CYX``)."""
        self._dict.set_float(_CYX, cyx)

    # ------------------------------------------------------------------ predicates
    # Upstream PDFBox lacks these — they are convenience helpers that
    # distinguish *absent* entries from entries that happen to be set to
    # the upstream-default sentinel (``-1.0`` for ``/CYX``, ``None`` for
    # the string slots). ``contains_key`` is the ``COSDictionary``-level
    # operation that mirrors upstream's ``COSDictionary.containsKey``;
    # behavior is identical to writing ``in dict`` over the COS layer.
    def has_scale_ratio(self) -> bool:
        """Return ``True`` when the ``/R`` (scale ratio) entry is present."""
        return self._dict.contains_key(_R)

    def has_change_xs(self) -> bool:
        """Return ``True`` when the ``/X`` (changes along x-axis) entry is present."""
        return self._dict.contains_key(_X)

    def has_change_ys(self) -> bool:
        """Return ``True`` when the ``/Y`` (changes along y-axis) entry is present."""
        return self._dict.contains_key(_Y)

    def has_distances(self) -> bool:
        """Return ``True`` when the ``/D`` (distances) entry is present."""
        return self._dict.contains_key(_D)

    def has_areas(self) -> bool:
        """Return ``True`` when the ``/A`` (areas) entry is present."""
        return self._dict.contains_key(_A)

    def has_angles(self) -> bool:
        """Return ``True`` when the ``/T`` (angles) entry is present."""
        return self._dict.contains_key(_T)

    def has_line_slopes(self) -> bool:
        """Return ``True`` when the ``/S`` (line slopes) entry is present.

        Mirrors the corrected-spelling alias :meth:`get_line_slopes`; the
        upstream-spelled :meth:`has_line_sloaps` is exposed below.
        """
        return self._dict.contains_key(_S)

    def has_line_sloaps(self) -> bool:
        """Alias for :meth:`has_line_slopes` matching the upstream typo."""
        return self.has_line_slopes()

    def has_coord_system_origin(self) -> bool:
        """Return ``True`` when the ``/O`` (coord-system origin) entry is present."""
        return self._dict.contains_key(_O)

    def has_cyx(self) -> bool:
        """Return ``True`` when the ``/CYX`` entry is present.

        Distinguishes between an absent ``/CYX`` (``get_cyx()`` returns
        ``-1.0`` as the upstream-compatible sentinel) and an entry that
        was explicitly set to ``-1.0``.
        """
        return self._dict.contains_key(_CYX)


__all__ = ["PDRectlinearMeasureDictionary"]
