from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSBoolean, COSDictionary, COSName

from .pd_annotation import PDAnnotation

_3DD: COSName = COSName.get_pdf_name("3DD")
_3DV: COSName = COSName.get_pdf_name("3DV")
_3DA: COSName = COSName.get_pdf_name("3DA")
_3DI: COSName = COSName.get_pdf_name("3DI")
_3DB: COSName = COSName.get_pdf_name("3DB")


class PDAnnotation3D(PDAnnotation):
    """
    3D annotation — ``/Subtype /3D``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation3D``.

    3D annotations are how 3D artwork is represented in a PDF document
    (PDF 32000-1:2008 §13.6.2, Table 298). Not a markup annotation —
    extends :class:`PDAnnotation` directly.

    Subtype-specific entries beyond base:

    * ``/3DD`` — required. The 3D stream (or 3D reference dictionary)
      specifying the default artwork.
    * ``/3DV`` — default initial view of the 3D artwork (3D view
      dictionary, ``COSDictionary``, name, or integer index into
      ``3DD``'s ``VA`` array).
    * ``/3DA`` — activation dictionary (Table 299) controlling how the
      annotation is activated and deactivated.
    * ``/3DI`` — interactive flag. ``true`` (default) means primary content
      is interactive; ``false`` means primary content is the poster image.
    * ``/3DB`` — view box. Rectangle within ``/Rect`` where the 3D content
      is rendered (PDF 2.0 / extension).
    """

    SUB_TYPE: str = "3D"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /3DD (3D artwork) ----------

    def get_3dd(self) -> COSBase | None:
        """Return the raw ``/3DD`` value (a 3D stream or 3D reference
        dictionary)."""
        return self._dict.get_dictionary_object(_3DD)

    def set_3dd(self, value: COSBase | None) -> None:
        if value is None:
            self._dict.remove_item(_3DD)
            return
        self._dict.set_item(
            _3DD,
            value.get_cos_object() if hasattr(value, "get_cos_object") else value,
        )

    def get_artwork(self) -> COSBase | None:
        """Descriptive alias for the raw ``/3DD`` 3D artwork entry."""
        return self.get_3dd()

    def set_artwork(self, value: COSBase | None) -> None:
        self.set_3dd(value)

    # ---------- /3DV (default view) ----------

    def get_3dv(self) -> COSBase | None:
        """Return the raw ``/3DV`` default view (dictionary, name, or integer)."""
        return self._dict.get_dictionary_object(_3DV)

    def set_3dv(self, value: COSBase | None) -> None:
        if value is None:
            self._dict.remove_item(_3DV)
            return
        self._dict.set_item(
            _3DV,
            value.get_cos_object() if hasattr(value, "get_cos_object") else value,
        )

    def get_default_view(self) -> COSBase | None:
        """Descriptive alias for the raw ``/3DV`` default-view entry."""
        return self.get_3dv()

    def set_default_view(self, value: COSBase | None) -> None:
        self.set_3dv(value)

    # ---------- /3DA (activation dictionary) ----------

    def get_3da(self) -> COSDictionary | None:
        """Return the raw ``/3DA`` activation dictionary."""
        value = self._dict.get_dictionary_object(_3DA)
        if isinstance(value, COSDictionary):
            return value
        return None

    def set_3da(self, value: COSDictionary | None) -> None:
        if value is None:
            self._dict.remove_item(_3DA)
            return
        self._dict.set_item(
            _3DA,
            value.get_cos_object() if hasattr(value, "get_cos_object") else value,
        )

    def get_activation_dictionary(self) -> COSDictionary | None:
        """Descriptive alias for the raw ``/3DA`` activation dictionary."""
        return self.get_3da()

    def set_activation_dictionary(self, value: COSDictionary | None) -> None:
        self.set_3da(value)

    # ---------- /3DI (interactive flag) ----------

    def is_interactive(self) -> bool:
        """``/3DI`` — default ``True`` per spec."""
        value = self._dict.get_dictionary_object(_3DI)
        if isinstance(value, COSBoolean):
            return bool(value.get_value())
        return True

    def set_interactive(self, value: bool) -> None:
        self._dict.set_item(_3DI, COSBoolean.get_boolean(bool(value)))

    # ---------- /3DB (view box) ----------

    def get_3db(self) -> COSArray | None:
        value = self._dict.get_dictionary_object(_3DB)
        if isinstance(value, COSArray):
            return value
        return None

    def set_3db(self, value: COSArray | None) -> None:
        if value is None:
            self._dict.remove_item(_3DB)
            return
        self._dict.set_item(_3DB, value)


__all__ = ["PDAnnotation3D"]
