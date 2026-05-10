from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSFloat, COSName

from .pd_shading import PDShading

_SHADING_TYPE: COSName = COSName.get_pdf_name("ShadingType")
_DOMAIN: COSName = COSName.get_pdf_name("Domain")
_MATRIX: COSName = COSName.get_pdf_name("Matrix")
_FUNCTION: COSName = COSName.get_pdf_name("Function")


class PDShadingType1(PDShading):
    """Function-based shading. Mirrors PDFBox ``PDShadingType1``.

    Per PDF 32000-1 §8.7.4.5.2 (Table 79): ``/Domain`` is a 4-element
    parametric range ``[xmin xmax ymin ymax]`` (default ``[0 1 0 1]``),
    ``/Matrix`` is an optional 6-element transformation matrix mapping the
    domain rectangle into the target coordinate space (default identity),
    and ``/Function`` is required — it may be a single function or an array
    of ``n`` functions where ``n`` is the number of color components.
    """

    def __init__(self, dictionary_or_stream: COSDictionary | None = None) -> None:
        super().__init__(dictionary_or_stream)
        if dictionary_or_stream is None:
            self._dict.set_int(_SHADING_TYPE, PDShading.SHADING_TYPE1)

    def get_shading_type(self) -> int:
        return PDShading.SHADING_TYPE1

    # ---------- /Domain ----------

    def get_domain(self) -> COSArray | None:
        """Returns ``/Domain`` (a 4-element ``[xmin xmax ymin ymax]`` array).
        When absent, materializes the spec default ``[0 1 0 1]`` as a fresh
        ``COSArray`` — the entry is *not* written back to the underlying
        dictionary, so callers can detect "explicit vs defaulted" via
        ``get_cos_object().get_dictionary_object('Domain')``."""
        v = self._dict.get_dictionary_object(_DOMAIN)
        if isinstance(v, COSArray):
            return v
        default = COSArray()
        for f in (0.0, 1.0, 0.0, 1.0):
            default.add(COSFloat(f))
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

    # ---------- /Matrix ----------

    def get_matrix(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_MATRIX)
        return v if isinstance(v, COSArray) else None

    def set_matrix(self, matrix: COSArray | None) -> None:
        if matrix is None:
            self._dict.remove_item(_MATRIX)
            return
        self._dict.set_item(_MATRIX, matrix)

    # ---------- /Function ----------

    def get_function(self) -> Any:
        """Returns the ``/Function`` entry wrapped as a ``PDFunction``
        (dispatched on ``/FunctionType``), or ``None`` when ``/Function``
        is absent. Mirrors upstream ``PDShading.getFunction()``.

        When ``/Function`` is an array of single-output functions (one per
        color component), this returns the raw ``COSArray`` — callers should
        use ``get_functions_array()`` to enumerate the per-component
        functions explicitly."""
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
        # Treat as iterable of PDFunction.
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


    # ---------- paint (rendering hook) ----------

    def to_paint(self, matrix: Any = None) -> Any:
        """Return a ``Type1ShadingPaint`` for this function-based shading.

        Mirrors upstream ``PDShadingType1.toPaint(Matrix)`` (line 104 of
        ``PDShadingType1.java``) which returns
        ``new Type1ShadingPaint(this, matrix)``. pypdfbox's rendering
        surface lands in a later wave, so the paint constructor isn't
        wired through yet — raises :class:`NotImplementedError` until
        it is.
        """
        raise NotImplementedError(
            "PDShadingType1.to_paint requires the rendering cluster; "
            "Type1ShadingPaint is not wired through yet"
        )


__all__ = ["PDShadingType1"]
