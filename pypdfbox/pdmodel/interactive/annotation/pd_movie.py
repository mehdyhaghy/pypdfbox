from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)

_F: COSName = COSName.get_pdf_name("F")
_ASPECT: COSName = COSName.get_pdf_name("Aspect")
_ROTATE: COSName = COSName.get_pdf_name("Rotate")
_POSTER: COSName = COSName.get_pdf_name("Poster")


class PDMovie:
    """Movie dictionary wrapper for ``/Movie`` annotation payloads.

    Covers the PDF 32000-1 Table 271 scalar fields. Richer viewer playback
    behaviour still lives in :class:`PDMovieActivation`.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_file(self) -> PDFileSpecification | None:
        return PDFileSpecification.create_fs(self._dict.get_dictionary_object(_F))

    def set_file(self, file_spec: PDFileSpecification | COSBase | str | None) -> None:
        if file_spec is None:
            self._dict.remove_item(_F)
            return
        if isinstance(file_spec, str):
            self._dict.set_string(_F, file_spec)
            return
        if isinstance(file_spec, PDFileSpecification):
            self._dict.set_item(_F, file_spec.get_cos_object())
            return
        self._dict.set_item(_F, file_spec)

    def get_aspect(self) -> tuple[int, int] | None:
        value = self._dict.get_dictionary_object(_ASPECT)
        if isinstance(value, COSArray) and value.size() >= 2:
            return (value.get_int(0), value.get_int(1))
        return None

    def set_aspect(
        self,
        width: int | tuple[int, int] | list[int] | None,
        height: int | None = None,
    ) -> None:
        # Single-arg tuple/list form mirrors common ``Aspect`` array shape.
        if isinstance(width, (tuple, list)):
            if len(width) < 2:
                self._dict.remove_item(_ASPECT)
                return
            w, h = int(width[0]), int(width[1])
            self._dict.set_item(_ASPECT, COSArray.of_cos_integers((w, h)))
            return
        if width is None or height is None:
            self._dict.remove_item(_ASPECT)
            return
        self._dict.set_item(_ASPECT, COSArray.of_cos_integers((width, height)))

    def get_rotation(self) -> int:
        return self._dict.get_int(_ROTATE, 0)

    def set_rotation(self, rotation: int | None) -> None:
        if rotation is None:
            self._dict.remove_item(_ROTATE)
            return
        self._dict.set_int(_ROTATE, rotation)

    def get_poster(self) -> COSBase | bool | None:
        value = self._dict.get_dictionary_object(_POSTER)
        if value is None:
            return None
        from pypdfbox.cos import COSBoolean

        if isinstance(value, COSBoolean):
            return value.value
        return value

    def set_poster(self, poster: COSBase | bool | None) -> None:
        if poster is None:
            self._dict.remove_item(_POSTER)
            return
        if isinstance(poster, bool):
            self._dict.set_boolean(_POSTER, poster)
            return
        self._dict.set_item(_POSTER, poster)


__all__ = ["PDMovie"]
