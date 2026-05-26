"""Adobe XMP "Paged-Text" (``xmpTPg``) schema.

Mirrors ``org.apache.xmpbox.schema.XMPPageTextSchema`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/schema/XMPPageTextSchema.java``).

Upstream ``XMPPageTextSchema`` is a thin :class:`XMPSchema` subclass carrying
only the property local-name constants for the paged-text namespace plus the
two upstream constructors (``XMPMetadata`` and ``XMPMetadata`` + ``prefix``).
The local-name constants match upstream's ``public static final String``
fields verbatim; the structured-type annotations
(``@StructuredType(preferedPrefix = "xmpTPg", namespace = ".../t/pg/")``) are
surfaced as the :attr:`PREFERRED_PREFIX` / :attr:`NAMESPACE` class attributes
that the base class understands.

This is distinct from :class:`pypdfbox.xmpbox.xmp_paged_text_schema.XMPageTextSchema`
(note the missing "d"), which carries the richer typed accessors. Both share
the same namespace; this class is the verbatim upstream-named mirror.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.xmpbox.xmp_schema import XMPSchema

if TYPE_CHECKING:
    from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


class XMPPageTextSchema(XMPSchema):
    """Representation of the Adobe XMP "Paged-Text" schema."""

    NAMESPACE = "http://ns.adobe.com/xap/1.0/t/pg/"
    PREFERRED_PREFIX = "xmpTPg"

    # Local-name constants — names match upstream ``public static final`` fields.

    # The size of the largest page in the document (Dimensions).
    MAX_PAGE_SIZE = "MaxPageSize"

    # The number of pages in the document (Integer).
    N_PAGES = "NPages"

    # An ordered array of plate names that are needed to print the document.
    PLATENAMES = "PlateNames"

    # An ordered array of colorants (swatches) that are used in the document.
    COLORANTS = "Colorants"

    # An unordered array of fonts that are used in the document.
    FONTS = "Fonts"

    def __init__(self, metadata: XMPMetadata, prefix: str | None = None) -> None:
        """Mirror upstream's two constructors via an optional ``prefix``.

        ``XMPPageTextSchema(metadata)`` uses the preferred ``xmpTPg`` prefix;
        ``XMPPageTextSchema(metadata, prefix)`` overrides it.
        """
        if prefix is None:
            super().__init__(metadata, self.NAMESPACE, self.PREFERRED_PREFIX)
        else:
            super().__init__(metadata, self.NAMESPACE, prefix)


__all__ = ["XMPPageTextSchema"]
