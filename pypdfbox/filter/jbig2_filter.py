"""JBIG2 filter — upstream-named alias of :class:`JBIG2Decode`.

Mirrors ``org.apache.pdfbox.filter.JBIG2Filter``. The Java upstream
class **is** the registered JBIG2 filter implementation; in the Python
port the heavy lifting already lives in :class:`JBIG2Decode` (which
wraps the existing ``jbig2-parser`` runtime dependency — library-first
per project guidelines). This module provides a thin subclass under the
upstream class name so a direct port from PDFBox Java sources can write::

    from pypdfbox.filter.jbig2_filter import JBIG2Filter

and resolve the symbol without re-deriving it.

License posture — why not ``imagecodecs`` for JBIG2
---------------------------------------------------

The sibling DCT (JPEG) and JPX (JPEG 2000) filters route their primary
decode through ``imagecodecs`` because its bundled libraries
(libjpeg-turbo and OpenJPEG) are permissively licensed (BSD-style).
JBIG2 is intentionally different: the only JBIG2 decoder ``imagecodecs``
can be built against is ``jbig2dec`` from Artifex, which is **AGPL-3.0**
— incompatible with this project's permissive-only license posture
(see CLAUDE.md "Licensing & attribution" — forbidden list includes
AGPL). We confirmed the ``imagecodecs`` wheel shipped at runtime has no
``jbig2`` decoder exposed at the module level (``dir(imagecodecs)``
returns no JBIG2 names) and no ``LICENSE-jbig2dec`` entry under
``imagecodecs/licenses/``, so the AGPL codec is not present — but we
still keep this route off by design so a future ``imagecodecs`` rebuild
that adds ``jbig2dec`` cannot accidentally pull AGPL code into the
pypdfbox decode path.

The ``jbig2-parser`` library we already depend on is pure Python (slow
for complex multi-region JBIG2 docs but adequate for the JBIG2 streams
PDFs ship in practice) and is permissively licensed, so it remains the
sole JBIG2 path here.
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
        contains ``levigo``; in pypdfbox we route JBIG2 decoding through
        the ``jbig2-parser`` library so the Levigo plugin isn't involved
        — but the method exists for parity with the Java API surface.
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
except Exception:
    pass
