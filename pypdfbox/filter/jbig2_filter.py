"""JBIG2 filter — upstream-named alias of :class:`JBIG2Decode`.

Mirrors ``org.apache.pdfbox.filter.JBIG2Filter``. The Java upstream
class **is** the registered JBIG2 filter implementation; in the Python
port the contract lives in :class:`JBIG2Decode`. This module provides a
thin subclass under the upstream class name so a direct port from
PDFBox Java sources can write::

    from pypdfbox.filter.jbig2_filter import JBIG2Filter

and resolve the symbol without re-deriving it.

License posture — why JBIG2 decoding is unsupported
---------------------------------------------------

JBIG2 (ITU-T T.88) decoding is **intentionally unsupported** in
pypdfbox. The only available JBIG2 decoder is ``jbig2-parser``, whose
compiled extension statically links the Rust ``jbig2dec`` crate — a
binding to Artifex's AGPL ``jbig2dec`` C library. GPL-3.0/AGPL are on
the project's hard-forbidden license list (CLAUDE.md "Licensing &
attribution"), so no JBIG2 decoder is bundled. ``imagecodecs`` is also
ruled out for the same reason: the only JBIG2 codec it can be built
against is the AGPL ``jbig2dec`` (the runtime wheel exposes no JBIG2
names and ships no ``LICENSE-jbig2dec`` entry, but the route stays off
by design so a future rebuild adding ``jbig2dec`` cannot pull AGPL code
into the decode path).

Consequently :meth:`JBIG2Decode.decode` (inherited here) raises
``OSError``; the filter remains registered only so ``/JBIG2Decode`` is
recognised as a known filter name.
"""

from __future__ import annotations

import logging
from typing import BinaryIO

from pypdfbox.cos import COSDictionary

from .decode_result import DecodeResult
from .filter_factory import FilterFactory
from .jbig2_decode import JBIG2Decode

_LOG = logging.getLogger(__name__)


class JBIG2Filter(JBIG2Decode):
    """Alias for :class:`JBIG2Decode` under the upstream class name.

    Functionally identical to :class:`JBIG2Decode`; this subclass exists
    purely so the upstream class name resolves and so callers writing
    against the Java API surface see the familiar name.
    """

    # One-shot guard so the Levigo-donated notice only logs once per
    # process lifetime, matching the upstream ``levigoLogged`` static flag.
    _levigo_logged: bool = False

    @classmethod
    def log_levigo_donated(cls) -> None:
        """Log the one-time Levigo plugin donation notice.

        Mirrors upstream's private ``logLevigoDonated()``. In Java this
        fires when the discovered JBIG2 ImageIO plugin class name
        contains ``levigo``; in pypdfbox JBIG2 decoding is unsupported
        (no permissively-licensed decoder exists) so the Levigo plugin
        isn't involved — but the method exists for parity with the Java
        API surface.
        """
        if cls._levigo_logged:
            return
        _LOG.info(
            "The Levigo JBIG2 plugin has been donated to the Apache Foundation"
        )
        _LOG.info(
            "and an improved version is available for download at "
            "https://pdfbox.apache.org/download.cgi"
        )
        cls._levigo_logged = True

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        return super().decode(encoded, decoded, parameters, index)

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        # Upstream throws UnsupportedOperationException — mirror via the
        # parent class which already raises in encode().
        super().encode(raw, encoded, parameters)


# Register the upstream-named subclass under the upstream long name so
# callers using `FilterFactory.get("JBIG2Filter")` get the same wrapper.
# Do *not* overwrite the existing `JBIG2Decode` registration (other tests
# rely on the registered instance being precisely `JBIG2Decode`).
try:
    if not FilterFactory.is_registered("JBIG2Filter"):
        FilterFactory.register("JBIG2Filter", JBIG2Filter())
except Exception:  # pragma: no cover - defensive registration guard
    pass
