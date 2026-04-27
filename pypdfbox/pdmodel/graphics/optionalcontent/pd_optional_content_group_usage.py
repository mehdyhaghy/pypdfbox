"""Typed accessors for the OCG ``/Usage`` sub-dictionary.

PDF 32000-1 §8.11.4.4 Table 102 defines the optional ``/Usage`` entry of
an optional content group as a dictionary whose keys group usage hints
into typed sub-dictionaries (``CreatorInfo``, ``Language``, ``Export``,
``Zoom``, ``Print``, ``View``, ``User``, ``PageElement``).

Apache PDFBox does not provide a dedicated wrapper class for ``/Usage``
— it exposes the raw ``COSDictionary`` from ``PDOptionalContentGroup``
and lets callers reach into the typed sub-entries by hand. This module
provides a Pythonic typed wrapper layered on top of the existing
``PDOptionalContentGroup`` so callers do not have to manage
``COSName`` keys themselves. The class is original to pypdfbox and is
recorded as such in ``PROVENANCE.md``.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSFloat, COSName, COSNumber

_CREATOR_INFO: COSName = COSName.get_pdf_name("CreatorInfo")
_CREATOR: COSName = COSName.get_pdf_name("Creator")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")

_LANGUAGE: COSName = COSName.get_pdf_name("Language")
_LANG: COSName = COSName.get_pdf_name("Lang")
_PREFERRED: COSName = COSName.get_pdf_name("Preferred")

_EXPORT: COSName = COSName.get_pdf_name("Export")
_EXPORT_STATE: COSName = COSName.get_pdf_name("ExportState")

_ZOOM: COSName = COSName.get_pdf_name("Zoom")
_MIN: COSName = COSName.get_pdf_name("min")
_MAX: COSName = COSName.get_pdf_name("max")

_PRINT: COSName = COSName.get_pdf_name("Print")
_PRINT_STATE: COSName = COSName.get_pdf_name("PrintState")

_VIEW: COSName = COSName.get_pdf_name("View")
_VIEW_STATE: COSName = COSName.get_pdf_name("ViewState")

_USER: COSName = COSName.get_pdf_name("User")
_TYPE: COSName = COSName.get_pdf_name("Type")
_NAME: COSName = COSName.get_pdf_name("Name")

_PAGE_ELEMENT: COSName = COSName.get_pdf_name("PageElement")


def _read_name(sub: COSDictionary, key: COSName) -> str | None:
    """Read a ``/Name`` value from ``sub`` returning ``None`` when missing
    or not a ``COSName``. Used for state names like ``ON`` / ``OFF``."""
    value = sub.get_dictionary_object(key)
    if isinstance(value, COSName):
        return value.name
    return None


def _read_float(sub: COSDictionary, key: COSName) -> float | None:
    """Read a numeric value as ``float`` from ``sub``; ``None`` when
    missing or not a number."""
    value = sub.get_dictionary_object(key)
    if isinstance(value, COSNumber):
        return float(value.value)
    return None


# ---------------------------------------------------------------------------
# Sub-dictionary wrappers — each holds a reference to the live COSDictionary
# so writes round-trip through ``get_cos_object``. Read-side fields are
# resolved lazily from the dict so external mutation is observed.
# ---------------------------------------------------------------------------


class _UsageSubDict:
    """Base class for ``/Usage`` sub-dictionary wrappers."""

    def __init__(self, dictionary: COSDictionary) -> None:
        self._dict = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"{type(self).__name__}({self._dict!r})"


class PDUsageCreatorInfo(_UsageSubDict):
    """Wrapper for ``/Usage/CreatorInfo`` (PDF 32000-1 §8.11.4.4)."""

    @property
    def creator(self) -> str | None:
        return self._dict.get_string(_CREATOR)

    @creator.setter
    def creator(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_CREATOR)
        else:
            self._dict.set_string(_CREATOR, value)

    @property
    def subtype(self) -> str | None:
        return _read_name(self._dict, _SUBTYPE)

    @subtype.setter
    def subtype(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_SUBTYPE)
        else:
            self._dict.set_item(_SUBTYPE, COSName.get_pdf_name(value))


class PDUsageLanguage(_UsageSubDict):
    """Wrapper for ``/Usage/Language``."""

    @property
    def lang(self) -> str | None:
        return self._dict.get_string(_LANG)

    @lang.setter
    def lang(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_LANG)
        else:
            self._dict.set_string(_LANG, value)

    @property
    def preferred(self) -> str | None:
        # /Preferred is a name per Table 102 (allowed values: "ON", "OFF").
        return _read_name(self._dict, _PREFERRED)

    @preferred.setter
    def preferred(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_PREFERRED)
            return
        self._dict.set_item(_PREFERRED, COSName.get_pdf_name(value))


class PDUsageExport(_UsageSubDict):
    """Wrapper for ``/Usage/Export``."""

    @property
    def export_state(self) -> str | None:
        return _read_name(self._dict, _EXPORT_STATE)

    @export_state.setter
    def export_state(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_EXPORT_STATE)
            return
        upper = value.upper()
        if upper not in ("ON", "OFF"):
            raise ValueError(
                f"export_state must be 'ON' or 'OFF', got {value!r}"
            )
        self._dict.set_item(_EXPORT_STATE, COSName.get_pdf_name(upper))


class PDUsageZoom(_UsageSubDict):
    """Wrapper for ``/Usage/Zoom``.

    Per Table 102, /min defaults to 0 and /max defaults to +infinity when
    absent; we surface ``None`` for missing entries and let callers apply
    their own defaults rather than baking them in here.
    """

    @property
    def min(self) -> float | None:
        return _read_float(self._dict, _MIN)

    @min.setter
    def min(self, value: float | None) -> None:
        if value is None:
            self._dict.remove_item(_MIN)
        else:
            self._dict.set_item(_MIN, COSFloat(float(value)))

    @property
    def max(self) -> float | None:
        return _read_float(self._dict, _MAX)

    @max.setter
    def max(self, value: float | None) -> None:
        if value is None:
            self._dict.remove_item(_MAX)
        else:
            self._dict.set_item(_MAX, COSFloat(float(value)))


class PDUsagePrint(_UsageSubDict):
    """Wrapper for ``/Usage/Print``."""

    @property
    def subtype(self) -> str | None:
        return _read_name(self._dict, _SUBTYPE)

    @subtype.setter
    def subtype(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_SUBTYPE)
        else:
            self._dict.set_item(_SUBTYPE, COSName.get_pdf_name(value))

    @property
    def print_state(self) -> str | None:
        return _read_name(self._dict, _PRINT_STATE)

    @print_state.setter
    def print_state(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_PRINT_STATE)
            return
        upper = value.upper()
        if upper not in ("ON", "OFF"):
            raise ValueError(
                f"print_state must be 'ON' or 'OFF', got {value!r}"
            )
        self._dict.set_item(_PRINT_STATE, COSName.get_pdf_name(upper))


class PDUsageView(_UsageSubDict):
    """Wrapper for ``/Usage/View``."""

    @property
    def view_state(self) -> str | None:
        return _read_name(self._dict, _VIEW_STATE)

    @view_state.setter
    def view_state(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_VIEW_STATE)
            return
        upper = value.upper()
        if upper not in ("ON", "OFF"):
            raise ValueError(
                f"view_state must be 'ON' or 'OFF', got {value!r}"
            )
        self._dict.set_item(_VIEW_STATE, COSName.get_pdf_name(upper))


class PDUsageUser(_UsageSubDict):
    """Wrapper for ``/Usage/User``."""

    @property
    def type(self) -> str | None:
        # /Type is a name (Ind/Ttl/Org).
        return _read_name(self._dict, _TYPE)

    @type.setter
    def type(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_TYPE)
        else:
            self._dict.set_item(_TYPE, COSName.get_pdf_name(value))

    @property
    def name(self) -> str | None:
        # /Name is a text string or array of text strings; return the
        # first when an array is present.
        from pypdfbox.cos import COSArray

        value = self._dict.get_dictionary_object(_NAME)
        if isinstance(value, COSArray):
            for entry in value:
                if hasattr(entry, "get_string"):
                    s = entry.get_string()  # type: ignore[no-untyped-call]
                    if isinstance(s, str):
                        return s
            return None
        return self._dict.get_string(_NAME)

    @name.setter
    def name(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_NAME)
        else:
            self._dict.set_string(_NAME, value)


class PDUsagePageElement(_UsageSubDict):
    """Wrapper for ``/Usage/PageElement``."""

    @property
    def subtype(self) -> str | None:
        return _read_name(self._dict, _SUBTYPE)

    @subtype.setter
    def subtype(self, value: str | None) -> None:
        if value is None:
            self._dict.remove_item(_SUBTYPE)
        else:
            self._dict.set_item(_SUBTYPE, COSName.get_pdf_name(value))


# ---------------------------------------------------------------------------
# Top-level /Usage wrapper
# ---------------------------------------------------------------------------


class PDOptionalContentGroupUsage:
    """Typed wrapper for an OCG ``/Usage`` dictionary.

    This class is original to pypdfbox — Apache PDFBox exposes the raw
    ``COSDictionary`` rather than a dedicated wrapper. Constructing
    against an existing ``COSDictionary`` aliases (does not copy) so
    writes round-trip through the underlying OCG.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---- shared sub-dict helpers ----

    def _sub(self, key: COSName) -> COSDictionary | None:
        value = self._dict.get_dictionary_object(key)
        return value if isinstance(value, COSDictionary) else None

    def _sub_or_create(self, key: COSName) -> COSDictionary:
        existing = self._sub(key)
        if existing is not None:
            return existing
        created = COSDictionary()
        self._dict.set_item(key, created)
        return created

    # ---- typed sub-accessors (read returns wrapper or None) ----

    def get_creator_info(self) -> PDUsageCreatorInfo | None:
        sub = self._sub(_CREATOR_INFO)
        return PDUsageCreatorInfo(sub) if sub is not None else None

    def get_or_create_creator_info(self) -> PDUsageCreatorInfo:
        return PDUsageCreatorInfo(self._sub_or_create(_CREATOR_INFO))

    def get_language(self) -> PDUsageLanguage | None:
        sub = self._sub(_LANGUAGE)
        return PDUsageLanguage(sub) if sub is not None else None

    def get_or_create_language(self) -> PDUsageLanguage:
        return PDUsageLanguage(self._sub_or_create(_LANGUAGE))

    def get_export(self) -> PDUsageExport | None:
        sub = self._sub(_EXPORT)
        return PDUsageExport(sub) if sub is not None else None

    def get_or_create_export(self) -> PDUsageExport:
        return PDUsageExport(self._sub_or_create(_EXPORT))

    def get_zoom(self) -> PDUsageZoom | None:
        sub = self._sub(_ZOOM)
        return PDUsageZoom(sub) if sub is not None else None

    def get_or_create_zoom(self) -> PDUsageZoom:
        return PDUsageZoom(self._sub_or_create(_ZOOM))

    def get_print(self) -> PDUsagePrint | None:
        sub = self._sub(_PRINT)
        return PDUsagePrint(sub) if sub is not None else None

    def get_or_create_print(self) -> PDUsagePrint:
        return PDUsagePrint(self._sub_or_create(_PRINT))

    def get_view(self) -> PDUsageView | None:
        sub = self._sub(_VIEW)
        return PDUsageView(sub) if sub is not None else None

    def get_or_create_view(self) -> PDUsageView:
        return PDUsageView(self._sub_or_create(_VIEW))

    def get_user(self) -> PDUsageUser | None:
        sub = self._sub(_USER)
        return PDUsageUser(sub) if sub is not None else None

    def get_or_create_user(self) -> PDUsageUser:
        return PDUsageUser(self._sub_or_create(_USER))

    def get_page_element(self) -> PDUsagePageElement | None:
        sub = self._sub(_PAGE_ELEMENT)
        return PDUsagePageElement(sub) if sub is not None else None

    def get_or_create_page_element(self) -> PDUsagePageElement:
        return PDUsagePageElement(self._sub_or_create(_PAGE_ELEMENT))

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"PDOptionalContentGroupUsage({self._dict!r})"


__all__ = [
    "PDOptionalContentGroupUsage",
    "PDUsageCreatorInfo",
    "PDUsageExport",
    "PDUsageLanguage",
    "PDUsagePageElement",
    "PDUsagePrint",
    "PDUsageUser",
    "PDUsageView",
    "PDUsageZoom",
]
