from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSName,
)

from .pd_shading import PDShading

_SHADING_TYPE: COSName = COSName.get_pdf_name("ShadingType")
_COORDS: COSName = COSName.get_pdf_name("Coords")
_DOMAIN: COSName = COSName.get_pdf_name("Domain")
_FUNCTION: COSName = COSName.get_pdf_name("Function")
_EXTEND: COSName = COSName.get_pdf_name("Extend")


class PDShadingType3(PDShading):
    """Radial shading. Mirrors PDFBox ``PDShadingType3`` lite surface.

    Per PDF 32000-1 §8.7.4.5.4 (Table 86), ``/Coords`` is a 6-element array
    ``[x0 y0 r0 x1 y1 r1]`` defining the starting and ending circles,
    ``/Domain`` is a 2-element parametric range (default ``[0 1]``),
    ``/Function`` is required, and ``/Extend`` is a 2-element boolean array
    indicating whether to extend the shading beyond the starting/ending
    circle (default ``[false false]``).
    """

    def __init__(self, dictionary_or_stream: COSDictionary | None = None) -> None:
        super().__init__(dictionary_or_stream)
        if dictionary_or_stream is None:
            self._dict.set_int(_SHADING_TYPE, PDShading.SHADING_TYPE3)

    def get_shading_type(self) -> int:
        return PDShading.SHADING_TYPE3

    # ---------- /Coords ----------

    def get_coords(self) -> COSArray | None:
        """Returns ``/Coords`` (a 6-element ``[x0 y0 r0 x1 y1 r1]`` array)
        or ``None`` when the entry is absent. ``/Coords`` has no spec
        default; it is required per Table 86."""
        v = self._dict.get_dictionary_object(_COORDS)
        return v if isinstance(v, COSArray) else None

    def set_coords(self, coords: COSArray | None) -> None:
        if coords is None:
            self._dict.remove_item(_COORDS)
            return
        self._dict.set_item(_COORDS, coords)

    # ---------- /Domain ----------

    def get_domain(self) -> COSArray | None:
        """Returns ``/Domain`` (a 2-element parametric range), or ``None`` when
        the entry is absent or is not a ``COSArray``.

        Mirrors upstream ``PDShadingType3.getDomain()`` (inherited from
        ``PDShadingType2``) which delegates to ``getCOSArray(DOMAIN)`` —
        returns the stored array or ``null``; it does **not** materialize the
        spec default ``[0 1]``. Callers that need the default (the radial
        shading context) apply it themselves."""
        v = self._dict.get_dictionary_object(_DOMAIN)
        return v if isinstance(v, COSArray) else None

    def set_domain(self, domain: COSArray | Iterable[float] | None) -> None:
        """Set ``/Domain``. Accepts a ``COSArray`` (stored as-is, preserving
        indirect references) or any iterable of floats (wrapped into a fresh
        ``COSArray`` of ``COSFloat`` entries). ``None`` removes the entry."""
        if domain is None:
            self._dict.remove_item(_DOMAIN)
            return
        if isinstance(domain, COSArray):
            self._dict.set_item(_DOMAIN, domain)
            return
        array = COSArray()
        array.set_float_array(domain)
        self._dict.set_item(_DOMAIN, array)

    # ---------- /Function ----------

    def get_function(self) -> Any:
        """Returns the ``/Function`` entry wrapped as a ``PDFunction``
        (dispatched on ``/FunctionType``), or ``None`` when ``/Function``
        is absent. Mirrors upstream ``PDShading.getFunction()`` which
        returns a ``PDFunction``.

        When ``/Function`` is an array of single-output functions (one per
        color component), this returns the raw ``COSArray`` — callers should
        use ``get_functions_array()`` for explicit per-component access."""
        from pypdfbox.pdmodel.common.function import PDFunction

        item = self._dict.get_dictionary_object(_FUNCTION)
        if item is None:
            return None
        if isinstance(item, COSArray):
            return item
        return PDFunction.create(item)

    def get_functions_array(self) -> list[Any]:
        """Returns the per-component ``/Function`` entries wrapped as
        ``PDFunction`` instances. When ``/Function`` is a single function,
        returns a one-element list. Returns an empty list when absent."""
        from pypdfbox.pdmodel.common.function import PDFunction

        item = self._dict.get_dictionary_object(_FUNCTION)
        if item is None:
            return []
        if isinstance(item, COSArray):
            out: list[Any] = []
            for i in range(item.size()):
                entry = item.get_object(i)
                if entry is not None:
                    out.append(PDFunction.create(entry))
            return out
        return [PDFunction.create(item)]

    def set_function(self, value: Any) -> None:
        """Set ``/Function``. Accepts a ``PDFunction`` (its backing COS
        object is stored), a raw ``COSDictionary`` / ``COSStream``, a
        ``COSArray`` of per-component functions, an iterable of
        ``PDFunction`` instances (wrapped into a fresh ``COSArray``), or
        ``None`` to remove."""
        from pypdfbox.pdmodel.common.function import PDFunction

        if value is None:
            self._dict.remove_item(_FUNCTION)
            return
        if isinstance(value, PDFunction):
            self._dict.set_item(_FUNCTION, value.get_cos_object())
            return
        if isinstance(value, COSBase):
            self._dict.set_item(_FUNCTION, value)
            return
        try:
            iterator = iter(value)
        except TypeError as exc:
            raise TypeError(
                "set_function expects PDFunction, COSDictionary, COSStream, "
                f"COSArray, iterable of PDFunction, or None; got "
                f"{type(value).__name__}"
            ) from exc
        array = COSArray()
        for entry in iterator:
            if isinstance(entry, PDFunction):
                array.add(entry.get_cos_object())
            elif isinstance(entry, COSBase):
                array.add(entry)
            else:
                raise TypeError(
                    "set_function iterable entries must be PDFunction or "
                    f"COSBase; got {type(entry).__name__}"
                )
        self._dict.set_item(_FUNCTION, array)

    # ---------- /Extend ----------

    def get_extend(self) -> COSArray | None:
        """Returns ``/Extend`` (a 2-element boolean array), or ``None`` when
        the entry is absent or is not a ``COSArray``.

        Mirrors upstream ``PDShadingType3.getExtend()`` (inherited from
        ``PDShadingType2``) which delegates to ``getCOSArray(EXTEND)`` —
        returns the stored ``COSArray`` or ``null``; it does **not**
        materialize the spec default ``[false false]`` nor coerce the result
        to booleans. Callers that need the ``(start, end)`` boolean pair (the
        radial shading context) read the two ``COSBoolean`` entries off the
        array themselves."""
        v = self._dict.get_dictionary_object(_EXTEND)
        return v if isinstance(v, COSArray) else None

    def set_extend(self, start: bool | COSArray | None, end: bool | None = None) -> None:
        """Set ``/Extend``. Accepts either ``(start, end)`` as a pair of
        booleans or the upstream-shaped single ``COSArray`` argument.
        Pass ``None`` for the single-argument form to remove the entry."""
        if end is None:
            if start is None:
                self._dict.remove_item(_EXTEND)
                return
            if isinstance(start, COSArray):
                self._dict.set_item(_EXTEND, start)
                return
        array = COSArray()
        array.add(COSBoolean.get(bool(start)))
        array.add(COSBoolean.get(bool(end)))
        self._dict.set_item(_EXTEND, array)


    # ---------- paint (rendering hook) ----------

    def to_paint(self, matrix: Any = None) -> Any:
        """Return a ``RadialShadingPaint`` for this radial-gradient shading.

        Mirrors upstream ``PDShadingType3.toPaint(Matrix)`` which returns
        ``new RadialShadingPaint(this, matrix)``.
        """
        from .radial_shading_paint import RadialShadingPaint  # noqa: PLC0415

        return RadialShadingPaint(self, matrix)


__all__ = ["PDShadingType3"]
