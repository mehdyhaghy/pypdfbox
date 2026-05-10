from __future__ import annotations

from typing import IO

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature

from .fdf_dictionary import FDFDictionary

_FDF: COSName = COSName.get_pdf_name("FDF")
_VERSION: COSName = COSName.get_pdf_name("Version")
_SIG: COSName = COSName.get_pdf_name("Sig")


class FDFCatalog:
    """The catalog (root object) of an FDF file. Mirrors
    ``org.apache.pdfbox.pdmodel.fdf.FDFCatalog``.

    Wraps the root dictionary and exposes the embedded ``/FDF``
    sub-dictionary via :meth:`get_fdf` (always non-``None``: an empty
    sub-dict is created on demand to match upstream construction
    semantics).
    """

    def __init__(self, catalog: COSDictionary | None = None) -> None:
        self._catalog: COSDictionary = catalog if catalog is not None else COSDictionary()
        # Lazily wrapped FDF sub-dictionary (so repeat calls return the
        # same FDFDictionary instance for a given underlying COS dict).
        self._fdf_wrapper: FDFDictionary | None = None

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._catalog

    # ---------- /FDF sub-dictionary ----------

    def get_fdf(self) -> FDFDictionary:
        """Return the embedded ``/FDF`` dictionary, creating an empty one
        on demand if the catalog does not yet carry one. Mirrors upstream
        ``FDFCatalog.getFDF()`` which never returns ``null``.
        """
        if self._fdf_wrapper is not None:
            existing = self._catalog.get_dictionary_object(_FDF)
            if existing is self._fdf_wrapper.get_cos_object():
                return self._fdf_wrapper
        v = self._catalog.get_dictionary_object(_FDF)
        if isinstance(v, COSDictionary):
            self._fdf_wrapper = FDFDictionary(v)
        else:
            new_dict = COSDictionary()
            self._catalog.set_item(_FDF, new_dict)
            self._fdf_wrapper = FDFDictionary(new_dict)
        return self._fdf_wrapper

    def has_fdf(self) -> bool:
        return isinstance(self._catalog.get_dictionary_object(_FDF), COSDictionary)

    def clear_fdf(self) -> None:
        self.set_fdf(None)

    def set_fdf(self, fdf: FDFDictionary | None) -> None:
        if fdf is None:
            self._catalog.remove_item(_FDF)
            self._fdf_wrapper = None
        else:
            self._catalog.set_item(_FDF, fdf.get_cos_object())
            self._fdf_wrapper = fdf

    # ---------- /Version (optional FDF version override) ----------

    def get_version(self) -> str | None:
        v = self._catalog.get_dictionary_object(_VERSION)
        if isinstance(v, COSName):
            return v.name
        return None

    def has_version(self) -> bool:
        return self.get_version() is not None

    def clear_version(self) -> None:
        self.set_version(None)

    def set_version(self, version: str | None) -> None:
        if version is None:
            self._catalog.remove_item(_VERSION)
        else:
            self._catalog.set_item(_VERSION, COSName.get_pdf_name(version))

    # ---------- /Sig (digital signature) ----------

    def get_signature(self) -> PDSignature | None:
        """Return the signature dictionary (``/Sig``) or ``None`` if absent.

        Mirrors upstream ``FDFCatalog.getSignature()`` (lines 147-151).
        """
        sig = self._catalog.get_dictionary_object(_SIG)
        if isinstance(sig, COSDictionary):
            return PDSignature(sig)
        return None

    def set_signature(self, sig: PDSignature | None) -> None:
        """Set the signature dictionary (``/Sig``).

        Mirrors upstream ``FDFCatalog.setSignature(PDSignature)`` (lines
        158-161). Passing ``None`` removes the entry; upstream lacks an
        explicit clear path but ``setItem(name, null)`` removes the key
        in PDFBox.
        """
        if sig is None:
            self._catalog.remove_item(_SIG)
        else:
            self._catalog.set_item(_SIG, sig.get_cos_object())

    # ---------- XFDF XML serialisation ----------

    def write_xml(self, output: IO[str]) -> None:
        """Serialise the embedded ``/FDF`` dictionary as XFDF XML to
        ``output``.

        Mirrors upstream ``FDFCatalog.writeXML(Writer)`` (lines 74-78),
        which simply delegates to the embedded FDF dictionary.
        """
        self.get_fdf().write_xml(output)
