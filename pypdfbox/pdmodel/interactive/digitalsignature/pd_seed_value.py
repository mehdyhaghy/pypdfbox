from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SV: COSName = COSName.get_pdf_name("SV")
_FILTER: COSName = COSName.get_pdf_name("Filter")
_SUB_FILTER: COSName = COSName.get_pdf_name("SubFilter")
_V: COSName = COSName.get_pdf_name("V")
_REASONS: COSName = COSName.get_pdf_name("Reasons")
_MDP: COSName = COSName.get_pdf_name("MDP")
_TIME_STAMP: COSName = COSName.get_pdf_name("TimeStamp")


class PDSeedValue:
    """Seed value dictionary (``/Type /SV``). Mirrors PDFBox ``PDSeedValue``
    lite surface (PDF 32000-1 §12.7.4.5, Table 234).

    Deferred upstream behavior: typed wrappers for ``/MDP``, ``/TimeStamp``,
    ``/CertificateSeedValue``, ``/LegalAttestation`` and the ``/Ff`` flags
    helpers are not implemented — accessors return raw COS or basic values.
    """

    TYPE = "SV"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
            self._dict.set_item(_TYPE, _SV)
        else:
            self._dict = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Filter ----------

    def get_filter(self) -> str | None:
        return self._dict.get_name(_FILTER)

    def set_filter(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_FILTER)
            return
        self._dict.set_name(_FILTER, name)

    # ---------- /SubFilter (array of names) ----------

    def get_sub_filter(self) -> list[str] | None:
        v = self._dict.get_dictionary_object(_SUB_FILTER)
        if not isinstance(v, COSArray):
            return None
        names = v.to_cos_name_string_list()
        if any(n is None for n in names):
            return None
        return [str(n) for n in names]  # type: ignore[arg-type]

    def set_sub_filter(self, names: list[str] | None) -> None:
        if names is None:
            self._dict.remove_item(_SUB_FILTER)
            return
        self._dict.set_item(_SUB_FILTER, COSArray.of_cos_names(names))

    # ---------- /V version ----------

    def get_v(self) -> int | None:
        v = self._dict.get_dictionary_object(_V)
        if isinstance(v, COSInteger):
            return v.value
        return None

    def set_v(self, v: int | None) -> None:
        if v is None:
            self._dict.remove_item(_V)
            return
        self._dict.set_int(_V, v)

    # ---------- /Reasons (array of text strings) ----------

    def get_reasons(self) -> list[str] | None:
        v = self._dict.get_dictionary_object(_REASONS)
        if not isinstance(v, COSArray):
            return None
        out = v.to_cos_string_string_list()
        if any(s is None for s in out):
            return None
        return [str(s) for s in out]  # type: ignore[arg-type]

    def set_reasons(self, reasons: list[str] | None) -> None:
        if reasons is None:
            self._dict.remove_item(_REASONS)
            return
        self._dict.set_item(_REASONS, COSArray.of_cos_strings(reasons))

    # ---------- /MDP raw ----------

    def get_mdp(self) -> COSDictionary | None:
        v = self._dict.get_dictionary_object(_MDP)
        if isinstance(v, COSDictionary):
            return v
        return None

    def set_mdp(self, mdp: COSDictionary | None) -> None:
        if mdp is None:
            self._dict.remove_item(_MDP)
            return
        self._dict.set_item(_MDP, mdp)

    # ---------- /TimeStamp raw ----------

    def get_time_stamp(self) -> COSDictionary | None:
        v = self._dict.get_dictionary_object(_TIME_STAMP)
        if isinstance(v, COSDictionary):
            return v
        return None

    def set_time_stamp(self, time_stamp: COSDictionary | None) -> None:
        if time_stamp is None:
            self._dict.remove_item(_TIME_STAMP)
            return
        self._dict.set_item(_TIME_STAMP, time_stamp)


__all__ = ["PDSeedValue"]
