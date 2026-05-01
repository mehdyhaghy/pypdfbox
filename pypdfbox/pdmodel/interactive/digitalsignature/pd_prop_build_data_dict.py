from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

_NAME: COSName = COSName.get_pdf_name("Name")
_DATE: COSName = COSName.get_pdf_name("Date")
_REX: COSName = COSName.get_pdf_name("REx")
_R: COSName = COSName.get_pdf_name("R")
_V: COSName = COSName.get_pdf_name("V")
_PRE_RELEASE: COSName = COSName.get_pdf_name("PreRelease")
_OS: COSName = COSName.get_pdf_name("OS")
_NON_EFONT_NO_WARN: COSName = COSName.get_pdf_name("NonEFontNoWarn")
_TRUSTED_MODE: COSName = COSName.get_pdf_name("TrustedMode")


class PDPropBuildDataDict:
    """The general property data dictionaries from the build property
    dictionary. Mirrors PDFBox ``PDPropBuildDataDict``.

    See: PDF Signature Build Dictionary Specification (Adobe).
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
        else:
            self._dict = dictionary
        # The specification claims to use direct objects.
        self._dict.set_direct(True)

    # ---------- COS object access ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Name ----------

    def get_name(self) -> str | None:
        """Name of the software module that was used to create the signature."""
        return self._dict.get_name(_NAME)

    def set_name(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_NAME)
            return
        self._dict.set_name(_NAME, name)

    # ---------- /Date ----------

    def get_date(self) -> str | None:
        """Build date of the software module. Not necessarily a PDF Date."""
        return self._dict.get_string(_DATE)

    def set_date(self, date: str | None) -> None:
        if date is None:
            self._dict.remove_item(_DATE)
            return
        self._dict.set_string(_DATE, date)

    # ---------- /REx version ----------

    def get_version(self) -> str | None:
        """Application implementation version (e.g. ``7.0.7``).

        Stored under the ``/REx`` key as specified by Adobe's PDF Signature
        Build Dictionary Specification when this dict is the ``/App``
        sub-dictionary of a build properties dictionary.
        """
        return self._dict.get_string(_REX)

    def set_version(self, application_version: str | None) -> None:
        if application_version is None:
            self._dict.remove_item(_REX)
            return
        self._dict.set_string(_REX, application_version)

    # ---------- /R revision ----------

    def get_revision(self) -> int:
        """Software module revision number, corresponding to ``/Date``.

        Returns ``-1`` (PDFBox ``getLong`` default) if absent.
        """
        return self._dict.get_long(_R)

    def set_revision(self, revision: int) -> None:
        self._dict.set_long(_R, revision)

    # ---------- /V minimum revision (deprecated PDF 1.7) ----------

    def get_minimum_revision(self) -> int:
        """Software module revision required to process this signature.

        Note: deprecated for PDF v1.7. Returns ``-1`` if absent.
        """
        return self._dict.get_long(_V)

    def set_minimum_revision(self, revision: int) -> None:
        self._dict.set_long(_V, revision)

    # ---------- /PreRelease ----------

    def get_pre_release(self) -> bool:
        """``True`` if signature was created with unreleased software."""
        return self._dict.get_boolean(_PRE_RELEASE, False)

    def set_pre_release(self, pre_release: bool) -> None:
        self._dict.set_boolean(_PRE_RELEASE, pre_release)

    # ---------- /OS ----------

    def get_os(self) -> str | None:
        """Operating system identifier.

        PDF v1.5 specifies a string; PDF v1.7 specifies an array of names.
        Both encodings are supported on read.
        """
        v = self._dict.get_dictionary_object(_OS)
        if isinstance(v, COSArray):
            return v.get_name(0)
        return self._dict.get_string(_OS)

    def set_os(self, os: str | None) -> None:
        """Set OS identifier. Stored as the first item of an array of names,
        per PDF v1.7 PDF Signature Build Dictionary Specification.
        """
        if os is None:
            self._dict.remove_item(_OS)
            return
        v = self._dict.get_dictionary_object(_OS)
        if not isinstance(v, COSArray):
            v = COSArray()
            v.set_direct(True)
            self._dict.set_item(_OS, v)
        v.add_at(0, COSName.get_pdf_name(os))

    # ---------- /NonEFontNoWarn ----------

    def get_non_e_font_no_warn(self) -> bool:
        """``True`` if the reader should suppress the non-embedded font
        warning. Default ``True`` (matches upstream).
        """
        return self._dict.get_boolean(_NON_EFONT_NO_WARN, True)

    def set_non_e_font_no_warn(self, no_embed_font_warning: bool) -> None:
        self._dict.set_boolean(_NON_EFONT_NO_WARN, no_embed_font_warning)

    # ---------- /TrustedMode ----------

    def get_trusted_mode(self) -> bool:
        """``True`` if the application was in trusted mode while signing."""
        return self._dict.get_boolean(_TRUSTED_MODE, False)

    def set_trusted_mode(self, trusted_mode: bool) -> None:
        self._dict.set_boolean(_TRUSTED_MODE, trusted_mode)


__all__ = ["PDPropBuildDataDict"]
