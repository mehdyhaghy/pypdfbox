from __future__ import annotations


class EndstreamFilterStream:
    """Filter helper used by ``read_until_end_stream`` to strip a
    trailing line break (CR LF or LF — but **not** a lone CR) from a
    stream body whose declared ``/Length`` is missing or wrong.

    Mirrors ``org.apache.pdfbox.pdfparser.EndstreamFilterStream``. The
    upstream class is package-private; we expose it on the module so
    higher-level recovery code (and tests) can drive it.

    The class does not actually emit bytes — it only computes how many
    bytes the *filtered* stream would have. The real byte sink is the
    output stream the caller is already writing to; this helper buffers
    the trailing CR/LF/CR LF across :meth:`filter` calls and decides at
    :meth:`calculate_length` whether to credit them. It also implements
    the PDFBOX-2120 heuristic: if the first ten bytes look like ASCII
    text, filtering is disabled wholesale (the trailing line break is
    significant and must be preserved).

    See ``EndstreamFilterStream.java`` for the original behaviour and
    PDFBOX-2079 / PDFBOX-2120 / PDFBOX-1164 for context.
    """

    __slots__ = ("_has_cr", "_has_lf", "_pos", "_must_filter", "_length")

    # Heuristic probe length used to decide whether the leading bytes
    # are ASCII text (disable filtering) or binary (filter trailing
    # newlines). Mirrors the literal ``10`` in upstream's ``filter``.
    _ASCII_PROBE_LENGTH: int = 10

    def __init__(self) -> None:
        self._has_cr: bool = False
        self._has_lf: bool = False
        self._pos: int = 0
        self._must_filter: bool = True
        self._length: int = 0

    # ---------- public API ----------

    def filter(self, data: bytes, off: int, length: int) -> None:
        """Account for ``data[off:off + length]`` in the filtered stream.

        Trailing CR / LF / CR LF are buffered across calls so a final
        line break at end-of-stream can be dropped by
        :meth:`calculate_length`.
        """
        if self._pos == 0 and length > self._ASCII_PROBE_LENGTH:
            # PDFBOX-2120: don't filter if the leading bytes look like
            # ASCII — preserve the trailing CR LF / LF in that case.
            self._must_filter = False
            for i in range(self._ASCII_PROBE_LENGTH):
                b = data[off + i]
                # Heuristic from PDFStreamParser (PDFBOX-1164).
                if b < 0x09 or (0x0A < b < 0x20 and b != 0x0D):
                    # Control character < 0x09 (or non-CR/LF in 0x0B..0x1F)
                    # — looks like binary, keep filtering.
                    self._must_filter = True
                    break
        if self._must_filter:
            # First, account for the CR/LF we kept from the previous call.
            if self._has_cr:
                self._has_cr = False
                if (
                    not self._has_lf
                    and length == 1
                    and data[off] == 0x0A
                ):
                    # Buffer is just a single LF — completes the CR LF
                    # we held back; drop everything (including the CR
                    # we'd otherwise keep) and bail.
                    return
                self._length += 1
            if self._has_lf:
                self._length += 1
                self._has_lf = False
            # Hold back a trailing CR / LF / CR LF from this buffer.
            if length > 0:
                last = data[off + length - 1]
                if last == 0x0D:  # '\r'
                    self._has_cr = True
                    length -= 1
                elif last == 0x0A:  # '\n'
                    self._has_lf = True
                    length -= 1
                    if length > 0 and data[off + length - 1] == 0x0D:
                        self._has_cr = True
                        length -= 1
        self._length += length
        self._pos += length

    def calculate_length(self) -> int:
        """Finalise: a held-back lone CR (no LF) is significant and is
        kept; a held-back CR LF / LF is dropped. Returns the total byte
        count of the filtered stream.
        """
        if self._has_cr and not self._has_lf:
            self._length += 1
            self._pos += 1
        self._has_cr = False
        self._has_lf = False
        return self._length
