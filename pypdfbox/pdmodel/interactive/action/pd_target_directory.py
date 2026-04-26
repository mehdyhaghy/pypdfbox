from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName

_R: COSName = COSName.get_pdf_name("R")
_N: COSName = COSName.get_pdf_name("N")
_P: COSName = COSName.get_pdf_name("P")
_A: COSName = COSName.get_pdf_name("A")
_T: COSName = COSName.get_pdf_name("T")
_C: COSName = COSName.get_pdf_name("C")
_REL_P: COSName = COSName.get_pdf_name("P")


class PDTargetDirectory:
    """Target dictionary specifying path information to the target document
    of an embedded GoTo action. Mirrors PDFBox ``PDTargetDirectory`` lite
    surface (PDF 32000-1 Table 202)."""

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
            self._dict.set_item(_R, _C)
        else:
            self._dict = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /R relationship ----------

    def get_relationship(self) -> str | None:
        return self._dict.get_name(_R)

    def set_relationship(self, relationship: str) -> None:
        if relationship not in ("P", "C"):
            raise ValueError(
                f"The only valid values are P or C, not {relationship}"
            )
        self._dict.set_name(_R, relationship)

    # ---------- /N named destination (string) ----------

    def get_named_destination(self) -> str | None:
        return self._dict.get_string(_N)

    def set_named_destination(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_N)
            return
        self._dict.set_string(_N, name)

    # ---------- /P page number (int) ----------

    def get_page_number(self) -> int | None:
        v = self._dict.get_dictionary_object(_P)
        if isinstance(v, COSInteger):
            return v.value
        return None

    def set_page_number(self, page_number: int | None) -> None:
        if page_number is None:
            self._dict.remove_item(_P)
            return
        self._dict.set_int(_P, page_number)

    # ---------- /A annotation index (int) ----------

    def get_annotation_number(self) -> int | None:
        v = self._dict.get_dictionary_object(_A)
        if isinstance(v, COSInteger):
            return v.value
        return None

    def set_annotation_number(self, annotation_number: int | None) -> None:
        if annotation_number is None:
            self._dict.remove_item(_A)
            return
        self._dict.set_int(_A, annotation_number)

    # ---------- /T chained target ----------

    def get_target(self) -> PDTargetDirectory | None:
        v = self._dict.get_dictionary_object(_T)
        if isinstance(v, COSDictionary):
            return PDTargetDirectory(v)
        return None

    def set_target(self, target: PDTargetDirectory | None) -> None:
        if target is None:
            self._dict.remove_item(_T)
            return
        self._dict.set_item(_T, target.get_cos_object())


__all__ = ["PDTargetDirectory"]
