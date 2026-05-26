"""Several constants used in XMP.

Mirrors ``org.apache.xmpbox.XmpConstants`` (PDFBox 3.0,
``xmpbox/src/main/java/org/apache/xmpbox/XmpConstants.java``).

Upstream ``XmpConstants`` is a ``final`` class with a private constructor that
only holds ``public static final String`` constants. The same values were
already surfaced as module-level names on :mod:`pypdfbox.xmpbox.xmp_metadata`;
to keep a single source of truth this class re-exports those module constants
as class attributes rather than redefining them. The class form is provided so
upstream-style ``XmpConstants.RDF_NAMESPACE`` references port one-to-one.
"""

from __future__ import annotations

from pypdfbox.xmpbox import xmp_metadata as _md


class XmpConstants:
    """Holder for the XMP wire-format constants (upstream-named, final)."""

    # The RDF namespace URI reference.
    RDF_NAMESPACE = _md.RDF_NAMESPACE

    # The default xpacket header begin attribute.
    DEFAULT_XPACKET_BEGIN = _md.DEFAULT_XPACKET_BEGIN

    # The default xpacket header id attribute.
    DEFAULT_XPACKET_ID = _md.DEFAULT_XPACKET_ID

    # The default xpacket header encoding attribute.
    DEFAULT_XPACKET_ENCODING = _md.DEFAULT_XPACKET_ENCODING

    # The default xpacket data (XMP Data).
    DEFAULT_XPACKET_BYTES = _md.DEFAULT_XPACKET_BYTES

    # The default xpacket trailer end attribute.
    DEFAULT_XPACKET_END = _md.DEFAULT_XPACKET_END

    # The default namespace prefix for RDF.
    DEFAULT_RDF_PREFIX = _md.DEFAULT_RDF_PREFIX

    # The default local name for RDF.
    DEFAULT_RDF_LOCAL_NAME = _md.DEFAULT_RDF_LOCAL_NAME

    # The list element name.
    LIST_NAME = _md.LIST_NAME

    # The language attribute name.
    LANG_NAME = _md.LANG_NAME

    # The about attribute name.
    ABOUT_NAME = _md.ABOUT_NAME

    # The Description element name.
    DESCRIPTION_NAME = _md.DESCRIPTION_NAME

    # The resource attribute name.
    RESOURCE_NAME = _md.RESOURCE_NAME

    # The parse type attribute name.
    PARSE_TYPE = _md.PARSE_TYPE

    # The default language code.
    X_DEFAULT = _md.X_DEFAULT

    def __init__(self) -> None:
        # hide constructor — upstream's constructor is private.
        raise TypeError("XmpConstants is a non-instantiable constant holder")


__all__ = ["XmpConstants"]
