from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_annotation import PDAnnotation

_T: COSName = COSName.get_pdf_name("T")
_MOVIE: COSName = COSName.get_pdf_name("Movie")
_A: COSName = COSName.get_pdf_name("A")


class PDAnnotationMovie(PDAnnotation):
    """
    Movie annotation — ``/Subtype /Movie``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationMovie``.

    Contains animated graphics and sound to be presented on the computer
    screen and through the speakers (PDF 32000-1:2008 §12.5.6.17,
    Table 184). The companion ``/Movie`` dictionary (Table 271) is exposed
    here as a raw ``COSDictionary``; a typed ``PDMovie`` wrapper is
    deferred — see ``CHANGES.md``. The ``/A`` activation entry can be a
    boolean *or* a movie-activation dictionary; we surface it as a raw
    ``COSBase`` for the same reason.
    """

    SUB_TYPE: str = "Movie"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /T (annotation title) ----------

    def get_title(self) -> str | None:
        return self._dict.get_string(_T)

    def set_title(self, value: str | None) -> None:
        self._dict.set_string(_T, value)

    # ---------- /Movie (movie dictionary, required) ----------

    def get_movie(self) -> COSDictionary | None:
        value = self._dict.get_dictionary_object(_MOVIE)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_movie(self, value: COSDictionary | None) -> None:
        if value is None:
            self._dict.remove_item(_MOVIE)
            return
        self._dict.set_item(_MOVIE, value)

    # ---------- /A (activation: boolean or activation dict, default true) ----------

    def get_activation(self) -> COSBase | None:
        return self._dict.get_dictionary_object(_A)

    def set_activation(self, value: COSBase | None) -> None:
        if value is None:
            self._dict.remove_item(_A)
            return
        self._dict.set_item(
            _A,
            value.get_cos_object() if hasattr(value, "get_cos_object") else value,
        )


__all__ = ["PDAnnotationMovie"]
