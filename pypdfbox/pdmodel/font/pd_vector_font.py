"""Vector outline font protocol.

Mirrors ``org.apache.pdfbox.pdmodel.font.PDVectorFont`` from upstream
Apache PDFBox 3.0. A vector font is any non-Type-3 font whose glyphs are
expressible as scalable outline paths — concretely
:class:`PDType1Font`, :class:`PDType1CFont`, :class:`PDTrueTypeFont`,
:class:`PDType0Font` (delegating to its descendant
:class:`PDCIDFontType0` / :class:`PDCIDFontType2`), and
:class:`PDMMType1Font`.

Upstream Java declares this as an ``interface``; we use
``typing.Protocol`` (runtime-checkable) so the existing pypdfbox font
classes already satisfy ``isinstance(font, PDVectorFont)`` without
having to touch their MRO.

Upstream method names (camelCase) are mapped to snake_case per the
project porting rules:

- ``getPath``           → :meth:`get_path`
- ``getNormalizedPath`` → :meth:`get_normalized_path`
- ``hasGlyph``          → :meth:`has_glyph`
- ``getHintedNormalizedPath`` → :func:`get_hinted_normalized_path`
  (a Java ``default`` method; see below)

Java ``IOException`` raised by upstream accessors maps to :class:`OSError`
per the project's Java→Python exception mapping.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PDVectorFont(Protocol):
    """Protocol for any vector-outline (i.e. non-Type-3) PDF font.

    Java upstream:
        ``public interface PDVectorFont`` in
        ``org.apache.pdfbox.pdmodel.font`` (Apache PDFBox 3.0,
        ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDVectorFont.java``).

    All accessors take a *PDF character code*, not a Unicode codepoint.
    Convert via the font's encoding / ToUnicode CMap before/after these
    calls. Upstream raises ``IOException`` on failure; pypdfbox raises
    :class:`OSError`.
    """

    def get_path(self, code: int) -> Any:
        """Return the glyph outline for PDF character code ``code``.

        Mirrors upstream ``GeneralPath getPath(int code) throws IOException``.
        Upstream returns :class:`java.awt.geom.GeneralPath`; pypdfbox is
        AWT-free, so concrete implementations may return a list of
        path-segment tuples or any other shape suitable for the renderer.
        Typed as ``Any`` so all of those satisfy the protocol.

        :raises OSError: when the font program cannot be read.
        """
        ...

    def get_normalized_path(self, code: int) -> Any:
        """Return the glyph outline for ``code`` normalized to the
        PostScript 1000-unit square. Fallback (``.notdef``) glyphs are
        substituted for missing codes.

        Mirrors upstream ``GeneralPath getNormalizedPath(int code) throws IOException``.

        :raises OSError: when the font program cannot be read.
        """
        ...

    def has_glyph(self, code: int) -> bool:
        """Return ``True`` when the font has a real glyph for PDF
        character code ``code`` (i.e. not a fallback to ``.notdef``).

        Mirrors upstream ``boolean hasGlyph(int code) throws IOException``.

        :raises OSError: when the font program cannot be read.
        """
        ...



def get_hinted_normalized_path(self: Any, code: int, ppem: int) -> Any:
    """Return the grid-fitted (TrueType-hinted) normalized glyph path for
    ``code`` at ``ppem``, or ``None`` if hinting does not apply (not an
    embedded TrueType outline font, a ppem the font's gasp table excludes,
    or hinting disabled). Like :meth:`PDVectorFont.get_normalized_path`
    the result is normalized to the 1000 unit square.

    Mirrors upstream's ``default GeneralPath getHintedNormalizedPath(int,
    int)`` (PDFBOX-3293), which returns ``null``. It is attached to the
    protocol after class creation so it is not a structural member: as with
    a Java default method, a font need not implement it to satisfy
    ``isinstance(font, PDVectorFont)``. Concrete fonts that do not hint
    (``PDType1Font``, ``PDCIDFont``) define the same ``None`` default.

    :raises OSError: when the font program cannot be read.
    """
    return None


PDVectorFont.get_hinted_normalized_path = get_hinted_normalized_path  # type: ignore[attr-defined]

__all__ = ["PDVectorFont"]
