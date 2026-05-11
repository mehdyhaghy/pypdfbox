from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_resource_cache import PDResourceCache

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_PATTERN: COSName = COSName.get_pdf_name("Pattern")
_PATTERN_TYPE: COSName = COSName.get_pdf_name("PatternType")
_MATRIX: COSName = COSName.get_pdf_name("Matrix")
_EXT_G_STATE: COSName = COSName.get_pdf_name("ExtGState")


class PDAbstractPattern:
    """Base wrapper for a PDF pattern dictionary. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.pattern.PDAbstractPattern``.

    Two concrete subclasses dispatch off ``/PatternType``:

    - ``PDTilingPattern`` (type 1) — a content-stream tile.
    - ``PDShadingPattern`` (type 2) — a shading reference.

    Lite surface: ``/Matrix`` is exposed as a ``list[float]`` (typed
    ``Matrix`` lands with the rendering cluster); ``/ExtGState`` keeps the
    original raw-dictionary getter for back-compat and also exposes the typed
    ``PDExtendedGraphicsState`` through ``get_ext_g_state``."""

    TYPE_TILING_PATTERN: int = 1
    TYPE_SHADING_PATTERN: int = 2

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict: COSDictionary = (
            dictionary if dictionary is not None else COSDictionary()
        )
        # Fresh dictionary gets ``/Type /Pattern``; existing dictionaries are
        # left untouched (upstream parity — see PDAbstractPattern() ctor).
        if dictionary is None and self._dict.get_dictionary_object(_TYPE) is None:
            self._dict.set_item(_TYPE, _PATTERN)

    # ---------- factory ----------

    @staticmethod
    def create(
        dictionary: COSDictionary | None,
        resource_cache: PDResourceCache | None = None,
    ) -> PDAbstractPattern | None:
        """Dispatch on ``/PatternType``. Returns ``None`` when ``dictionary``
        is ``None``; raises ``OSError`` for an unknown pattern type (mirrors
        upstream ``IOException``).

        ``resource_cache`` is forwarded to ``PDTilingPattern`` (mirrors
        upstream ``PDAbstractPattern.create(COSDictionary, ResourceCache)``);
        ignored for ``PDShadingPattern`` since shading patterns do not own
        a content-stream-bearing resources subtree."""
        # Local imports avoid a circular dependency between the abstract
        # base and its subclasses.
        from .pd_shading_pattern import PDShadingPattern  # noqa: PLC0415
        from .pd_tiling_pattern import PDTilingPattern  # noqa: PLC0415

        if dictionary is None:
            return None
        if not isinstance(dictionary, COSDictionary):
            raise TypeError(
                "PDAbstractPattern.create expects COSDictionary, got "
                f"{type(dictionary).__name__}"
            )
        pattern_type = dictionary.get_int(_PATTERN_TYPE, 0)
        if pattern_type == PDAbstractPattern.TYPE_TILING_PATTERN:
            return PDTilingPattern(dictionary, resource_cache=resource_cache)
        if pattern_type == PDAbstractPattern.TYPE_SHADING_PATTERN:
            return PDShadingPattern(dictionary)
        raise OSError(f"Error: Unknown pattern type {pattern_type}")

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Type ----------

    def get_type(self) -> str:
        """Always returns ``"Pattern"`` — the constant ``/Type`` value for
        a pattern dictionary. Mirrors upstream ``PDAbstractPattern.getType``."""
        return "Pattern"

    # ---------- /PatternType ----------

    def get_pattern_type(self) -> int:
        """Subclasses override to return their fixed pattern type code.

        Falls back to reading the ``/PatternType`` entry off the underlying
        dictionary when called on a bare ``PDAbstractPattern`` instance.
        Mirrors upstream's abstract method signature; the value is
        physically stored in COS so a base-level lookup is always
        available."""
        value = self._dict.get_int(_PATTERN_TYPE, 0)
        if value:
            return int(value)
        raise NotImplementedError(
            "PDAbstractPattern is abstract; override get_pattern_type"
        )

    def set_pattern_type(self, pattern_type: int) -> None:
        """Write ``/PatternType``. Mirrors upstream
        ``PDAbstractPattern.setPatternType``. The concrete subclasses
        override ``get_pattern_type`` to return their fixed code, but
        upstream still exposes a setter on the base for symmetry with
        ``setPaintType`` — we mirror that surface."""
        self._dict.set_int(_PATTERN_TYPE, int(pattern_type))

    # ---------- /PaintType (base for symmetry with upstream) ----------

    def set_paint_type(self, paint_type: int) -> None:
        """Write ``/PaintType``. Upstream defines this on the base class
        (overridden as a no-op refinement on ``PDTilingPattern``); we
        mirror that surface so callers can write ``/PaintType`` on either
        subclass without re-typing."""
        self._dict.set_int(COSName.get_pdf_name("PaintType"), int(paint_type))

    # ---------- /Matrix ----------

    def _matrix_values_or_none(self) -> list[float] | None:
        value = self._dict.get_dictionary_object(_MATRIX)
        if not isinstance(value, COSArray) or value.size() < 6:
            return None
        out: list[float] = []
        for i in range(6):
            entry = value.get_object(i)
            if not isinstance(entry, (COSInteger, COSFloat)):
                return None
            out.append(float(entry.value))
        return out

    def get_matrix(self) -> list[float]:
        """``/Matrix`` as a 6-tuple ``[a, b, c, d, e, f]``. Defaults to the
        identity matrix per PDF §8.7. Mirrors upstream's
        ``Matrix.createMatrix(...)`` semantics on the array form (a typed
        ``Matrix`` class lands with the rendering cluster).

        Permissive on malformed inputs — matches upstream
        ``Matrix.createMatrix`` which returns identity when the entry is
        missing, not a ``COSArray``, has fewer than 6 elements, or any
        element is not numeric."""
        return self._matrix_values_or_none() or [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

    def set_matrix(self, values) -> None:  # type: ignore[no-untyped-def]
        """Write ``/Matrix``. Accepts:

        - ``None`` — clears the entry.
        - ``COSArray`` — stored directly.
        - ``Sequence[float]`` of length 6 — wrapped as a ``COSArray`` of
          ``COSFloat``.
        - Any object with a callable ``get_matrix()`` that returns a
          6-element sequence (an ``AffineTransform``-like duck type) —
          mirrors upstream's ``setMatrix(AffineTransform)`` overload, which
          internally calls ``transform.getMatrix(double[])`` to extract the
          6 affine entries ``[a, b, c, d, e, f]``."""
        if values is None:
            self._dict.remove_item(_MATRIX)
            return
        if isinstance(values, COSArray):
            self._dict.set_item(_MATRIX, values)
            return
        # Duck-typed AffineTransform-like adapter: accept either a Pythonic
        # no-arg ``get_matrix()`` returning six values or the Java-shaped
        # ``getMatrix(double[])`` pattern that fills a caller-provided buffer.
        if not isinstance(values, (list, tuple)) and hasattr(values, "get_matrix"):
            get_matrix = values.get_matrix
            try:
                extracted = get_matrix()
            except TypeError:
                buffer = [0.0] * 6
                extracted = get_matrix(buffer)
                if extracted is None:
                    extracted = buffer
            try:
                length = len(extracted)
            except TypeError as exc:
                raise TypeError(
                    "set_matrix received an object whose get_matrix() "
                    "returned a non-sequence value"
                ) from exc
            if length != 6:
                raise ValueError(
                    "/Matrix expects exactly 6 numbers (a b c d e f); "
                    f"AffineTransform-like adapter yielded {length}"
                )
            arr = COSArray([COSFloat(float(v)) for v in extracted])
            self._dict.set_item(_MATRIX, arr)
            return
        if len(values) != 6:
            raise ValueError(
                f"/Matrix expects exactly 6 numbers (a b c d e f); got {len(values)}"
            )
        arr = COSArray([COSFloat(float(v)) for v in values])
        self._dict.set_item(_MATRIX, arr)

    def has_matrix(self) -> bool:
        """``True`` when ``/Matrix`` is present as a valid six-number
        ``COSArray``. Malformed entries return ``False`` because
        :meth:`get_matrix` will fall back to identity for them."""
        return self._matrix_values_or_none() is not None

    def clear_matrix(self) -> None:
        """Remove ``/Matrix``. No-op if absent."""
        self._dict.remove_item(_MATRIX)

    # ---------- /ExtGState ----------

    def get_extended_graphics_state(self) -> COSDictionary | None:
        """Raw ``/ExtGState`` dictionary if present, else ``None``.

        Kept as a back-compat raw accessor; prefer the typed
        ``get_ext_g_state`` (upstream's ``getExtGState`` spelling)."""
        value = self._dict.get_dictionary_object(_EXT_G_STATE)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_extended_graphics_state(
        self, extgs: COSDictionary | None
    ) -> None:
        """Back-compat raw setter. Prefer ``set_ext_g_state``."""
        if extgs is None:
            self._dict.remove_item(_EXT_G_STATE)
            return
        self._dict.set_item(_EXT_G_STATE, extgs)

    def has_extended_graphics_state(self) -> bool:
        """``True`` when ``/ExtGState`` is present as a ``COSDictionary``."""
        return isinstance(
            self._dict.get_dictionary_object(_EXT_G_STATE), COSDictionary
        )

    def clear_extended_graphics_state(self) -> None:
        """Remove ``/ExtGState``. No-op if absent."""
        self._dict.remove_item(_EXT_G_STATE)

    def get_ext_g_state(self):  # type: ignore[no-untyped-def]
        """Typed ``/ExtGState`` accessor — mirrors upstream
        ``PDAbstractPattern.getExtGState``. Returns a
        ``PDExtendedGraphicsState`` wrapper around the raw dictionary, or
        ``None`` when the entry is missing or not a dictionary."""
        # Local import — PDExtendedGraphicsState lives under graphics.state
        # which we don't want to drag in at module-load time (keeps the
        # pattern module dependency-light).
        from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (  # noqa: PLC0415
            PDExtendedGraphicsState,
        )

        value = self._dict.get_dictionary_object(_EXT_G_STATE)
        if isinstance(value, COSDictionary):
            return PDExtendedGraphicsState(value)
        return None

    def set_ext_g_state(self, ext_g_state) -> None:  # type: ignore[no-untyped-def]
        """Typed ``/ExtGState`` setter. Accepts a
        ``PDExtendedGraphicsState``, a raw ``COSDictionary``, or ``None``
        (clears the entry)."""
        from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (  # noqa: PLC0415
            PDExtendedGraphicsState,
        )

        if ext_g_state is None:
            self._dict.remove_item(_EXT_G_STATE)
            return
        if isinstance(ext_g_state, PDExtendedGraphicsState):
            self._dict.set_item(_EXT_G_STATE, ext_g_state.get_cos_object())
            return
        if isinstance(ext_g_state, COSDictionary):
            self._dict.set_item(_EXT_G_STATE, ext_g_state)
            return
        raise TypeError(
            "set_ext_g_state expects PDExtendedGraphicsState, COSDictionary, "
            f"or None; got {type(ext_g_state).__name__}"
        )

    def has_ext_g_state(self) -> bool:
        """Alias of :meth:`has_extended_graphics_state` using upstream's
        shorter ``ExtGState`` spelling."""
        return self.has_extended_graphics_state()

    def clear_ext_g_state(self) -> None:
        """Alias of :meth:`clear_extended_graphics_state` using upstream's
        shorter ``ExtGState`` spelling."""
        self.clear_extended_graphics_state()

    # ---------- type predicates ----------

    def is_tiling_pattern(self) -> bool:
        """``True`` when this is a tiling pattern (``/PatternType 1``)."""
        return self.get_pattern_type() == PDAbstractPattern.TYPE_TILING_PATTERN

    def is_shading_pattern(self) -> bool:
        """``True`` when this is a shading pattern (``/PatternType 2``)."""
        return self.get_pattern_type() == PDAbstractPattern.TYPE_SHADING_PATTERN


__all__ = ["PDAbstractPattern"]
