from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation

    from .pd_thread_bead import PDThreadBead

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_THREAD: COSName = COSName.get_pdf_name("Thread")
_I: COSName = COSName.get_pdf_name("I")
_F: COSName = COSName.get_pdf_name("F")


class PDThread:
    """A single article thread in a PDF document.

    Mirrors PDFBox ``org.apache.pdfbox.pdmodel.interactive.pagenavigation.PDThread``.
    A thread is a ``COSDictionary`` with ``/Type /Thread`` whose ``/F`` entry
    references the first :class:`PDThreadBead` in the article. The optional
    ``/I`` entry holds an information dictionary (a
    :class:`pypdfbox.pdmodel.PDDocumentInformation` shape).
    """

    def __init__(self, t: COSDictionary | None = None) -> None:
        if t is None:
            self._thread = COSDictionary()
            self._thread.set_item(_TYPE, _THREAD)
        else:
            self._thread = t

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        """Return the underlying ``COSDictionary``."""
        return self._thread

    # ---------- /I (info) ----------

    def get_thread_info(self) -> PDDocumentInformation | None:
        """Return the thread information dictionary, or ``None`` when absent."""
        from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation

        info = self._thread.get_dictionary_object(_I)
        if isinstance(info, COSDictionary):
            return PDDocumentInformation(info)
        return None

    def set_thread_info(self, info: PDDocumentInformation | None) -> None:
        """Set the thread information dictionary (``/I``); ``None`` removes it."""
        if info is None:
            self._thread.remove_item(_I)
            return
        self._thread.set_item(_I, info.get_cos_object())

    # ---------- /F (first bead) ----------

    def get_first_bead(self) -> PDThreadBead | None:
        """Return the first bead in the thread, or ``None`` when ``/F`` is
        absent. Required by the spec but defensive for damaged inputs."""
        from .pd_thread_bead import PDThreadBead

        bead = self._thread.get_dictionary_object(_F)
        if isinstance(bead, COSDictionary):
            return PDThreadBead(bead)
        return None

    def set_first_bead(self, bead: PDThreadBead | None) -> None:
        """Set the first bead. When non-``None`` the bead's thread reference
        is updated to point back at this object — mirrors the upstream
        ``setFirstBead`` side effect."""
        if bead is None:
            self._thread.remove_item(_F)
            return
        bead.set_thread(self)
        self._thread.set_item(_F, bead.get_cos_object())

    # ---------- upstream-name aliases ----------
    #
    # Upstream PDFBox exposes ``getInfo()`` / ``setInfo()`` on PDThread (not
    # ``getThreadInfo`` — that's our own clarifying name). Provide the
    # snake_case equivalents of the upstream names so PDFBox developers can
    # reach for what they expect.

    def get_info(self) -> PDDocumentInformation | None:
        """Alias of :meth:`get_thread_info` matching upstream ``getInfo``."""
        return self.get_thread_info()

    def set_info(self, info: PDDocumentInformation | None) -> None:
        """Alias of :meth:`set_thread_info` matching upstream ``setInfo``."""
        self.set_thread_info(info)


__all__ = ["PDThread"]
