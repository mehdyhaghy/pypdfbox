from __future__ import annotations

from pypdfbox.cos import COSBase, COSBoolean, COSDictionary, COSName

from .pd_annotation import PDAnnotation
from .pd_movie import PDMovie
from .pd_movie_activation import PDMovieActivation

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
    as a typed ``PDMovie`` wrapper, with raw COS dictionary accessors retained
    for compatibility. The ``/A`` activation entry can be a boolean or a movie
    activation dictionary; typed activation dictionaries are surfaced through
    ``PDMovieActivation``.
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

    def getTitle(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_title()

    def setTitle(self, value: str | None) -> None:  # noqa: N802 - upstream Java name
        self.set_title(value)

    # ---------- /Movie (movie dictionary, required) ----------

    def get_movie_dictionary(self) -> COSDictionary | None:
        value = self._dict.get_dictionary_object(_MOVIE)
        if isinstance(value, COSDictionary):
            return value
        return None

    def get_movie(self) -> PDMovie | None:
        value = self.get_movie_dictionary()
        if value is None:
            return None
        return PDMovie(value)

    def getMovie(self) -> PDMovie | None:  # noqa: N802 - upstream Java name
        return self.get_movie()

    def set_movie(self, value: PDMovie | COSDictionary | None) -> None:
        if value is None:
            self._dict.remove_item(_MOVIE)
            return
        if isinstance(value, PDMovie):
            self._dict.set_item(_MOVIE, value.get_cos_object())
            return
        self._dict.set_item(_MOVIE, value)

    def setMovie(  # noqa: N802 - upstream Java name
        self, value: PDMovie | COSDictionary | None
    ) -> None:
        self.set_movie(value)

    # ---------- /A (activation: boolean or activation dict, default true) ----------

    def get_activation_entry(self) -> COSBase | None:
        return self._dict.get_dictionary_object(_A)

    def get_activation(self) -> PDMovieActivation | bool | None:
        value = self.get_activation_entry()
        if isinstance(value, COSDictionary):
            return PDMovieActivation(value)
        if isinstance(value, COSBoolean):
            return value.value
        return None

    def getActivation(self) -> PDMovieActivation | bool | None:  # noqa: N802
        return self.get_activation()

    def get_effective_activation(self) -> PDMovieActivation | bool | None:
        """Return ``/A`` with the spec default applied.

        ``/A`` defaults to ``true`` when absent. Malformed non-boolean,
        non-dictionary entries still return ``None`` so callers can
        distinguish them from the absent-entry default.
        """
        value = self.get_activation_entry()
        if value is None:
            return True
        if isinstance(value, COSDictionary):
            return PDMovieActivation(value)
        if isinstance(value, COSBoolean):
            return value.value
        return None

    def set_activation(
        self, value: PDMovieActivation | COSBase | bool | None
    ) -> None:
        if value is None:
            self._dict.remove_item(_A)
            return
        if isinstance(value, bool):
            self._dict.set_boolean(_A, value)
            return
        if isinstance(value, PDMovieActivation):
            self._dict.set_item(_A, value.get_cos_object())
            return
        cos_value = value.get_cos_object() if hasattr(value, "get_cos_object") else value
        self._dict.set_item(_A, cos_value)

    def setActivation(  # noqa: N802 - upstream Java name
        self, value: PDMovieActivation | COSBase | bool | None
    ) -> None:
        self.set_activation(value)

    def has_activation(self) -> bool:
        """Return ``True`` when ``/A`` is explicitly present."""
        return self._dict.get_dictionary_object(_A) is not None

    def clear_activation(self) -> None:
        """Remove ``/A`` and restore the implicit ``true`` default."""
        self._dict.remove_item(_A)


__all__ = ["PDAnnotationMovie"]
