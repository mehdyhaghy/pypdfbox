from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SIG_FIELD_LOCK: COSName = COSName.get_pdf_name("SigFieldLock")
_ACTION: COSName = COSName.get_pdf_name("Action")
_FIELDS: COSName = COSName.get_pdf_name("Fields")
_P: COSName = COSName.get_pdf_name("P")


class PDSignatureLock:
    """Signature field lock dictionary (``/Type /SigFieldLock``). Mirrors the
    PDF 32000-1 §12.7.4.5 Table 233 SigFieldLock entry. Upstream PDFBox 3.0
    does not ship a typed wrapper for this dictionary — this lite port
    follows the same accessor conventions as ``PDSignature`` / ``PDSeedValue``.

    Deferred upstream behavior: validation that ``/Action == /All`` forbids
    a ``/Fields`` entry, and that ``/Action /Include`` / ``/Exclude``
    require one.
    """

    TYPE = "SigFieldLock"

    # ---------- /Action values (PDF 32000-1 §12.7.4.5 Table 233) ----------
    # All form fields do not permit changes after signing.
    ACTION_ALL = "All"
    # Form fields specified in /Fields do not permit changes after signing.
    ACTION_INCLUDE = "Include"
    # Form fields not specified in /Fields do not permit changes after signing.
    ACTION_EXCLUDE = "Exclude"

    # ---------- /P permission values (PDF 32000-1 §12.7.4.5 Table 233) ----------
    # No changes to the document are permitted; any change invalidates the
    # signature.
    P_NO_CHANGES = 1
    # Permitted changes are filling in forms, instantiating page templates,
    # and signing.
    P_ALLOW_FORM_FILL = 2
    # Permitted changes are the same as for /P 2, plus annotation creation,
    # deletion, and modification.
    P_ALLOW_FORM_FILL_AND_ANNOTATIONS = 3

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
            self._dict.set_item(_TYPE, _SIG_FIELD_LOCK)
        else:
            self._dict = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Action ----------

    def get_action(self) -> str | None:
        return self._dict.get_name(_ACTION)

    def set_action(self, action: str | None) -> None:
        if action is None:
            self._dict.remove_item(_ACTION)
            return
        self._dict.set_name(_ACTION, action)

    # ---------- /Fields ----------

    def get_fields(self) -> list[str] | None:
        v = self._dict.get_dictionary_object(_FIELDS)
        if not isinstance(v, COSArray):
            return None
        out = v.to_cos_string_string_list()
        if any(s is None for s in out):
            return None
        return [str(s) for s in out]  # type: ignore[arg-type]

    def set_fields(self, names: list[str] | None) -> None:
        if names is None:
            self._dict.remove_item(_FIELDS)
            return
        self._dict.set_item(_FIELDS, COSArray.of_cos_strings(names))

    # ---------- /P permission level ----------

    def get_p(self) -> int | None:
        v = self._dict.get_dictionary_object(_P)
        if isinstance(v, COSInteger):
            return v.value
        return None

    def set_p(self, p: int | None) -> None:
        if p is None:
            self._dict.remove_item(_P)
            return
        self._dict.set_int(_P, p)


__all__ = ["PDSignatureLock"]
