from __future__ import annotations

from pypdfbox.cos import COSDictionary


class FDFPageInfo:
    """Page-info dictionary inside an :class:`FDFPage`.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFPageInfo`` (Java
    lines 28-60). Upstream is an intentionally thin wrapper — the spec
    leaves the dictionary contents application-defined — so this class
    exposes only the ``COSDictionary`` surface.
    """

    def __init__(self, page_info: COSDictionary | None = None) -> None:
        self._page_info: COSDictionary = (
            page_info if page_info is not None else COSDictionary()
        )

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        """Return the wrapped ``COSDictionary``. Mirrors upstream
        ``getCOSObject()`` (Java line 56)."""
        return self._page_info


__all__ = ["FDFPageInfo"]
