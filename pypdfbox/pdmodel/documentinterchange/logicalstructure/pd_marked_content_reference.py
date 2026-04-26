from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream

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

    # ---------- /MCID marked content identifier ----

    def get_mcid(self) -> int:
        return self._dictionary.get_int(_MCID)

    def set_mcid(self, mcid: int) -> None:
        if mcid < 0:
            raise ValueError("MCID is negative")
        self._dictionary.set_int(_MCID, mcid)

    def __repr__(self) -> str:
        return f"mcid={self.get_mcid()}"


__all__ = ["PDMarkedContentReference"]
