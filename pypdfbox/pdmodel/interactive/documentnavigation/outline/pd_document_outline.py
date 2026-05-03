from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_outline_node import PDOutlineNode

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_OUTLINES: COSName = COSName.get_pdf_name("Outlines")
_COUNT: COSName = COSName.COUNT  # type: ignore[attr-defined]


class PDDocumentOutline(PDOutlineNode):
    """
    Document-level outline root. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDDocumentOutline``.

    A blank outline carries ``/Type /Outlines``; existing dictionaries
    are wrapped in place.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        # Upstream ``PDDocumentOutline(COSDictionary)`` unconditionally
        # writes ``/Type /Outlines`` on the wrapped dictionary — even
        # when a stale or wrong ``/Type`` is already present. Mirror that
        # behavior so wrapping a half-built outline dict normalizes the
        # type marker.
        self._dictionary.set_item(_TYPE, _OUTLINES)

    # ---------- open / closed: root is always open per upstream ----------

    def is_node_open(self) -> bool:
        """The outline root is *always* considered open. Mirrors upstream
        ``PDDocumentOutline#isNodeOpen`` which is a hard-coded ``return
        true`` — the document outline is not an outline item, so the
        ``/Count`` sign convention from PDF 32000-1:2008 §12.3.3 doesn't
        apply to it. This makes the ``add_last`` / ``add_first`` open-count
        propagation paths feed positive contributions into the root, so
        upstream's invariant ``outline.get_open_count() >= 0`` holds."""
        return True

    def open_node(self) -> None:
        """No-op — the outline root cannot be opened or closed. Mirrors
        upstream ``PDDocumentOutline#openNode`` which carries the comment
        *"The root of the outline hierarchy is not an OutlineItem and
        cannot be opened or closed"*."""

    def close_node(self) -> None:
        """No-op — the outline root cannot be opened or closed. Mirrors
        upstream ``PDDocumentOutline#closeNode`` which carries the comment
        *"The root of the outline hierarchy is not an OutlineItem and
        cannot be opened or closed"*."""

    def is_open(self) -> bool:
        """pypdfbox-only Python helper that reports the outline root's
        open/closed state by inspecting ``/Count`` sign — ``True`` when
        ``/Count`` is absent or non-negative, ``False`` only when
        ``/Count`` is negative. Distinct from :meth:`is_node_open` which
        mirrors upstream's hard-coded ``True``. Retained for callers that
        want to introspect the legacy sign convention without running the
        full open-count propagation."""
        if self._dictionary.get_dictionary_object(_COUNT) is None:
            return True
        return self.get_open_count() >= 0


__all__ = ["PDDocumentOutline"]
