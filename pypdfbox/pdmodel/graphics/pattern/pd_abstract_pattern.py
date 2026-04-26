from __future__ import annotations

from collections.abc import Sequence

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)

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
    ``Matrix`` lands with the rendering cluster); ``/ExtGState`` is
    returned as the raw ``COSDictionary`` (typed
    ``PDExtendedGraphicsState`` is wrapped on the shading subclass)."""

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
    def create(dictionary: COSDictionary | None) -> PDAbstractPattern | None:
        """Dispatch on ``/PatternType``. Returns ``None`` when ``dictionary``
        is ``None``; raises ``OSError`` for an unknown pattern type (mirrors
        upstream ``IOException``)."""
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
            return PDTilingPattern(dictionary)
        if pattern_type == PDAbstractPattern.TYPE_SHADING_PATTERN:
            return PDShadingPattern(dictionary)
        raise OSError(f"Error: Unknown pattern type {pattern_type}")

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /PatternType ----------

    def get_pattern_type(self) -> int:
        """Subclasses override to return their fixed pattern type code."""
        raise NotImplementedError

    # ---------- /Matrix ----------

    def get_matrix(self) -> list[float]:
        """``/Matrix`` as a 6-tuple ``[a, b, c, d, e, f]``. Defaults to the
        identity matrix per PDF §8.7. Mirrors upstream's
        ``Matrix.createMatrix(...)`` semantics on the array form (a typed
        ``Matrix`` class lands with the rendering cluster)."""
        value = self._dict.get_dictionary_object(_MATRIX)
        if isinstance(value, COSArray) and value.size() >= 6:
            out: list[float] = []
            for i in range(6):
                entry = value.get_object(i)
                if isinstance(entry, (COSInteger, COSFloat)):
                    out.append(float(entry.value))
                else:
                    raise TypeError(
                        f"/Matrix entry {i} is not numeric: {type(entry).__name__}"
                    )
            return out
        return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

    def set_matrix(self, values: Sequence[float] | COSArray | None) -> None:
        if values is None:
            self._dict.remove_item(_MATRIX)
            return
        if isinstance(values, COSArray):
            self._dict.set_item(_MATRIX, values)
            return
        if len(values) != 6:
            raise ValueError(
                f"/Matrix expects exactly 6 numbers (a b c d e f); got {len(values)}"
            )
        arr = COSArray([COSFloat(float(v)) for v in values])
        self._dict.set_item(_MATRIX, arr)

    # ---------- /ExtGState ----------

    def get_extended_graphics_state(self) -> COSDictionary | None:
        """Raw ``/ExtGState`` dictionary if present, else ``None``. The
        typed ``PDExtendedGraphicsState`` wrapper is provided on
        ``PDShadingPattern`` (upstream API surface)."""
        value = self._dict.get_dictionary_object(_EXT_G_STATE)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_extended_graphics_state(
        self, extgs: COSDictionary | None
    ) -> None:
        if extgs is None:
            self._dict.remove_item(_EXT_G_STATE)
            return
        self._dict.set_item(_EXT_G_STATE, extgs)


__all__ = ["PDAbstractPattern"]
