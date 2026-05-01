"""
Upstream-named module mirror for ``org.apache.pdfbox.filter.CCITTFaxFilter``.

The implementation lives in :mod:`pypdfbox.filter.ccitt_fax_decode` and
is registered under the PDF ``/Filter`` name ``CCITTFaxDecode`` (and its
abbreviation ``CCF``). This module exposes the same codec under the
upstream-faithful Java class name :class:`CCITTFaxFilter`, so a direct
port from PDFBox source can write::

    from pypdfbox.filter.ccitt_fax_filter import CCITTFaxFilter

and resolve the symbol without disturbing the existing registry wiring.
"""

from __future__ import annotations

from .ccitt_fax_decode import CCITTFaxDecode
from .filter_factory import FilterFactory

__all__ = ["CCITTFaxFilter"]


class CCITTFaxFilter(CCITTFaxDecode):
    """Alias for :class:`CCITTFaxDecode` under the upstream class name.

    Mirrors ``org.apache.pdfbox.filter.CCITTFaxFilter`` (PDFBox 3.0.x).
    Behavior, parameters and registry semantics are identical to
    :class:`CCITTFaxDecode`; this subclass exists purely so the upstream
    Java-style import path resolves.
    """


# Register the upstream-named subclass alongside the existing
# ``CCITTFaxDecode`` registration. The PDF ``/Filter`` name
# (``CCITTFaxDecode``) and its abbreviation (``CCF``) continue to
# resolve to the original ``CCITTFaxDecode`` instance owned by
# ``ccitt_fax_decode.py``.
FilterFactory.register("CCITTFaxFilter", CCITTFaxFilter())
