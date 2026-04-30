"""
Upstream-named module mirror for ``org.apache.pdfbox.filter.FlateFilter``.

The implementation lives in :mod:`pypdfbox.filter.flate_decode` and is
registered under the PDF ``/Filter`` name ``FlateDecode`` (and its
abbreviation ``Fl``). This module exposes the same codec under the
upstream-faithful Java class name :class:`FlateFilter`, so a direct port
from PDFBox source can write::

    from pypdfbox.filter.flate_filter import FlateFilter

and resolve the symbol without disturbing the existing registry wiring.
"""

from __future__ import annotations

from .filter_factory import FilterFactory
from .flate_decode import FlateDecode

__all__ = ["FlateFilter"]


class FlateFilter(FlateDecode):
    """Alias for :class:`FlateDecode` under the upstream class name.

    Mirrors ``org.apache.pdfbox.filter.FlateFilter`` (PDFBox 3.0.x).
    Behavior, parameters and registry semantics are identical to
    :class:`FlateDecode`; this subclass exists purely so the upstream
    Java-style import path resolves.
    """


# Register the upstream-named subclass alongside the existing
# ``FlateDecode`` registration. The PDF ``/Filter`` name
# (``FlateDecode``) and its abbreviation (``Fl``) continue to resolve
# to the original ``FlateDecode`` instance owned by ``flate_decode.py``.
FilterFactory.register("FlateFilter", FlateFilter())
