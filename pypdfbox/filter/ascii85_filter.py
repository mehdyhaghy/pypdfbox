"""
Upstream-named module mirror for ``org.apache.pdfbox.filter.ASCII85Filter``.

The implementation lives in :mod:`pypdfbox.filter.ascii85_decode` and is
registered under the PDF ``/Filter`` name ``ASCII85Decode`` (and its
abbreviation ``A85``). This module exposes the same codec under the
upstream-faithful Java class name :class:`ASCII85Filter`, so a direct
port from PDFBox source can write::

    from pypdfbox.filter.ascii85_filter import ASCII85Filter

and resolve the symbol without disturbing the existing registry wiring.
"""

from __future__ import annotations

from .ascii85_decode import ASCII85Decode
from .filter_factory import FilterFactory

__all__ = ["ASCII85Filter"]


class ASCII85Filter(ASCII85Decode):
    """Alias for :class:`ASCII85Decode` under the upstream class name.

    Mirrors ``org.apache.pdfbox.filter.ASCII85Filter`` (PDFBox 3.0.x).
    Behavior, parameters and registry semantics are identical to
    :class:`ASCII85Decode`; this subclass exists purely so the upstream
    Java-style import path resolves.
    """


# Register the upstream-named subclass alongside the existing
# ``ASCII85Decode`` registration. The PDF ``/Filter`` name
# (``ASCII85Decode``) and its abbreviation (``A85``) continue to
# resolve to the original ``ASCII85Decode`` instance owned by
# ``ascii85_decode.py``.
FilterFactory.register("ASCII85Filter", ASCII85Filter())
