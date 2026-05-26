from __future__ import annotations

from typing import BinaryIO, Final

from pypdfbox.cos import COSDictionary

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory

# ISO 32000-1 §7.4.7 JBIG2Decode parameter keys.
_JBIG2_GLOBALS: Final[str] = "JBIG2Globals"

#: Message raised when ``/JBIG2Decode`` decode is attempted. The only
#: available JBIG2 decoder (``jbig2-parser``, which statically links the
#: Rust ``jbig2dec`` crate — a binding to Artifex's AGPL ``jbig2dec`` C
#: library) is GPL-3.0/AGPL-licensed and therefore excluded by the
#: project's permissive-only license policy (CLAUDE.md §4).
_UNSUPPORTED_MESSAGE: Final[str] = (
    "JBIG2Decode is not supported: the only available JBIG2 decoder "
    "(jbig2-parser → jbig2dec) is GPL-3.0/AGPL-licensed and is excluded by "
    "the project's permissive-only license policy (CLAUDE.md §4). The "
    "/JBIG2Decode filter is intentionally unsupported."
)


class JBIG2Decode(Filter):
    """``/JBIG2Decode`` filter (ISO 32000-1 §7.4.7) — intentionally unsupported.

    JBIG2 (ITU-T T.88) decoding is **not implemented** in pypdfbox. The
    only available JBIG2 decoder is ``jbig2-parser``, whose compiled
    extension statically links the Rust ``jbig2dec`` crate — a binding to
    Artifex's AGPL ``jbig2dec`` C library. GPL-3.0/AGPL are on the
    project's hard-forbidden license list (CLAUDE.md §4), so no JBIG2
    decoder is bundled and :meth:`decode` raises ``OSError``.

    The filter is still **registered** with :class:`FilterFactory` so
    ``/JBIG2Decode`` is recognised as a known filter name (and image
    XObjects can detect the filter); it simply cannot be decoded.

    Mirrors `org.apache.pdfbox.filter.JBIG2Filter` in name and contract;
    PDFBox likewise does not ship a JBIG2 encoder.
    """

    #: ``/JBIG2Globals`` parameter key per ISO 32000-1 §7.4.7. Exposed
    #: as a class attribute so callers reaching for the upstream
    #: ``COSName.JBIG2_GLOBALS`` reference site land on a stable name.
    JBIG2_GLOBALS: Final[str] = _JBIG2_GLOBALS

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        """Always raises — JBIG2 decoding is intentionally unsupported.

        See the class docstring: the sole available decoder is
        GPL-3.0/AGPL-licensed and excluded by the permissive-only policy.
        """
        raise OSError(_UNSUPPORTED_MESSAGE)

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        """``/JBIG2Decode`` is a decode-only filter — by upstream design.

        Mirrors ``JBIG2Filter`` in Apache PDFBox, which inherits the
        default ``encode`` that raises ``UnsupportedOperationException``.
        PDFBox does not ship a JBIG2 encoder (and no production PDF
        toolchain produces JBIG2 from scratch — the format is the
        province of dedicated tools such as ``jbig2enc`` invoked by
        upstream OCR / scan pipelines). This is upstream-faithful
        behaviour, not a pypdfbox deferral.
        """
        raise NotImplementedError(
            "JBIG2Decode.encode is not implemented (decode-only)"
        )


# PDF spec defines NO short-name abbreviation for /JBIG2Decode
# (ISO 32000-1 §7.4.2 Table 6) — register only the long name.
FilterFactory.register("JBIG2Decode", JBIG2Decode())
