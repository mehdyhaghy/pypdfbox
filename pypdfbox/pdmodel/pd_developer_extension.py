from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString


_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_DEVELOPER_EXTENSIONS: COSName = COSName.get_pdf_name("DeveloperExtensions")
_BASE_VERSION: COSName = COSName.get_pdf_name("BaseVersion")
_EXTENSION_LEVEL: COSName = COSName.get_pdf_name("ExtensionLevel")
_URL: COSName = COSName.get_pdf_name("URL")


class PDDeveloperExtension:
    """
    Wrapper for a single entry in the document catalog's
    ``/Extensions`` dictionary — a *developer extension* dictionary
    (PDF 32000-1 §7.12.2 / ISO 32000-2 §7.12.3).

    A developer extension declares that a particular vendor extension
    has been applied to the document. The value stored under the
    catalog's ``/Extensions`` is a dictionary keyed by a registered
    prefix (e.g. ``ADBE`` for Adobe), and each value is a developer
    extension dictionary with these entries:

    - ``/Type``           — must be ``DeveloperExtensions`` (optional but
                            recommended; this wrapper sets it on creation).
    - ``/BaseVersion``    — name; the base PDF version (e.g. ``1.7``)
                            that the extension is layered on top of.
    - ``/ExtensionLevel`` — integer; vendor-defined extension level.
    - ``/URL``            — string (PDF 2.0 / ISO 32000-2 §7.12.3); an
                            optional URL identifying the extension.

    Conceptually mirrors a ``PDDeveloperExtension`` wrapper as it
    would be defined in PDFBox. PDFBox 3.0 itself does not ship a
    typed wrapper — only the COSName constants ``BASE_VERSION``,
    ``EXTENSION_LEVEL``, and ``EXTENSIONS``. This class is a
    spec-driven helper provided by pypdfbox so callers don't have to
    poke at raw COS dictionaries when reading or writing developer
    extensions.
    """

    # Common registered prefix names for the catalog ``/Extensions``
    # dictionary. Spelled out as constants for parity with how callers
    # routinely identify the extension publisher.
    ADBE: str = "ADBE"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            dictionary = COSDictionary()
            dictionary.set_item(_TYPE, _DEVELOPER_EXTENSIONS)
        elif dictionary.get_dictionary_object(_TYPE) is None:
            # Match PDFBox-style wrappers: ensure ``/Type`` is present
            # for any freshly-wrapped dictionary that lacked it.
            dictionary.set_item(_TYPE, _DEVELOPER_EXTENSIONS)
        self._dictionary = dictionary

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    # Upstream alias: ``COSObjectable#getCOSObject`` is sometimes called
    # ``getCOSDictionary`` on dictionary-only wrappers.
    def get_cos_dictionary(self) -> COSDictionary:
        return self._dictionary

    # ---------- /BaseVersion ----------

    def get_base_version(self) -> str | None:
        """Return the ``/BaseVersion`` name as a plain string (e.g.
        ``"1.7"``), or ``None`` when absent."""
        return self._dictionary.get_name(_BASE_VERSION)

    def set_base_version(self, base_version: str | None) -> None:
        """Set the ``/BaseVersion`` PDF version. Pass ``None`` to remove."""
        if base_version is None:
            self._dictionary.remove_item(_BASE_VERSION)
            return
        self._dictionary.set_item(_BASE_VERSION, COSName.get_pdf_name(base_version))

    # ---------- /ExtensionLevel ----------

    def get_extension_level(self) -> int:
        """Return the ``/ExtensionLevel`` integer, or ``-1`` when absent
        (mirrors PDFBox's ``COSDictionary.getInt`` default)."""
        return self._dictionary.get_int(_EXTENSION_LEVEL)

    def set_extension_level(self, extension_level: int) -> None:
        """Set ``/ExtensionLevel``. PDFBox's overload takes a primitive
        ``int`` (no ``Integer`` boxing), so we accept ``int`` only."""
        self._dictionary.set_int(_EXTENSION_LEVEL, int(extension_level))

    # ---------- /URL (ISO 32000-2 / PDF 2.0) ----------

    def get_url(self) -> str | None:
        """Return the optional ``/URL`` string (ISO 32000-2 §7.12.3),
        or ``None`` when absent.

        Note: PDF 1.x did not define ``/URL`` on a developer extension
        dictionary; PDF 2.0 added it. PDFBox 3.0 has no typed accessor —
        pypdfbox surfaces it for forward compatibility."""
        return self._dictionary.get_string(_URL)

    def set_url(self, url: str | None) -> None:
        """Set the optional ``/URL`` string. Pass ``None`` to remove."""
        if url is None:
            self._dictionary.remove_item(_URL)
            return
        self._dictionary.set_item(_URL, COSString(url))

    def __repr__(self) -> str:
        return (
            f"PDDeveloperExtension(base_version={self.get_base_version()!r}, "
            f"extension_level={self.get_extension_level()!r})"
        )


__all__ = ["PDDeveloperExtension"]
