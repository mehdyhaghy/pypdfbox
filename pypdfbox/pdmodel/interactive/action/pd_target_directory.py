from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString

_R: COSName = COSName.get_pdf_name("R")
_N: COSName = COSName.get_pdf_name("N")
_P: COSName = COSName.get_pdf_name("P")
_A: COSName = COSName.get_pdf_name("A")
_T: COSName = COSName.get_pdf_name("T")
_C: COSName = COSName.get_pdf_name("C")


class PDTargetDirectory:
    """Target dictionary specifying path information to the target document
    of an embedded GoTo action. Mirrors PDFBox ``PDTargetDirectory`` lite
    surface (PDF 32000-1 Table 202).

    Per spec:
        /N — name of the file in the ``/EmbeddedFiles`` name tree (when
             the relationship is ``/C``: child target).
        /P — either the integer page index of the target (0-based) or the
             name of a named destination in the target document.
        /A — either the integer index of an annotation on the target page
             or the value of its ``/NM`` entry.
        /T — chained ``PDTargetDirectory`` for the next nested target.
    """

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

    # ---------- /N target embedded-file name ----------

    def get_target_filename(self) -> str | None:
        """The name of the embedded file in the target catalog's
        ``/EmbeddedFiles`` name tree (per PDF 32000-1 Table 202 ``/N``)."""
        return self._dict.get_string(_N)

    def set_target_filename(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_N)
            return
        self._dict.set_string(_N, name)

    # ---------- /P page number (int form) ----------

    def get_page_number(self) -> int | None:
        """Integer page index from ``/P`` (0-based). Returns ``None`` when
        ``/P`` is absent or carries the named-destination string form
        instead — use :meth:`get_named_destination` for that case."""
        v = self._dict.get_dictionary_object(_P)
        if isinstance(v, COSInteger):
            return v.value
        return None

    def set_page_number(self, page_number: int | None) -> None:
        if page_number is None:
            self._dict.remove_item(_P)
            return
        self._dict.set_int(_P, page_number)

    # ---------- /P named destination (string form) ----------

    def get_named_destination(self) -> str | None:
        """Named-destination string from ``/P`` (per PDF 32000-1 Table 202
        ``/P`` may also be a name resolved against the target document's
        ``/Dests`` map). Returns ``None`` when ``/P`` is absent or carries
        the integer page-index form — use :meth:`get_page_number` for
        that case."""
        v = self._dict.get_dictionary_object(_P)
        if isinstance(v, COSString):
            return v.get_string()
        return None

    def set_named_destination(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_P)
            return
        self._dict.set_string(_P, name)

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
