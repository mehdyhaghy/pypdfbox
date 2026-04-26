from __future__ import annotations


class CodespaceRange:
    """
    A single ``begincodespacerange`` entry from a CMap.

    The lengths of ``start_bytes`` and ``end_bytes`` must match. Per the
    PostScript CMap spec, two-byte (and longer) codespace ranges are
    rectangular — each byte position must lie independently within
    ``[start[i], end[i]]`` for the range to match. A single-byte range
    is the trivial linear case.

    Special case (PDFBOX-4923): a one-byte ``<00>`` start paired with a
    multi-byte end is accepted by widening the start to the same length
    with leading zero bytes.
    """

    def __init__(
        self,
        start_bytes: bytes | bytearray | memoryview,
        end_bytes: bytes | bytearray | memoryview,
    ) -> None:
        start = bytes(start_bytes)
        end = bytes(end_bytes)
        if len(start) != len(end):
            # PDFBOX-4923 — accept "1 begincodespacerange <00> <ffff>" style.
            if len(start) == 1 and start[0] == 0:
                start = b"\x00" * len(end)
            else:
                raise ValueError(
                    "The start and the end values must not have different lengths."
                )
        self._start: tuple[int, ...] = tuple(start)
        self._end: tuple[int, ...] = tuple(end)
        self._code_length: int = len(end)

    def get_code_length(self) -> int:
        return self._code_length

    def matches(self, code: bytes | bytearray | memoryview) -> bool:
        """True iff ``code`` (length-checked) lies within this range."""
        return self.is_full_match(code, len(code))

    def is_full_match(
        self, code: bytes | bytearray | memoryview, code_len: int
    ) -> bool:
        """True iff the first ``code_len`` bytes of ``code`` lie within this
        range and ``code_len`` matches this range's ``code_length``."""
        if self._code_length != code_len:
            return False
        for i in range(self._code_length):
            b = code[i] & 0xFF
            if b < self._start[i] or b > self._end[i]:
                return False
        return True
