"""
Upstream-named module mirror for
``org.apache.pdfbox.filter.RunLengthDecodeFilter``.

The implementation lives in :mod:`pypdfbox.filter.run_length_decode` and
is registered under the PDF ``/Filter`` name ``RunLengthDecode`` (and
its abbreviation ``RL``). This module exposes the same codec under the
upstream-faithful Java class name :class:`RunLengthDecodeFilter`, so a
direct port from PDFBox source can write::

    from pypdfbox.filter.run_length_filter import RunLengthDecodeFilter

and resolve the symbol without disturbing the existing registry wiring.
"""

from __future__ import annotations

from .filter_factory import FilterFactory
from .run_length_decode import RunLengthDecode

__all__ = ["RunLengthDecodeFilter"]


class RunLengthDecodeFilter(RunLengthDecode):
    """Alias for :class:`RunLengthDecode` under the upstream-faithful name.

    Mirrors ``org.apache.pdfbox.filter.RunLengthDecodeFilter`` (PDFBox
    3.0.x). Behavior, parameters and registry semantics are identical
    to :class:`RunLengthDecode`; this subclass exists purely so the
    upstream Java-style import path resolves.
    """


# Register the upstream-named subclass alongside the existing
# ``RunLengthDecode`` registration. The PDF ``/Filter`` name
# (``RunLengthDecode``) and its abbreviation (``RL``) continue to
# resolve to the original ``RunLengthDecode`` instance owned by
# ``run_length_decode.py``.
FilterFactory.register("RunLengthDecodeFilter", RunLengthDecodeFilter())
