from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]


class PDMeasureDictionary:
    """This class represents a measure dictionary.

    Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.interactive.measurement.PDMeasureDictionary``.

    Wraps a :class:`COSDictionary` whose ``/Type`` is ``Measure``. The
    ``/Subtype`` distinguishes between flavors (``RL`` for rectlinear, the
    only flavor implemented by upstream PDFBox 3.0.x).
    """

    #: The ``/Type`` value of the dictionary.
    TYPE: str = "Measure"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
            self._dict.set_name(_TYPE, self.TYPE)
        else:
            self._dict = dictionary

    # ------------------------------------------------------------------ COSObjectable
    def get_cos_object(self) -> COSDictionary:
        """Return the underlying ``COSDictionary``."""
        return self._dict

    # ------------------------------------------------------------------ /Type
    def get_type(self) -> str:
        """Return the type of the measure dictionary, always ``Measure``."""
        return self.TYPE

    # ------------------------------------------------------------------ /Subtype
    def get_subtype(self) -> str:
        """Return the subtype of the measure dictionary.

        Defaults to :attr:`PDRectlinearMeasureDictionary.SUBTYPE` (``"RL"``)
        if the entry is missing — matches upstream's
        ``getNameAsString(COSName.SUBTYPE, PDRectlinearMeasureDictionary.SUBTYPE)``.
        """
        # Local import to avoid an import cycle with the subclass.
        from .pd_rectlinear_measure_dictionary import (  # noqa: PLC0415
            PDRectlinearMeasureDictionary,
        )

        value = self._dict.get_name(_SUBTYPE, PDRectlinearMeasureDictionary.SUBTYPE)
        return value if value is not None else PDRectlinearMeasureDictionary.SUBTYPE

    def _set_subtype(self, subtype: str) -> None:
        """Set the subtype of the measure dictionary.

        This corresponds to upstream's ``protected void setSubtype(String)``;
        Python lacks language-level access control, so the leading underscore
        signals the intended "protected" semantics. Subclasses set their own
        subtype constant via this hook.
        """
        self._dict.set_name(_SUBTYPE, subtype)


__all__ = ["PDMeasureDictionary"]
