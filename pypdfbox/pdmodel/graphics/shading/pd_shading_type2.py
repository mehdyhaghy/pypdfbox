from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSName,
)

from .pd_shading import PDShading

_SHADING_TYPE: COSName = COSName.get_pdf_name("ShadingType")
_COORDS: COSName = COSName.get_pdf_name("Coords")
_DOMAIN: COSName = COSName.get_pdf_name("Domain")
_FUNCTION: COSName = COSName.get_pdf_name("Function")
_EXTEND: COSName = COSName.get_pdf_name("Extend")


class PDShadingType2(PDShading):
    """Axial (linear-gradient) shading. Mirrors PDFBox ``PDShadingType2``.

    Per PDF 32000-1 §8.7.4.5.3 (Table 85): ``/Coords`` is a 4-element array
    ``[x0 y0 x1 y1]`` defining the gradient axis, ``/Domain`` is a 2-element
    parametric range (default ``[0 1]``), ``/Function`` is required, and
    ``/Extend`` is a 2-element boolean array indicating whether to extend
    the shading beyond the starting/ending point (default ``[false false]``).
    """

    def __init__(self, dictionary_or_stream: COSDictionary | None = None) -> None:
        super().__init__(dictionary_or_stream)
        if dictionary_or_stream is None:
            self._dict.set_int(_SHADING_TYPE, PDShading.SHADING_TYPE2)

    def get_shading_type(self) -> int:
        return PDShading.SHADING_TYPE2

    # ---------- /Coords ----------

    def get_coords(self) -> COSArray | None:
        """Returns ``/Coords`` (a 4-element ``[x0 y0 x1 y1]`` array) or
        ``None`` when the entry is absent. ``/Coords`` has no spec default;
        it is required per Table 85."""
        v = self._dict.get_dictionary_object(_COORDS)
        return v if isinstance(v, COSArray) else None

    def set_coords(self, coords: COSArray | None) -> None:
        if coords is None:
            self._dict.remove_item(_COORDS)
            return
        self._dict.set_item(_COORDS, coords)

    # ---------- /Domain ----------

    def get_domain(self) -> COSArray | None:
        """Returns ``/Domain`` (a 2-element parametric range). When absent,
        materializes the spec default ``[0 1]`` as a fresh ``COSArray`` —
        the entry is *not* written back to the underlying dictionary."""
        v = self._dict.get_dictionary_object(_DOMAIN)
        if isinstance(v, COSArray):
            return v
        default = COSArray()
        default.add(COSFloat(0.0))
        default.add(COSFloat(1.0))
        return default

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
        is absent. Mirrors upstream ``PDShading.getFunction()``.

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

    def get_extend(self) -> tuple[bool, bool]:
        """Returns ``/Extend`` as a 2-tuple ``(extend_start, extend_end)``.
        Per Table 85, the spec default when the entry is absent is
        ``[false false]``. Non-boolean entries are coerced to ``False``."""
        v = self._dict.get_dictionary_object(_EXTEND)
        if not isinstance(v, COSArray) or v.size() < 2:
            return (False, False)
        a = v.get_object(0)
        b = v.get_object(1)
        return (
            isinstance(a, COSBoolean) and a.get_value(),
            isinstance(b, COSBoolean) and b.get_value(),
        )

    def set_extend(self, start: bool | COSArray | None, end: bool | None = None) -> None:
        """Set ``/Extend``. Accepts either ``(start, end)`` as a pair of
        booleans (matching upstream's 2-element ``[start end]`` array form)
        or a single ``COSArray`` argument (legacy form — stored as-is).
        Pass ``None`` for the single-argument form to remove the entry."""
        # Single-argument forms (back-compat).
        if end is None:
            if start is None:
                self._dict.remove_item(_EXTEND)
                return
            if isinstance(start, COSArray):
                self._dict.set_item(_EXTEND, start)
                return
        # Two-argument form (canonical, matches upstream).
        array = COSArray()
        array.add(COSBoolean.get(bool(start)))
        array.add(COSBoolean.get(bool(end)))
        self._dict.set_item(_EXTEND, array)


__all__ = ["PDShadingType2"]
