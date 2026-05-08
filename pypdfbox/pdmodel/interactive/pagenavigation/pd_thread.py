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

    # ---------- equality / hashing (PDDictionaryWrapper parity) ----------

    def __eq__(self, other: object) -> bool:
        """Equality by underlying ``COSDictionary`` identity. Mirrors the
        upstream ``PDDictionaryWrapper#equals`` contract — two ``PDThread``
        wrappers compare equal when (and only when) they wrap the same
        ``COSDictionary`` instance, so fresh wrappers returned by
        ``PDThreadBead.get_thread`` compare equal across calls.
        """
        if self is other:
            return True
        if isinstance(other, PDThread):
            return self._thread is other._thread
        return NotImplemented

    def __hash__(self) -> int:
        """Hash by ``id`` of the wrapped dictionary, paired with
        :meth:`__eq__`. Mirrors upstream ``PDDictionaryWrapper#hashCode``."""
        return id(self._thread)

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
            self.clear_thread_info()
            return
        self._thread.set_item(_I, info.get_cos_object())

    def has_thread_info(self) -> bool:
        """Return ``True`` when ``/I`` contains a parsable information dictionary."""
        return isinstance(self._thread.get_dictionary_object(_I), COSDictionary)

    def clear_thread_info(self) -> None:
        """Remove the thread information dictionary (``/I``), if present."""
        self._thread.remove_item(_I)

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
            self.clear_first_bead()
            return
        bead.set_thread(self)
        self._thread.set_item(_F, bead.get_cos_object())

    def has_first_bead(self) -> bool:
        """Return ``True`` when ``/F`` contains a parsable bead dictionary."""
        return isinstance(self._thread.get_dictionary_object(_F), COSDictionary)

    def clear_first_bead(self) -> None:
        """Remove the first bead reference (``/F``), if present."""
        self._thread.remove_item(_F)

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

    def has_info(self) -> bool:
        """Alias of :meth:`has_thread_info` matching the ``get_info`` name."""
        return self.has_thread_info()

    def clear_info(self) -> None:
        """Alias of :meth:`clear_thread_info` matching the ``get_info`` name."""
        self.clear_thread_info()


__all__ = ["PDThread"]
