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
from collections.abc import Iterator
from typing import Any, cast

from pypdfbox.cos import COSArray, COSString

from .pdf_text_stripper import PDFTextStripper, _TextState
from .text_position import TextPosition

__all__ = [
    "AngleCollector",
    "FilteredTextStripper",
    "get_angle",
    "get_angle_from_matrix",
]


def get_angle_from_matrix(matrix: list[float] | tuple[float, ...] | None) -> int:
    """Return the rotation, in integer degrees, encoded by ``matrix``.

    Companion to :func:`get_angle` for callers that already hold the raw
    ``[a, b, c, d, e, f]`` text-matrix list (e.g. inside dispatch loops
    where materialising a :class:`TextPosition` is wasteful). Behaves
    identically to :func:`get_angle` — result is normalised to
    ``[0, 360)`` and ``None`` / short matrices return ``0``.
    """
    if matrix is None or len(matrix) < 4:
        return 0
    b = float(matrix[1])
    d = float(matrix[3])
    angle = int(round(math.degrees(math.atan2(b, d))))
    return (angle + 360) % 360


def get_angle(text: TextPosition) -> int:
    """Return the rotation, in integer degrees, of ``text``'s text matrix.

    Mirrors the static ``ExtractText.getAngle(TextPosition)`` helper.
    Result is normalised to ``[0, 360)`` so callers can use plain ``==``
    comparisons against ``0`` / ``90`` / ``180`` / ``270``.
    """
    return get_angle_from_matrix(text.get_text_matrix())


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
        iteration is the caller's responsibility (use ``sorted(...)`` or
        :meth:`get_sorted_angles`)."""
        return self._angles

    def get_sorted_angles(self) -> list[int]:
        """Return the collected angles as an ascending-sorted ``list``.

        Mirrors the iteration order of upstream's ``TreeSet<Integer>``
        backing store — useful when the caller needs deterministic
        per-page ordering (e.g. for the ``-rotationMagic`` extractor's
        un-rotate loop, which always processes ``0``, then ``90``, ``180``,
        ``270``).
        """
        return sorted(self._angles)

    def clear_angles(self) -> None:
        """Drop every angle recorded so far.

        Upstream AngleCollector's docstring requires constructing a fresh
        instance per page so the angle set starts empty. ``clear_angles``
        is a Pythonic alternative — it lets a long-lived collector be
        reused page-to-page without allocating, while still satisfying the
        per-page-empty contract.
        """
        self._angles.clear()

    def has_angle(self, angle: int) -> bool:
        """Return ``True`` iff ``angle`` (normalised to ``[0, 360)``) was
        recorded by this collector. Mirrors ``Set.contains`` semantics on
        the upstream ``TreeSet<Integer>``.
        """
        return ((int(angle) + 360) % 360) in self._angles

    def __contains__(self, angle: object) -> bool:
        try:
            return ((int(cast(Any, angle)) + 360) % 360) in self._angles
        except (TypeError, ValueError):
            return False

    def __len__(self) -> int:
        return len(self._angles)

    def __iter__(self) -> Iterator[int]:
        # Iterate in ascending order to match upstream ``TreeSet``
        # iteration semantics — callers that just need a deterministic
        # walk can do ``for a in collector`` instead of
        # ``for a in collector.get_sorted_angles()``.
        return iter(sorted(self._angles))

    def process_text_position(self, text: TextPosition) -> None:
        self._angles.add(get_angle(text))

    def should_skip_glyph(self, text: TextPosition) -> bool:
        self.process_text_position(text)
        return True

    def _emit(
        self,
        s: COSString,
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        before = len(positions)
        super()._emit(s, state, positions)
        if len(positions) > before:
            self._angles.add(_state_angle(state))


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

    def is_target_angle(self, angle: int) -> bool:
        """Return ``True`` iff ``angle`` (normalised to ``[0, 360)``)
        equals the configured target. Convenience predicate for callers
        that want to short-circuit a glyph dispatch loop without
        re-implementing the modulo dance.
        """
        return ((int(angle) + 360) % 360) == self._target_angle

    def process_text_position(self, text: TextPosition) -> None:
        if get_angle(text) == self._target_angle:
            super().process_text_position(text)

    def should_skip_glyph(self, text: TextPosition) -> bool:
        return get_angle(text) != self._target_angle

    def _emit(
        self,
        s: COSString,
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        if _state_angle(state) != self._target_angle:
            return
        super()._emit(s, state, positions)

    def _emit_tj_array(
        self,
        arr: COSArray,
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        if _state_angle(state) != self._target_angle:
            return
        super()._emit_tj_array(arr, state, positions)
