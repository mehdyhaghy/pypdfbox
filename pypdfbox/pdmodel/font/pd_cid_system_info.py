from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_REGISTRY: COSName = COSName.get_pdf_name("Registry")
_ORDERING: COSName = COSName.get_pdf_name("Ordering")
_SUPPLEMENT: COSName = COSName.get_pdf_name("Supplement")


class PDCIDSystemInfo:
    """Wraps a ``/CIDSystemInfo`` dictionary. Mirrors PDFBox ``PDCIDSystemInfo``.

    A ``CIDSystemInfo`` identifies the character collection of a CIDFont:
    ``/Registry`` (e.g. ``Adobe``), ``/Ordering`` (e.g. ``Japan1``), and
    integer ``/Supplement``.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Registry ----------

    def get_registry(self) -> str | None:
        return self._dict.get_string(_REGISTRY)

    def set_registry(self, registry: str | None) -> None:
        if registry is None:
            self._dict.remove_item(_REGISTRY)
            return
        self._dict.set_string(_REGISTRY, registry)

    # ---------- /Ordering ----------

    def get_ordering(self) -> str | None:
        return self._dict.get_string(_ORDERING)

    def set_ordering(self, ordering: str | None) -> None:
        if ordering is None:
            self._dict.remove_item(_ORDERING)
            return
        self._dict.set_string(_ORDERING, ordering)

    # ---------- /Supplement ----------

    def get_supplement(self) -> int:
        return self._dict.get_int(_SUPPLEMENT, 0)

    def set_supplement(self, supplement: int) -> None:
        self._dict.set_int(_SUPPLEMENT, int(supplement))

    def __str__(self) -> str:
        return f"{self.get_registry()}-{self.get_ordering()}-{self.get_supplement()}"


__all__ = ["PDCIDSystemInfo"]
