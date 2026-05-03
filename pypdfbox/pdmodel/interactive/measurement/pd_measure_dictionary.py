from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString

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

    #: The ``/Subtype`` value for rectlinear measure dictionaries.
    #:
    #: Mirrors :attr:`PDRectlinearMeasureDictionary.SUBTYPE`. Exposed on the
    #: base class so callers can dispatch on the subtype string without
    #: importing the rectlinear subclass (which would create an import cycle
    #: in some collaborator modules). PDF 32000-1 §12.7.5.5.
    SUBTYPE_RECTLINEAR: str = "RL"

    #: The ``/Subtype`` value for geospatial measure dictionaries.
    #:
    #: PDF 32000-1 §12.7.5.6 defines this subtype but upstream PDFBox 3.0.x
    #: does not provide a wrapper class for it; the constant is exposed for
    #: callers that need to recognize geospatial measures in third-party
    #: PDFs.
    SUBTYPE_GEOSPATIAL: str = "GEO"

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

        Per upstream ``COSDictionary.getNameAsString``, a ``/Subtype`` stored
        as a ``COSString`` (rather than a ``COSName``) is also returned as
        its string value, not the default.
        """
        # Local import to avoid an import cycle with the subclass.
        from .pd_rectlinear_measure_dictionary import (  # noqa: PLC0415
            PDRectlinearMeasureDictionary,
        )

        raw = self._dict.get_dictionary_object(_SUBTYPE)
        if isinstance(raw, COSName):
            return raw.name
        if isinstance(raw, COSString):
            return raw.get_string()
        return PDRectlinearMeasureDictionary.SUBTYPE

    def _set_subtype(self, subtype: str) -> None:
        """Set the subtype of the measure dictionary.

        This corresponds to upstream's ``protected void setSubtype(String)``;
        Python lacks language-level access control, so the leading underscore
        signals the intended "protected" semantics. Subclasses set their own
        subtype constant via this hook.
        """
        self._dict.set_name(_SUBTYPE, subtype)

    # ------------------------------------------------------------------ subtype predicates
    def is_rectlinear(self) -> bool:
        """Return ``True`` if this is a rectlinear measure dictionary.

        A measure dictionary is treated as rectlinear when its ``/Subtype``
        resolves to ``"RL"`` — including the upstream-default behavior of
        treating an *absent* ``/Subtype`` as ``"RL"`` (see
        :meth:`get_subtype`). This mirrors the contract upstream PDFBox
        relies on when constructing :class:`PDRectlinearMeasureDictionary`
        from a generic measure dictionary.
        """
        return self.get_subtype() == self.SUBTYPE_RECTLINEAR

    def is_geospatial(self) -> bool:
        """Return ``True`` if this is a geospatial measure dictionary.

        Per PDF 32000-1 §12.7.5.6 the ``/Subtype`` value for geospatial
        measures is ``"GEO"``. Upstream PDFBox 3.0.x has no wrapper class
        for this subtype; the predicate lets callers detect such
        dictionaries without re-deriving the magic string.
        """
        return self.get_subtype() == self.SUBTYPE_GEOSPATIAL


__all__ = ["PDMeasureDictionary"]
