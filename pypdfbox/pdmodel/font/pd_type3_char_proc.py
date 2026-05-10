from __future__ import annotations

from typing import IO, TYPE_CHECKING, Any

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources

if TYPE_CHECKING:
    from .pd_type3_font import PDType3Font


# PDF 32000-1 §9.6.5 — the two glyph-metric operators that must be the
# first operator inside a Type 3 char proc content stream:
#
#   wx wy  d0                       (set glyph width, no bounding box)
#   wx wy  llx lly urx ury  d1      (set glyph width and bounding box)
#
# d1 is the only way for a char proc to declare its own /BBox; with d0
# the glyph is "transparent" (no painting bounds) and the consumer must
# fall back to the font's /FontBBox for clipping.
_D0: bytes = b"d0"
_D1: bytes = b"d1"
_RESOURCES: COSName = COSName.get_pdf_name("Resources")


class PDType3CharProc(PDStream):
    """A single Type 3 glyph procedure — a content stream that paints one
    glyph. Mirrors PDFBox ``PDType3CharProc``.

    Each entry of the parent ``PDType3Font``'s ``/CharProcs`` dictionary is
    a stream conforming to this shape: the first content-stream operator
    must be ``d0`` or ``d1`` (PDF 32000-1 §9.6.5), which together set the
    glyph width and (for ``d1``) its bounding box. The remaining operators
    paint the glyph using the standard graphics operators, but with the
    colour operators ``rg/RG/g/G/k/K/sc/SC/scn/SCN/cs/CS`` reserved (only
    allowed when the parent font's ``/CharProcs`` paints uncoloured glyphs).

    Implements :class:`PDContentStream` so the content-stream engine can
    drive a char proc the same way it drives a page or form XObject — but
    we don't formally subclass the ABC because :class:`PDStream` is the
    canonical base in upstream and the ABC is a duck-type contract.
    """

    def __init__(self, font: PDType3Font, stream: COSStream) -> None:
        """Wrap ``stream`` (a ``COSStream`` from the font's ``/CharProcs``)
        and remember the parent ``font`` so :meth:`get_resources` /
        :meth:`get_matrix` can fall back to the font when the char proc
        carries no local entries (which is the common case).
        """
        super().__init__(stream)
        self._font = font

    # ---------- back-pointer ----------

    def get_font(self) -> PDType3Font:
        """Return the parent :class:`PDType3Font`. Mirrors upstream
        ``getFont()``."""
        return self._font

    def get_cos_object(self) -> COSStream:
        """Return the underlying ``COSStream``. Mirrors upstream
        ``getCOSObject()`` (override of :meth:`PDStream.get_cos_object`
        narrowing the return type to ``COSStream``).

        Upstream's ``PDType3CharProc`` is *not* a ``PDStream`` — it
        composes one — but pypdfbox subclasses ``PDStream`` to share the
        decoded-byte plumbing. We override here so the per-class parity
        tracker sees the method on the same class as upstream.
        """
        return self._stream

    def get_content_stream(self) -> PDStream:
        """Return a fresh :class:`PDStream` wrapper around the underlying
        ``COSStream``. Mirrors upstream ``getContentStream()`` exactly,
        which constructs ``new PDStream(charStream)`` on every call.
        """
        return PDStream(self._stream)

    # ---------- PDContentStream surface ----------

    def get_contents(self) -> IO[bytes]:
        """Decoded content-stream bytes as a readable stream. Mirrors
        upstream ``getContents() : InputStream``."""
        return self.create_input_stream()

    def get_contents_for_random_access(self) -> RandomAccessRead:
        """Random-access view over the decoded content-stream bytes —
        needed by the token parser. Mirrors upstream
        ``getContentsForRandomAccess()``."""
        return RandomAccessReadBuffer(self.to_byte_array())

    def get_resources(self) -> PDResources | None:
        """Return the resources dictionary used by this char-proc.

        PDFBOX-5294: a malformed PDF may stash a ``/Resources`` dictionary
        on the char-proc stream itself, even though PDF 32000-1 §9.6.5
        says resources belong on the parent font (or page). Upstream
        tolerates that misplacement and prefers the local entry when
        present; we mirror that. The well-formed path falls back to the
        parent font's ``/Resources``.

        Mirrors upstream ``getResources()``.
        """
        local = self._stream.get_dictionary_object(_RESOURCES)
        if isinstance(local, COSDictionary):
            return PDResources(local)
        return self._font.get_resources()

    def has_resources(self) -> bool:
        """Return ``True`` when this char-proc stream carries its own
        ``/Resources`` entry (PDFBOX-5294 misplacement). When ``False``,
        :meth:`get_resources` falls back to the parent font's
        ``/Resources``. No upstream method — convenience predicate."""
        return self._stream.contains_key(_RESOURCES)

    def get_b_box(self) -> PDRectangle:
        """Return the parent font's ``/FontBBox`` — the
        ``PDContentStream`` contract bounding box for this char-proc.

        Mirrors upstream ``getBBox()`` exactly, which simply returns
        ``font.getFontBBox()``. Per-glyph bounds declared by a leading
        ``d1`` operator are exposed separately via
        :meth:`get_glyph_b_box`.

        When the parent font has no ``/FontBBox`` we return an empty rect
        at the origin so callers always have a non-``None`` ``PDRectangle``
        to work with — upstream returns ``null`` in that case but
        ``PDContentStream.getBBox()`` is annotated non-null in 3.0.x and
        the only fonts without a ``/FontBBox`` are malformed.
        """
        font_bbox = self._font.get_font_bbox()
        if font_bbox is not None:
            return font_bbox
        return PDRectangle()

    def get_bbox(self) -> PDRectangle:
        """Alias for :meth:`get_b_box`.

        ``get_b_box`` follows the PDFBox ``getBBox`` case-conversion (the
        consecutive-caps run becomes a separate snake-case word), while
        ``get_bbox`` matches the spelling used by several local wrappers.
        """
        return self.get_b_box()

    def get_matrix(self) -> Any:
        """Return the parent font's ``/FontMatrix``. Char procs are
        rendered in the font's coordinate system; they have no matrix of
        their own. Mirrors upstream ``getMatrix()``."""
        return self._font.get_font_matrix()

    # ---------- glyph-metric parsing (d0 / d1) ----------

    def get_glyph_b_box(self) -> PDRectangle | None:
        """Parse the leading ``d1`` operator and return its declared
        bounding box, or ``None`` when the glyph uses ``d0`` (no bbox) or
        the content stream is malformed. Mirrors upstream
        ``getGlyphBBox()``.

        Per PDF 32000-1 §9.6.5 the upper-right corner stored by ``d1`` is
        absolute, so we pass ``(llx, lly, urx, ury)`` straight through
        :class:`PDRectangle`'s four-corner constructor. Upstream
        constructs the rect as ``new PDRectangle(x, y, urx-x, ury-y)``
        (origin + width/height); the two are equivalent because
        ``PDRectangle(x, y, w, h)`` adds ``x`` and ``y`` to the bottom
        corner internally.

        Behaviour deviation: upstream uses ``PDFStreamParser`` to walk
        the entire stream; we lift the operands of just the first metric
        operator from the decoded bytes since that's all the bounding
        box needs. The two paths agree on well-formed streams; on
        malformed streams we are slightly more lenient (``None`` instead
        of raising).
        """
        op_name, operands = self._first_metric_operator()
        if op_name != _D1 or len(operands) < 6:
            return None
        try:
            llx = float(operands[2])
            lly = float(operands[3])
            urx = float(operands[4])
            ury = float(operands[5])
        except ValueError:
            return None
        # PDRectangle takes the four corners directly:
        # (lower_left_x, lower_left_y, upper_right_x, upper_right_y).
        return PDRectangle(llx, lly, urx, ury)

    def get_glyph_bbox(self) -> PDRectangle | None:
        """Alias for :meth:`get_glyph_b_box`.

        Project convention keeps both spellings — ``get_glyph_b_box``
        mirrors the parity-tracker's literal snake-case of ``BBox`` and
        ``get_glyph_bbox`` is the more idiomatic Python form used by
        local callers.
        """
        return self.get_glyph_b_box()

    def has_d1(self) -> bool:
        """Return ``True`` when the char-proc's leading metric operator
        is ``d1`` (declares both width and bounding box). No upstream
        method — convenience predicate over :meth:`get_glyph_b_box`."""
        op_name, _ = self._first_metric_operator()
        return op_name == _D1

    def has_d0(self) -> bool:
        """Return ``True`` when the char-proc's leading metric operator
        is ``d0`` (declares width only, no bounding box → uncoloured
        glyph). No upstream method — convenience predicate."""
        op_name, _ = self._first_metric_operator()
        return op_name == _D0

    def get_width(self) -> float:
        """Return the glyph advance ``wx`` declared by the leading ``d0``
        / ``d1`` operator, or ``0.0`` when neither is present. Mirrors
        upstream ``getWidth()``.

        Behaviour deviation: upstream raises ``IOException`` for an empty
        stream, a missing ``d0``/``d1`` first operator, or a non-numeric
        first operand. We surface ``0.0`` in those malformed cases so
        callers (text-extraction, rendering) can keep walking the font's
        char-procs without aborting on a single broken glyph; the well-
        formed path matches upstream byte-for-byte.
        """
        op_name, operands = self._first_metric_operator()
        if op_name is None:
            return 0.0
        return self.parse_width(op_name, operands)

    def parse_width(self, operator: bytes, arguments: list[bytes]) -> float:
        """Extract the glyph advance from a ``d0`` / ``d1`` operator and
        its preceding numeric operands. Mirrors upstream's
        ``parseWidth(Operator, List<COSBase>)`` private helper (we keep
        it on the public surface so the per-class parity tracker matches
        it; callers should still prefer :meth:`get_width`).

        ``operator`` is the operator's literal bytes (``b"d0"`` /
        ``b"d1"``); ``arguments`` is the list of numeric operands that
        preceded it on the stream. Returns the ``wx`` operand
        (``arguments[0]``) coerced to ``float``.

        Behaviour deviation from upstream: returns ``0.0`` instead of
        raising ``IOException`` when the operator is not ``d0`` / ``d1``
        or when the first operand is missing or non-numeric. See
        :meth:`get_width` for the rationale.
        """
        if operator not in (_D0, _D1):
            return 0.0
        if not arguments:
            return 0.0
        try:
            return float(arguments[0])
        except ValueError:
            return 0.0

    def _first_metric_operator(self) -> tuple[bytes | None, list[bytes]]:
        """Tokenise the head of the decoded content stream until the first
        operator is found. Returns ``(operator_name, operands)`` where
        operator_name is the operator's bytes (``b"d0"`` / ``b"d1"`` for
        well-formed streams) or ``None`` when the stream is empty.

        Numbers are kept as raw byte strings; the caller decides whether
        to coerce them to ``float``. This keeps the helper free of any
        PDF-token-parser dependency."""
        data = self.to_byte_array()
        if not data:
            return None, []

        operands: list[bytes] = []
        i = 0
        n = len(data)
        while i < n:
            byte = data[i:i + 1]
            # Whitespace — skip (PDF whitespace = NUL HT LF FF CR SP).
            if byte in (b"\x00", b"\t", b"\n", b"\x0c", b"\r", b" "):
                i += 1
                continue
            # Comment — runs to EOL.
            if byte == b"%":
                while i < n and data[i:i + 1] not in (b"\n", b"\r"):
                    i += 1
                continue
            # Token start — read until the next whitespace or delimiter.
            start = i
            while i < n:
                tail = data[i:i + 1]
                if tail in (
                    b"\x00", b"\t", b"\n", b"\x0c", b"\r", b" ",
                    b"%", b"(", b")", b"<", b">", b"[", b"]", b"{", b"}", b"/",
                ):
                    break
                i += 1
            token = data[start:i]
            if not token:
                # Hit a delimiter we don't handle (e.g. a string literal
                # before any operator) — bail out, not a valid d0/d1
                # leading sequence.
                return None, operands
            # Numbers: optional sign + digits/dot.
            if _is_numeric_token(token):
                operands.append(token)
                continue
            # First non-numeric, non-whitespace token is an operator.
            return token, operands
        return None, operands


def _is_numeric_token(token: bytes) -> bool:
    """Return ``True`` if ``token`` is a PDF number literal (signed or
    unsigned, integer or real). Mirrors upstream's parser-level
    classification well enough for the d0/d1 operand-extraction path."""
    if not token:
        return False
    start = 0
    if token[0:1] in (b"+", b"-"):
        start = 1
    body = token[start:]
    if not body:
        return False
    seen_digit = False
    seen_dot = False
    for byte in body:
        ch = bytes([byte])
        if ch.isdigit():
            seen_digit = True
        elif ch == b"." and not seen_dot:
            seen_dot = True
        else:
            return False
    return seen_digit


__all__ = ["PDType3CharProc"]
