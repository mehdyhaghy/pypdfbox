"""Wave 1354 tail-sweep: cover ``validate_naming`` attrs-None guard.

xml.dom.minidom Elements always have a non-None ``attributes`` attribute,
but PDFBox upstream supports DOM impls where ``getAttributes`` is null
on text-only elements. The Python port keeps the defensive guard for
parity. A plain object whose ``attributes`` returns ``None`` exercises
the branch (line 64 in ``pdfa_extension_helper.py``).
"""

from __future__ import annotations

from pypdfbox.xmpbox.xml.pdfa_extension_helper import PdfaExtensionHelper


class _ElementWithoutAttributes:
    """Stand-in DOM Element whose ``attributes`` is ``None``."""

    attributes = None


def test_validate_naming_returns_silently_when_attributes_is_none() -> None:
    # No raise, no return value — just the early return at line 64.
    assert (
        PdfaExtensionHelper.validate_naming(None, _ElementWithoutAttributes())
        is None
    )
