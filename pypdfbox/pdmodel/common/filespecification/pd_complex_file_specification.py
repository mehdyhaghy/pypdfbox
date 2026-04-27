from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSStream

from .pd_file_specification import PDFileSpecification

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_FILESPEC: COSName = COSName.get_pdf_name("Filespec")
_F: COSName = COSName.get_pdf_name("F")
_UF: COSName = COSName.get_pdf_name("UF")
_DOS: COSName = COSName.get_pdf_name("DOS")
_MAC: COSName = COSName.get_pdf_name("Mac")
_UNIX: COSName = COSName.get_pdf_name("Unix")
_V: COSName = COSName.get_pdf_name("V")
_EF: COSName = COSName.get_pdf_name("EF")
_DESC: COSName = COSName.get_pdf_name("Desc")
_AF_RELATIONSHIP: COSName = COSName.get_pdf_name("AFRelationship")


class PDComplexFileSpecification(PDFileSpecification):
    """``/Type /Filespec`` dictionary form of a file specification. Mirrors
    PDFBox ``PDComplexFileSpecification``."""

    def __init__(self, dict_: COSDictionary | None = None) -> None:
        if dict_ is None:
            self._fs: COSDictionary = COSDictionary()
            self._fs.set_item(_TYPE, _FILESPEC)
        else:
            self._fs = dict_
        self._ef_dictionary: COSDictionary | None = None

    def get_cos_object(self) -> COSDictionary:
        return self._fs

    # ---------- /EF nested dictionary helpers ----------

    def _get_ef_dictionary(self) -> COSDictionary | None:
        if self._ef_dictionary is None and self._fs is not None:
            ef = self._fs.get_dictionary_object(_EF)
            if isinstance(ef, COSDictionary):
                self._ef_dictionary = ef
        return self._ef_dictionary

    def _get_object_from_ef_dictionary(self, key: COSName) -> COSBase | None:
        ef = self._get_ef_dictionary()
        if ef is not None:
            return ef.get_dictionary_object(key)
        return None

    # ---------- preferred filename ----------

    def get_filename(self) -> str | None:
        """Recommended file name. Tries unicode, then DOS, Mac, Unix,
        then the required ``/F`` entry. May contain a directory separator —
        callers must sanitise (CWE-22)."""
        filename = self.get_file_unicode()
        if filename is None:
            filename = self.get_file_dos()
        if filename is None:
            filename = self.get_file_mac()
        if filename is None:
            filename = self.get_file_unix()
        if filename is None:
            filename = self.get_file()
        return filename

    # ---------- /F /UF /DOS /Mac /Unix accessors ----------

    def get_file_unicode(self) -> str | None:
        return self._fs.get_string(_UF)

    def set_file_unicode(self, file: str | None) -> None:
        self._fs.set_string(_UF, file)

    def get_file(self) -> str | None:
        return self._fs.get_string(_F)

    def set_file(self, file: str | None) -> None:
        self._fs.set_string(_F, file)

    def get_file_dos(self) -> str | None:
        return self._fs.get_string(_DOS)

    def set_file_dos(self, file: str | None) -> None:
        self._fs.set_string(_DOS, file)

    def get_file_mac(self) -> str | None:
        return self._fs.get_string(_MAC)

    def set_file_mac(self, file: str | None) -> None:
        self._fs.set_string(_MAC, file)

    def get_file_unix(self) -> str | None:
        return self._fs.get_string(_UNIX)

    def set_file_unix(self, file: str | None) -> None:
        self._fs.set_string(_UNIX, file)

    # ---------- /V volatile ----------

    def set_volatile(self, file_is_volatile: bool) -> None:
        self._fs.set_boolean(_V, file_is_volatile)

    def is_volatile(self) -> bool:
        return self._fs.get_boolean(_V, False)

    # ---------- embedded file accessors ----------

    def _get_embedded(self, key: COSName) -> "PDEmbeddedFile | None":  # noqa: F821
        from .pd_embedded_file import PDEmbeddedFile

        base = self._get_object_from_ef_dictionary(key)
        if isinstance(base, COSStream):
            return PDEmbeddedFile(base)
        return None

    def _set_embedded(self, key: COSName, file: "PDEmbeddedFile | None") -> None:  # noqa: F821
        ef = self._get_ef_dictionary()
        if ef is None and file is not None:
            ef = COSDictionary()
            self._fs.set_item(_EF, ef)
            self._ef_dictionary = ef
        if ef is not None:
            ef.set_item(key, file.get_cos_object())

    def get_embedded_file(self) -> "PDEmbeddedFile | None":  # noqa: F821
        return self._get_embedded(_F)

    def set_embedded_file(self, file: "PDEmbeddedFile | None") -> None:  # noqa: F821
        self._set_embedded(_F, file)

    def get_embedded_file_dos(self) -> "PDEmbeddedFile | None":  # noqa: F821
        return self._get_embedded(_DOS)

    def get_embedded_file_mac(self) -> "PDEmbeddedFile | None":  # noqa: F821
        return self._get_embedded(_MAC)

    def get_embedded_file_unix(self) -> "PDEmbeddedFile | None":  # noqa: F821
        return self._get_embedded(_UNIX)

    def get_embedded_file_unicode(self) -> "PDEmbeddedFile | None":  # noqa: F821
        return self._get_embedded(_UF)

    def set_embedded_file_unicode(self, file: "PDEmbeddedFile | None") -> None:  # noqa: F821
        self._set_embedded(_UF, file)

    # ---------- /Desc description ----------

    def set_file_description(self, description: str | None) -> None:
        self._fs.set_string(_DESC, description)

    def get_file_description(self) -> str | None:
        return self._fs.get_string(_DESC)

    # ---------- /AFRelationship (PDF/A-3, ISO 19005-3 / ISO 32000-2 §14.13) ----------

    def get_af_relationship(self) -> str | None:
        """Return the value of the ``/AFRelationship`` name entry, or
        ``None`` if absent. Per ISO 32000-2 §14.13 the standard values
        are ``Source``, ``Data``, ``Alternative``, ``Supplement``,
        ``EncryptedPayload``, ``FormData`` and ``Unspecified``.
        Mirrors PDFBox ``getAFRelationship()``."""
        return self._fs.get_name(_AF_RELATIONSHIP)

    def set_af_relationship(self, relationship: str | None) -> None:
        """Set the ``/AFRelationship`` name entry. Pass ``None`` to
        remove. Mirrors PDFBox ``setAFRelationship(String)``."""
        if relationship is None:
            self._fs.remove_item(_AF_RELATIONSHIP)
            return
        self._fs.set_name(_AF_RELATIONSHIP, relationship)


__all__ = ["PDComplexFileSpecification"]
