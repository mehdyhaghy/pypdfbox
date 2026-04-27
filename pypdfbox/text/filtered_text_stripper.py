"""Rotation-aware text-extraction helpers used by the ``-rotationMagic``
flag in ``pypdfbox extracttext``.

Ported from upstream ``org.apache.pdfbox.tools.ExtractText`` (PDFBox 3.0),
where ``FilteredTextStripper``, ``AngleCollector``, and the static
``getAngle(TextPosition)`` helper all live as package-private classes
inside ``ExtractText.java``. We split them into the ``text`` module
because the API is reusable beyond the CLI tool — any caller can build a
``FilteredTextStripper(target_angle=90)`` to pull only the vertical text
out of a mixed-orientation page.

Upstream's strategy for handling rotated text in ``ExtractText``:

1. Run :class:`AngleCollector` once per page to discover the set of
   text-matrix rotations actually present (rounded to integer degrees).
2. For each angle, "un-rotate" the page by prepending a ``cm`` operator
   to the content stream, then run :class:`FilteredTextStripper` (which
   skips any glyph whose post-rotation angle is not zero).
3. Restore the page's content stream and ``/Rotate`` entry.

The pypdfbox lite stripper does not currently track the CTM, so the
"prepend a transform" trick is a no-op for us. Instead,
:class:`FilteredTextStripper` accepts a ``target_angle`` parameter that
defaults to ``0`` (matching upstream's hard-coded check) but can be set
to ``90`` / ``180`` / ``270`` directly. This skips the prepend dance
entirely while preserving the upstream contract that the stripper only
emits text whose text matrix matches the requested angle.

The angle is computed exactly as upstream does (see ``getAngle`` in
``ExtractText.java``):

    angle = atan2(text_matrix.b, text_matrix.d)  // post font-matrix concat

Upright (TrueType-default) font matrices have shape
``[s, 0, 0, s, 0, 0]`` for some scale ``s``, so ``atan2(s*b, s*d) ==
atan2(b, d)`` and the font matrix can be skipped without loss for the
fonts the lite stripper exposes today.
"""
from __future__ import annotations

import math

from .pdf_text_stripper import PDFTextStripper, _TextState
from .text_position import TextPosition

__all__ = ["AngleCollector", "FilteredTextStripper", "get_angle"]


def get_angle(text: TextPosition) -> int:
    """Return the rotation, in integer degrees, of ``text``'s text matrix.

    Mirrors the static ``ExtractText.getAngle(TextPosition)`` helper.
    Result is normalised to ``[0, 360)`` so callers can use plain ``==``
    comparisons against ``0`` / ``90`` / ``180`` / ``270``.
    """
    matrix = text.get_text_matrix()
    if matrix is None or len(matrix) < 4:
        return 0
    b = float(matrix[1])
    d = float(matrix[3])
    angle = int(round(math.degrees(math.atan2(b, d))))
    return (angle + 360) % 360


def _state_angle(state: _TextState) -> int:
    """Compute the integer-degree rotation of ``state``'s current text
    matrix without materialising a :class:`TextPosition`."""
    angle = int(round(math.degrees(math.atan2(state.tm_b, state.tm_d))))
    return (angle + 360) % 360


class AngleCollector(PDFTextStripper):
    """Discover which text rotations occur on a page.

    Mirrors the package-private ``AngleCollector`` class upstream uses to
    drive ``-rotationMagic``. ``get_text(document)`` runs the parser for
    its side effect of collecting angles; the returned string is
    discarded by the caller (upstream pipes it into a ``NullWriter``).

    Each new ``AngleCollector`` instance starts with an empty angle set,
    so callers must construct a fresh collector per page when they want
    per-page granularity (the upstream comment requires the same).
    """

    def __init__(self) -> None:
        super().__init__()
        self._angles: set[int] = set()

    def get_angles(self) -> set[int]:
        """Return the set of integer-degree rotations seen so far. Sorted
        iteration is the caller's responsibility (use ``sorted(...)``)."""
        return self._angles

    def _emit(self, s, state, positions):  # type: ignore[override]
        # Record the angle. We still call super so the parent populates
        # ``positions`` with the (filterless) extraction; upstream's
        # ``processTextPosition`` short-circuits at the same point.
        self._angles.add(_state_angle(state))
        super()._emit(s, state, positions)


class FilteredTextStripper(PDFTextStripper):
    """``PDFTextStripper`` that only emits text matching ``target_angle``.

    Subclassing follows upstream's structure (also a ``PDFTextStripper``
    subclass), and the behaviour matches: glyphs whose text-matrix
    rotation differs from the configured angle are silently dropped.

    Parameters
    ----------
    target_angle:
        Rotation in degrees that emitted text must match. Normalised to
        ``[0, 360)`` and rounded to int. Defaults to ``0``, matching
        upstream's hard-coded ``if (angle == 0)`` check.
    """

    def __init__(self, target_angle: int = 0) -> None:
        super().__init__()
        self._target_angle = (int(target_angle) + 360) % 360

    def get_target_angle(self) -> int:
        return self._target_angle

    def set_target_angle(self, angle: int) -> None:
        self._target_angle = (int(angle) + 360) % 360

    def _emit(self, s, state, positions):  # type: ignore[override]
        if _state_angle(state) != self._target_angle:
            return
        super()._emit(s, state, positions)

    def _emit_tj_array(self, arr, state, positions):  # type: ignore[override]
        if _state_angle(state) != self._target_angle:
            return
        super()._emit_tj_array(arr, state, positions)
