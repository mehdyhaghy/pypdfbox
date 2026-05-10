from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSStream

from .pd_file_specification import PDFileSpecification

if TYPE_CHECKING:
    from .pd_embedded_file import PDEmbeddedFile

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

    #: Value written to the ``/Type`` entry of a complex file specification
    #: dictionary. Mirrors upstream ``COSName.FILESPEC``.
    FILESPEC: str = "Filespec"

    # ---------- /AFRelationship name values (ISO 32000-2 §14.13) ----------
    # The seven standard ``/AFRelationship`` values defined by ISO 32000-2
    # §14.13 (PDF/A-3 / PDF 2.0 associated files). Surfaced as plain
    # strings (matching the value written into ``/AFRelationship``) so
    # callers comparing :meth:`get_af_relationship` against a literal
    # pick them up without round-tripping through ``COSName``. pypdfbox
    # enrichment — Apache PDFBox 3.0 does not surface these as named
    # constants, leaving callers to re-spell them at every call site.
    AF_RELATIONSHIP_SOURCE: str = "Source"
    AF_RELATIONSHIP_DATA: str = "Data"
    AF_RELATIONSHIP_ALTERNATIVE: str = "Alternative"
    AF_RELATIONSHIP_SUPPLEMENT: str = "Supplement"
    AF_RELATIONSHIP_ENCRYPTED_PAYLOAD: str = "EncryptedPayload"
    AF_RELATIONSHIP_FORM_DATA: str = "FormData"
    AF_RELATIONSHIP_UNSPECIFIED: str = "Unspecified"

    _STANDARD_AF_RELATIONSHIPS: frozenset[str] = frozenset(
        {
            "Source",
            "Data",
            "Alternative",
            "Supplement",
            "EncryptedPayload",
            "FormData",
            "Unspecified",
        }
    )

    @classmethod
    def is_standard_af_relationship(cls, value: str | None) -> bool:
        """Predicate: is ``value`` one of the seven ISO 32000-2 §14.13
        registered ``/AFRelationship`` values?

        ``None`` returns ``False`` (the absence of /AFRelationship is
        legal but it is not a "standard value"). PDF 2.0 producers may
        write vendor-specific relationship names, so a ``False`` result
        only means "outside the registered set" — not "invalid"."""
        return value in cls._STANDARD_AF_RELATIONSHIPS

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
        ef = self._fs.get_dictionary_object(_EF)
        if isinstance(ef, COSDictionary):
            self._ef_dictionary = ef
            return ef
        self._ef_dictionary = None
        return None

    def _get_object_from_ef_dictionary(self, key: COSName) -> COSBase | None:
        ef = self._get_ef_dictionary()
        if ef is not None:
            return ef.get_dictionary_object(key)
        return None

    def get_ef_dictionary(self) -> COSDictionary | None:
        """Return the ``/EF`` sub-dictionary, or ``None`` when absent.

        Mirrors upstream private ``getEFDictionary``. Caches the
        resolved dictionary on the instance so repeated lookups don't
        re-resolve through the parent.
        """
        return self._get_ef_dictionary()

    def get_object_from_ef_dictionary(self, key: COSName) -> COSBase | None:
        """Return the entry stored under ``key`` inside ``/EF``.

        Mirrors upstream private ``getObjectFromEFDictionary``. Returns
        ``None`` when ``/EF`` is absent or the named key is missing.
        """
        return self._get_object_from_ef_dictionary(key)

    def _has_embedded(self, key: COSName) -> bool:
        return isinstance(self._get_object_from_ef_dictionary(key), COSStream)

    def _clear_embedded(self, key: COSName) -> None:
        ef = self._get_ef_dictionary()
        if ef is not None:
            ef.remove_item(key)

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

    def _get_embedded(self, key: COSName) -> PDEmbeddedFile | None:
        from .pd_embedded_file import PDEmbeddedFile

        base = self._get_object_from_ef_dictionary(key)
        if isinstance(base, COSStream):
            return PDEmbeddedFile(base)
        return None

    def _set_embedded(self, key: COSName, file: PDEmbeddedFile | None) -> None:
        ef = self._get_ef_dictionary()
        if ef is None and file is not None:
            ef = COSDictionary()
            self._fs.set_item(_EF, ef)
            self._ef_dictionary = ef
        if ef is not None:
            # ``COSDictionary.set_item(key, None)`` removes the entry, so
            # ``set_embedded_file(None)`` clears the slot without raising.
            # Mirrors upstream Java where ``setItem(key, COSObjectable)``
            # accepts a null value as a removal.
            ef.set_item(key, file.get_cos_object() if file is not None else None)

    def get_embedded_file(self) -> PDEmbeddedFile | None:
        return self._get_embedded(_F)

    def set_embedded_file(self, file: PDEmbeddedFile | None) -> None:
        self._set_embedded(_F, file)

    def get_embedded_file_dos(self) -> PDEmbeddedFile | None:
        return self._get_embedded(_DOS)

    def set_embedded_file_dos(self, file: PDEmbeddedFile | None) -> None:
        self._set_embedded(_DOS, file)

    def get_embedded_file_mac(self) -> PDEmbeddedFile | None:
        return self._get_embedded(_MAC)

    def set_embedded_file_mac(self, file: PDEmbeddedFile | None) -> None:
        self._set_embedded(_MAC, file)

    def get_embedded_file_unix(self) -> PDEmbeddedFile | None:
        return self._get_embedded(_UNIX)

    def set_embedded_file_unix(self, file: PDEmbeddedFile | None) -> None:
        self._set_embedded(_UNIX, file)

    def get_embedded_file_unicode(self) -> PDEmbeddedFile | None:
        return self._get_embedded(_UF)

    def set_embedded_file_unicode(self, file: PDEmbeddedFile | None) -> None:
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
        return self._fs.get_name_as_string(_AF_RELATIONSHIP)

    def set_af_relationship(self, relationship: str | None) -> None:
        """Set the ``/AFRelationship`` name entry. Pass ``None`` to
        remove. Mirrors PDFBox ``setAFRelationship(String)``."""
        if relationship is None:
            self._fs.remove_item(_AF_RELATIONSHIP)
            return
        self._fs.set_name(_AF_RELATIONSHIP, relationship)

    # ---------- presence predicates ----------
    # Distinguish "entry absent" from "entry explicitly set to a falsy
    # value" without forcing callers to grovel through the underlying
    # ``COSDictionary``. Useful for round-trip decisions where preserving
    # an absent entry matters for byte-exact re-serialisation. pypdfbox
    # enrichment — Apache PDFBox 3.0 makes callers compare the getter
    # result against ``null`` themselves.

    def has_file(self) -> bool:
        """``True`` when the required ``/F`` entry is present.
        A ``False`` return on a presumed-conformant file spec indicates
        a malformed dictionary — PDF 32000-1 §7.11.3 makes ``/F`` the
        canonical filename entry."""
        return self._fs.contains_key(_F)

    def has_file_unicode(self) -> bool:
        """``True`` when the ``/UF`` (Unicode filename) entry is present.
        ``/UF`` is preferred over ``/F`` for cross-platform compatibility
        (PDF 32000-1 §7.11.3)."""
        return self._fs.contains_key(_UF)

    def has_file_dos(self) -> bool:
        """``True`` when the deprecated ``/DOS`` entry is present.
        ISO 32000-2 deprecates this entry in favour of ``/UF``."""
        return self._fs.contains_key(_DOS)

    def has_file_mac(self) -> bool:
        """``True`` when the deprecated ``/Mac`` entry is present.
        ISO 32000-2 deprecates this entry in favour of ``/UF``."""
        return self._fs.contains_key(_MAC)

    def has_file_unix(self) -> bool:
        """``True`` when the deprecated ``/Unix`` entry is present.
        ISO 32000-2 deprecates this entry in favour of ``/UF``."""
        return self._fs.contains_key(_UNIX)

    def has_volatile(self) -> bool:
        """``True`` when an explicit ``/V`` entry is present.
        Distinguishes "spec default of ``false`` was implied" from "the
        writer recorded ``/V false`` explicitly". :meth:`is_volatile`
        always returns the effective value (defaulting to ``False``)."""
        return self._fs.contains_key(_V)

    def has_embedded_files(self) -> bool:
        """``True`` when the ``/EF`` (embedded-files) sub-dictionary is
        present and well-formed. Does not check whether ``/EF`` contains any
        embedded streams — an empty ``/EF`` dictionary still satisfies
        this predicate."""
        return self._get_ef_dictionary() is not None

    def has_embedded_file(self) -> bool:
        """``True`` when ``/EF/F`` resolves to an embedded-file stream."""
        return self._has_embedded(_F)

    def has_embedded_file_unicode(self) -> bool:
        """``True`` when ``/EF/UF`` resolves to an embedded-file stream."""
        return self._has_embedded(_UF)

    def has_embedded_file_dos(self) -> bool:
        """``True`` when ``/EF/DOS`` resolves to an embedded-file stream."""
        return self._has_embedded(_DOS)

    def has_embedded_file_mac(self) -> bool:
        """``True`` when ``/EF/Mac`` resolves to an embedded-file stream."""
        return self._has_embedded(_MAC)

    def has_embedded_file_unix(self) -> bool:
        """``True`` when ``/EF/Unix`` resolves to an embedded-file stream."""
        return self._has_embedded(_UNIX)

    def has_file_description(self) -> bool:
        """``True`` when the ``/Desc`` entry is present.
        ``/Desc`` is required by PDF/A-3 conformance (ISO 19005-3)."""
        return self._fs.contains_key(_DESC)

    def has_af_relationship(self) -> bool:
        """``True`` when the ``/AFRelationship`` name entry is present.
        Required for PDF/A-3 associated files (ISO 19005-3 §6.10.2)."""
        return self._fs.contains_key(_AF_RELATIONSHIP)

    # ---------- clear_* (symmetric to has_*) ----------
    # Convenience shortcuts that remove an optional entry from the
    # underlying dictionary. pypdfbox enrichment — Apache PDFBox 3.0
    # does not surface explicit clearers on ``PDComplexFileSpecification``.

    def clear_volatile(self) -> None:
        """Remove the ``/V`` entry. After this call :meth:`is_volatile`
        returns the spec default of ``False``."""
        self._fs.remove_item(_V)

    def clear_file_description(self) -> None:
        """Remove the ``/Desc`` entry. No-op if absent. PDF/A-3
        conformance requires ``/Desc`` on associated files — clearing
        it on a PDF/A-3 file spec yields a non-conformant dictionary."""
        self._fs.remove_item(_DESC)

    def clear_af_relationship(self) -> None:
        """Remove the ``/AFRelationship`` entry. Equivalent to
        ``set_af_relationship(None)``."""
        self._fs.remove_item(_AF_RELATIONSHIP)

    def clear_embedded_files(self) -> None:
        """Remove the ``/EF`` sub-dictionary entirely. Drops every
        embedded-file slot (``/F``, ``/UF``, ``/DOS``, ``/Mac``, ``/Unix``)
        in one call. Also clears the cached reference held on this
        instance so a subsequent :meth:`set_embedded_file` rebuilds the
        ``/EF`` dictionary from scratch."""
        self._fs.remove_item(_EF)
        self._ef_dictionary = None

    def clear_embedded_file(self) -> None:
        """Remove the ``/EF/F`` embedded-file slot. No-op if absent."""
        self._clear_embedded(_F)

    def clear_embedded_file_unicode(self) -> None:
        """Remove the ``/EF/UF`` embedded-file slot. No-op if absent."""
        self._clear_embedded(_UF)

    def clear_embedded_file_dos(self) -> None:
        """Remove the ``/EF/DOS`` embedded-file slot. No-op if absent."""
        self._clear_embedded(_DOS)

    def clear_embedded_file_mac(self) -> None:
        """Remove the ``/EF/Mac`` embedded-file slot. No-op if absent."""
        self._clear_embedded(_MAC)

    def clear_embedded_file_unix(self) -> None:
        """Remove the ``/EF/Unix`` embedded-file slot. No-op if absent."""
        self._clear_embedded(_UNIX)

    # ---------- structural emptiness ----------

    def is_empty(self) -> bool:
        """``True`` when the dictionary carries no meaningful filename,
        embedded-file, description, or relationship entry.

        ``/Type`` is ignored — a fresh-but-empty file spec still carries
        ``/Type /Filespec`` from the constructor. ``/V`` is ignored too
        — its spec default is ``False`` and an explicit ``/V false`` is
        equivalent to absence for the purposes of "is this file spec
        meaningful". Useful for callers deciding whether to persist a
        draft file spec. pypdfbox enrichment — Apache PDFBox 3.0 does
        not expose an emptiness check."""
        return not (
            self.has_file()
            or self.has_file_unicode()
            or self.has_file_dos()
            or self.has_file_mac()
            or self.has_file_unix()
            or self.has_embedded_files()
            or self.has_file_description()
            or self.has_af_relationship()
        )


__all__ = ["PDComplexFileSpecification"]
