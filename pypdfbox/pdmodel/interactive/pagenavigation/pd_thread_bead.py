from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from pypdfbox.cos import COSArray, COSDictionary, COSName

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_page import PDPage
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    from .pd_thread import PDThread

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_BEAD: COSName = COSName.get_pdf_name("Bead")
_T: COSName = COSName.get_pdf_name("T")
_N: COSName = COSName.get_pdf_name("N")
_V: COSName = COSName.get_pdf_name("V")
_P: COSName = COSName.get_pdf_name("P")
_R: COSName = COSName.get_pdf_name("R")


class PDThreadBead:
    """A single bead in a thread of a PDF document.

    Mirrors PDFBox ``org.apache.pdfbox.pdmodel.interactive.pagenavigation.PDThreadBead``.
    A bead is a ``COSDictionary`` with ``/Type /Bead`` whose entries link the
    bead into a doubly-linked list (``/N`` next, ``/V`` previous), reference
    the owning thread (``/T``, only required on the first bead), the page
    (``/P``) and a rectangle on the page (``/R``).
    """

    def __init__(self, b: COSDictionary | None = None) -> None:
        if b is None:
            self._bead = COSDictionary()
            self._bead.set_item(_TYPE, _BEAD)
            # On a freshly minted bead the next/previous pointers point at
            # the bead itself — matches upstream's circular-list invariant.
            self.set_next_bead(self)
            self.set_previous_bead(self)
        else:
            self._bead = b

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        """Return the underlying ``COSDictionary``."""
        return self._bead

    # ---------- equality / hashing (PDDictionaryWrapper parity) ----------

    def __eq__(self, other: object) -> bool:
        """Equality by underlying ``COSDictionary`` identity. Mirrors the
        upstream ``PDDictionaryWrapper#equals`` contract — two ``PDThreadBead``
        wrappers compare equal when (and only when) they wrap the same
        ``COSDictionary`` instance, so fresh wrappers returned by
        ``get_next_bead`` / ``get_previous_bead`` compare equal across calls.
        """
        if self is other:
            return True
        if isinstance(other, PDThreadBead):
            return self._bead is other._bead
        return NotImplemented

    def __hash__(self) -> int:
        """Hash by ``id`` of the wrapped dictionary, paired with
        :meth:`__eq__`. Mirrors upstream ``PDDictionaryWrapper#hashCode``."""
        return id(self._bead)

    # ---------- /T (thread) ----------

    def get_thread(self) -> PDThread | None:
        """Return the thread that owns this bead (only required on the first
        bead per the spec, so this can legitimately be ``None``)."""
        from .pd_thread import PDThread

        dic = self._bead.get_dictionary_object(_T)
        if isinstance(dic, COSDictionary):
            return PDThread(dic)
        return None

    def set_thread(self, thread: PDThread | None) -> None:
        """Set the owning thread (``/T``); ``None`` removes the entry."""
        if thread is None:
            self._bead.remove_item(_T)
            return
        self._bead.set_item(_T, thread.get_cos_object())

    # ---------- /N (next) ----------

    def get_next_bead(self) -> PDThreadBead | None:
        """Return the next bead — wraps to the first bead when this is the
        last bead in the article."""
        nxt = self._bead.get_dictionary_object(_N)
        if isinstance(nxt, COSDictionary):
            return PDThreadBead(nxt)
        return None

    def set_next_bead(self, nxt: PDThreadBead | None) -> None:
        """Set the next bead (``/N``); ``None`` removes the entry."""
        if nxt is None:
            self._bead.remove_item(_N)
            return
        self._bead.set_item(_N, nxt.get_cos_object())

    # ---------- /V (previous) ----------

    def get_previous_bead(self) -> PDThreadBead | None:
        """Return the previous bead — wraps to the last bead when this is
        the first bead in the article."""
        prev = self._bead.get_dictionary_object(_V)
        if isinstance(prev, COSDictionary):
            return PDThreadBead(prev)
        return None

    def set_previous_bead(self, previous: PDThreadBead | None) -> None:
        """Set the previous bead (``/V``); ``None`` removes the entry."""
        if previous is None:
            self._bead.remove_item(_V)
            return
        self._bead.set_item(_V, previous.get_cos_object())

    # ---------- linked-list manipulation ----------

    def append_bead(self, append: PDThreadBead) -> None:
        """Insert ``append`` immediately after this bead, fixing up the
        next/previous pointers on both sides. Mirrors upstream
        ``appendBead``."""
        next_bead = self.get_next_bead()
        if next_bead is not None:
            next_bead.set_previous_bead(append)
            append.set_next_bead(next_bead)
        self.set_next_bead(append)
        append.set_previous_bead(self)

    # ---------- /P (page) ----------

    def get_page(self) -> PDPage | None:
        """Return the page this bead lives on, or ``None`` when absent."""
        from pypdfbox.pdmodel.pd_page import PDPage

        dic = self._bead.get_dictionary_object(_P)
        if isinstance(dic, COSDictionary):
            return PDPage(dic)
        return None

    def set_page(self, page: PDPage | None) -> None:
        """Set the owning page (``/P``); ``None`` removes the entry."""
        if page is None:
            self._bead.remove_item(_P)
            return
        self._bead.set_item(_P, page.get_cos_object())

    # ---------- /R (rectangle) ----------

    def get_rectangle(self) -> PDRectangle | None:
        """Return the rectangle on the page that this bead covers, or
        ``None`` when ``/R`` is absent."""
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle

        arr = self._bead.get_dictionary_object(_R)
        if isinstance(arr, COSArray):
            return PDRectangle.from_cos_array(arr)
        return None

    def set_rectangle(self, rect: PDRectangle | None) -> None:
        """Set the rectangle (``/R``); ``None`` removes the entry."""
        if rect is None:
            self._bead.remove_item(_R)
            return
        self._bead.set_item(_R, rect.to_cos_array())

    # ---------- iteration over the bead chain ----------

    def iter_beads(self) -> Iterator[PDThreadBead]:
        """Walk the (circular) bead chain forward starting from this bead.

        Yields ``self`` first, then follows ``/N`` until the chain wraps back
        to the starting bead's underlying ``COSDictionary`` or ``/N`` is
        absent. The walk is identity-aware: malformed PDFs that point ``/N``
        at an already-visited bead are tolerated by tracking visited
        dictionary identities, so the iterator is guaranteed to terminate.
        """
        seen: set[int] = set()
        current: PDThreadBead | None = self
        start_id = id(self._bead)
        while current is not None:
            cur_id = id(current._bead)
            if cur_id in seen:
                return
            seen.add(cur_id)
            yield current
            nxt = current.get_next_bead()
            if nxt is None:
                return
            if id(nxt.get_cos_object()) == start_id:
                return
            current = nxt

    def __iter__(self) -> Iterator[PDThreadBead]:
        """Equivalent to :meth:`iter_beads` — lets callers do ``for b in
        bead:`` to walk the article."""
        return self.iter_beads()

    # ---------- predicate helpers ----------

    def is_first_bead(self) -> bool:
        """Return ``True`` when this bead carries a ``/T`` thread reference.

        Per the PDF spec the ``/T`` entry is only required on the first bead
        of an article. Most well-formed PDFs therefore have exactly one bead
        per thread that satisfies this predicate; subsequent beads in the
        chain return ``False``.
        """
        return self._bead.contains_key(_T)

    def is_singleton(self) -> bool:
        """Return ``True`` when this bead is its own ``/N`` and ``/V``.

        Freshly-constructed beads start in this state — ``PDThreadBead()`` sets
        next/previous to point back at the new bead — and only leave it once
        they are linked into an article via :meth:`append_bead`. Useful for
        detecting unlinked beads before they're inserted into a thread.
        """
        nxt = self._bead.get_dictionary_object(_N)
        prev = self._bead.get_dictionary_object(_V)
        return nxt is self._bead and prev is self._bead

    def count_beads(self) -> int:
        """Return the number of beads reachable forward from this bead.

        Walks the ``/N`` chain via :meth:`iter_beads`, so the count is bounded
        by the visited-set guard and terminates even on malformed PDFs whose
        next-pointers do not loop back to the starting bead.
        """
        return sum(1 for _ in self.iter_beads())


__all__ = ["PDThreadBead"]
