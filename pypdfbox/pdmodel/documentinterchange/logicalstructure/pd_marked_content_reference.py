from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName, COSStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_page import PDPage

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_PG: COSName = COSName.get_pdf_name("Pg")
_STM: COSName = COSName.get_pdf_name("Stm")
_STM_OWN: COSName = COSName.get_pdf_name("StmOwn")
_MCID: COSName = COSName.get_pdf_name("MCID")


class PDMarkedContentReference:
    """
    A marked-content reference (``/Type /MCR`` dictionary). Mirrors PDFBox
    ``PDMarkedContentReference``.

    Lite surface: typed ``PDPage`` for ``/Pg`` is deferred — ``get_pg`` /
    ``set_pg`` operate on raw ``COSDictionary``.
    """

    TYPE: str = "MCR"

    #: Sentinel returned by :meth:`get_mcid` when ``/MCID`` is absent.
    #: Mirrors the ``-1`` default upstream ``COSDictionary.getInt(COSName)``
    #: returns when the entry is missing. pypdfbox addition: lets callers
    #: predicate against the sentinel without re-deriving the constant.
    MCID_NOT_SET: int = -1

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dictionary: COSDictionary = COSDictionary()
            self._dictionary.set_name(_TYPE, self.TYPE)
        else:
            self._dictionary = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    # ---------- /Pg page (raw COSDictionary; typed PDPage deferred) ----

    def get_pg(self) -> COSDictionary | None:
        pg = self._dictionary.get_dictionary_object(_PG)
        return pg if isinstance(pg, COSDictionary) else None

    def set_pg(self, page: COSDictionary | None) -> None:
        if page is None:
            self._dictionary.remove_item(_PG)
            return
        cos = page.get_cos_object() if hasattr(page, "get_cos_object") else page
        self._dictionary.set_item(_PG, cos)

    # ---------- /Pg page (typed PDPage — mirrors upstream getPage) ----

    def get_page(self) -> "PDPage | None":
        """Resolve ``/Pg`` to a typed :class:`PDPage`.

        Mirrors upstream ``PDMarkedContentReference.getPage()`` (PDF 32000-1
        §14.7.4.4): ``/Pg`` is optional on a marked-content reference; when
        present it overrides the enclosing structure element's ``/Pg`` for
        this MCR only. Returns ``None`` when ``/Pg`` is absent or not a
        dictionary.
        """
        page_dict = self._dictionary.get_dictionary_object(_PG)
        if not isinstance(page_dict, COSDictionary):
            return None
        # Local import avoids the pdmodel→logicalstructure→pdmodel cycle.
        from pypdfbox.pdmodel.pd_page import PDPage

        return PDPage(page_dict)

    def set_page(self, page: "PDPage | COSDictionary | None") -> None:
        """Set ``/Pg`` to a typed :class:`PDPage` wrapper or remove it.

        Mirrors upstream ``PDMarkedContentReference.setPage(PDPage)``.
        ``None`` removes the entry; any wrapper exposing ``get_cos_object``
        is unwrapped to its underlying dictionary.
        """
        if page is None:
            self._dictionary.remove_item(_PG)
            return
        cos = page.get_cos_object() if hasattr(page, "get_cos_object") else page
        self._dictionary.set_item(_PG, cos)

    def has_pg(self) -> bool:
        """Return ``True`` when ``/Pg`` is present and is a dictionary.

        pypdfbox addition: ``/Pg`` on an MCR is optional (PDF 32000-1
        §14.7.4.4); this predicate distinguishes "no override" from
        "override is malformed" without materialising a :class:`PDPage`.
        Symmetric with :meth:`PDObjectReference.has_pg`.
        """
        return isinstance(self._dictionary.get_dictionary_object(_PG), COSDictionary)

    # ---------- /Stm content stream ----

    def get_stm(self) -> COSStream | None:
        stm = self._dictionary.get_dictionary_object(_STM)
        return stm if isinstance(stm, COSStream) else None

    def set_stm(self, stream: COSStream | None) -> None:
        if stream is None:
            self._dictionary.remove_item(_STM)
            return
        cos = stream.get_cos_object() if hasattr(stream, "get_cos_object") else stream
        self._dictionary.set_item(_STM, cos)

    def has_stm(self) -> bool:
        """Return ``True`` when ``/Stm`` is present and is a content stream.

        pypdfbox addition: ``/Stm`` is required only for marked content in
        a content stream other than the page's own (PDF 32000-1 §14.7.4.4
        Table 324). The predicate avoids the cost of resolving the stream
        when the caller only needs presence.
        """
        return isinstance(self._dictionary.get_dictionary_object(_STM), COSStream)

    # ---------- /StmOwn stream owner ----

    def get_stm_own(self) -> COSDictionary | None:
        owner = self._dictionary.get_dictionary_object(_STM_OWN)
        return owner if isinstance(owner, COSDictionary) else None

    def set_stm_own(self, d: COSDictionary | None) -> None:
        if d is None:
            self._dictionary.remove_item(_STM_OWN)
            return
        cos = d.get_cos_object() if hasattr(d, "get_cos_object") else d
        self._dictionary.set_item(_STM_OWN, cos)

    def has_stm_own(self) -> bool:
        """Return ``True`` when ``/StmOwn`` is present and is a dictionary.

        pypdfbox addition: ``/StmOwn`` is required only when ``/Stm``
        refers to a content stream not directly owned by the structure
        element (PDF 32000-1 §14.7.4.4 Table 324). Useful for callers
        validating that an MCR with ``/Stm`` also carries the matching
        ownership entry.
        """
        return isinstance(
            self._dictionary.get_dictionary_object(_STM_OWN), COSDictionary
        )

    # ---------- /MCID marked content identifier ----

    def get_mcid(self) -> int:
        return self._dictionary.get_int(_MCID)

    def set_mcid(self, mcid: int) -> None:
        if mcid < 0:
            raise ValueError("MCID is negative")
        self._dictionary.set_int(_MCID, mcid)

    def has_mcid(self) -> bool:
        """Return ``True`` when ``/MCID`` is present in the dictionary.

        pypdfbox addition: :meth:`get_mcid` returns ``-1`` (the
        :data:`MCID_NOT_SET` sentinel) when ``/MCID`` is absent, which is
        indistinguishable from an MCID of ``0`` only by inspecting the
        dictionary directly. ``has_mcid`` lets callers gate on presence
        without re-reading the COS dictionary themselves.
        """
        return _MCID in self._dictionary

    def __repr__(self) -> str:
        return f"mcid={self.get_mcid()}"

    def __str__(self) -> str:
        """Render as ``mcid=<mcid>``. Mirrors upstream
        ``PDMarkedContentReference.toString()`` (PDF 32000-1 §14.7.4.4).

        Java callers reach for ``toString()``; the equivalent Python entry
        point is ``str()``. ``__repr__`` already returns the same format —
        we mirror it on ``__str__`` so ``str(mcr)`` and ``repr(mcr)`` agree
        and both line up with the upstream rendering.
        """
        return f"mcid={self.get_mcid()}"


__all__ = ["PDMarkedContentReference"]
