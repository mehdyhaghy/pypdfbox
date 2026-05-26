"""Arithmetic coding context used during JBIG2 bitstream decoding.

Port of ``org.apache.pdfbox.jbig2.decoder.arithmetic.CX``.

Represents a context in the arithmetic decoder that selects probability
estimates and statistics used during decoding procedures, as defined in
ITU-T Rec. T.88 (2000 E), ISO/IEC 14492:2001.

Context state:
  * ``cx`` array: stores the probability-estimate index (0-127) for each
    context state.
  * ``mps`` array: stores the most probable symbol (0 or 1) for each context
    state.
  * ``index``: current context index, selected based on the neighbourhood
    pattern (template-specific arrangement of previously decoded pixels).

The index is set before each decision to select which context state to use.
After decoding, the arithmetic decoder updates the selected context's
probability estimate and MPS based on the decoded symbol (see Annex A, T.88).

When arithmetic coding contexts are retained and reused across segments
(§7.4.2.2), a :meth:`copy` must be created to avoid sharing mutable
probability state between decoders.
"""

from __future__ import annotations


class CX:
    """Arithmetic decoder context (index + per-state probability/MPS arrays)."""

    def __init__(self, size: int, index: int) -> None:
        """Create a context with ``size`` states and an initial ``index``.

        All probability estimates are initialised to 0, and all MPS values are
        initialised to 0.
        """
        self.index = index
        # Java ``byte[]`` zero-initialised; a bytearray mirrors the
        # fixed-width, mutable, default-0 semantics.
        self._cx = bytearray(size)
        self._mps = bytearray(size)

    def cx(self) -> int:
        return self._cx[self.index] & 0x7F

    def set_cx(self, value: int) -> None:
        self._cx[self.index] = value & 0x7F

    def mps(self) -> int:
        """Return the decision. Possible values are ``0`` or ``1``."""
        return self._mps[self.index]

    def toggle_mps(self) -> None:
        """Flip the bit in the actual "more predictable symbol" array element."""
        self._mps[self.index] ^= 1

    def get_index(self) -> int:
        return self.index

    def set_index(self, index: int) -> None:
        """Set the context index used for subsequent decoding decisions.

        The index selects which context state's probability estimate and MPS
        will be used. The index value is typically computed from the
        neighbouring pixels in the template (§6.2.5.1 for generic regions,
        §6.4.7.1 for text regions).
        """
        self.index = index

    def copy(self) -> CX:
        """Return a deep copy of this context.

        The new instance has the same context values, probability estimates and
        current index, but is a separate instance. Changes to the copied object
        do not affect the original, and vice versa. Required when reusing
        arithmetic coding contexts across segments, to avoid sharing mutable
        probability state between decoders.
        """
        result = CX(len(self._cx), self.index)
        result._cx[:] = self._cx
        result._mps[:] = self._mps
        return result
