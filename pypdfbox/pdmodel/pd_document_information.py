from __future__ import annotations

import datetime as _dt
from collections.abc import Iterator

from pypdfbox.cos import COSDictionary, COSName, COSString

# PDF info dictionary keys (PDF 32000-1:2008 §14.3.3, Table 317).
_TITLE: COSName = COSName.get_pdf_name("Title")
_AUTHOR: COSName = COSName.get_pdf_name("Author")
_SUBJECT: COSName = COSName.get_pdf_name("Subject")
_KEYWORDS: COSName = COSName.get_pdf_name("Keywords")
_CREATOR: COSName = COSName.get_pdf_name("Creator")
_PRODUCER: COSName = COSName.get_pdf_name("Producer")
_CREATION_DATE: COSName = COSName.get_pdf_name("CreationDate")
_MOD_DATE: COSName = COSName.get_pdf_name("ModDate")
_TRAPPED: COSName = COSName.get_pdf_name("Trapped")


#: PDF spec value for /Trapped meaning the document has been fully
#: pre-trapped before printing (PDF 32000-1:2008 §14.11.6).
TRAPPED_TRUE: str = "True"

#: PDF spec value for /Trapped meaning the document has not been trapped.
TRAPPED_FALSE: str = "False"

#: PDF spec value for /Trapped meaning trapping state is unknown — also
#: the implicit default when /Trapped is absent.
TRAPPED_UNKNOWN: str = "Unknown"


_VALID_TRAPPED = frozenset({TRAPPED_TRUE, TRAPPED_FALSE, TRAPPED_UNKNOWN})


# Standard /Info dictionary keys per PDF 32000-1:2008 §14.3.3, Table 317.
# Anything else found in the dictionary is considered "custom metadata".
_STANDARD_KEYS: frozenset[str] = frozenset(
    {
        "Title",
        "Author",
        "Subject",
        "Keywords",
        "Creator",
        "Producer",
        "CreationDate",
        "ModDate",
        "Trapped",
    }
)


def _parse_pdf_date(value: str) -> _dt.datetime | None:
    """Parse a PDF date string the way ``COSDictionary.getDate`` does.

    Thin delegate to the canonical COS-layer parser
    (:func:`pypdfbox.cos.cos_dictionary._parse_pdf_date`, itself a 1:1 delegate
    to the oracle-pinned ``DateConverter.toCalendar`` port) so every PDF-date
    read goes through one faithful implementation. Retained as a module-level
    symbol because ``PDSignature`` / ``PDFormXObject`` import it from here.

    Earlier this module carried its own narrower ``_PDF_DATE_RE`` regex that
    handled only the ``D:YYYYMMDD…`` subset and clamped a ``60``-second value
    to ``59``; that diverged from upstream (which accepts the broader
    DateConverter shape and rejects a 60-second value with ``null``). Folded
    into the COS delegate in wave 1516.
    """
    from pypdfbox.cos.cos_dictionary import _parse_pdf_date as _cos_parse

    return _cos_parse(value)


def _anchor_naive(date: _dt.datetime | None) -> _dt.datetime | None:
    """Anchor a naive (tz-less) ``datetime`` to UTC.

    A naive datetime has no ``java.util.Calendar`` equivalent (a Calendar
    always carries a zone). Anchoring to UTC makes the offset render as
    ``+00'00'`` — matching upstream's GMT default rather than omitting the
    zone, which is what the bare COS-layer formatter would do for naive input.
    """
    if date is not None and (date.tzinfo is None or date.utcoffset() is None):
        return date.replace(tzinfo=_dt.UTC)
    return date


def _format_pdf_date(value: _dt.datetime) -> str:
    """Format a ``datetime`` as a PDF date string (``D:YYYYMMDDHHmmSSOHH'mm'``).

    Thin delegate to the canonical COS-layer formatter
    (:func:`pypdfbox.cos.cos_dictionary._format_pdf_date`) so every PDF-date
    write goes through one implementation. Retained as a module-level symbol
    because ``PDEmbeddedFile`` / ``PDSignature`` / ``PDAnnotation`` /
    ``PDFormXObject`` import it from here to share the exact formatting (zero
    offset renders ``+00'00'``, never ``Z`` — DateConverter.toString); a naive
    datetime is anchored to UTC first.
    """
    from pypdfbox.cos.cos_dictionary import _format_pdf_date as _cos_format

    return _cos_format(_anchor_naive(value)) or ""


def _get_info_string(info: COSDictionary, key: COSName | str) -> str | None:
    """Return a metadata string only when the COS value is a real string."""
    value = info.get_dictionary_object(key)
    if isinstance(value, COSString):
        return value.get_string()
    return None


class PDDocumentInformation:
    """
    Wrapper around the trailer's ``/Info`` dictionary. Mirrors
    ``org.apache.pdfbox.pdmodel.PDDocumentInformation``.

    Each ``get_*`` accessor returns ``None`` if the entry is absent or
    malformed for that field; each ``set_*`` accessor with a ``None`` argument
    clears the entry. The ``has_*`` helpers report key presence only, so a
    malformed present entry may still have a ``None`` typed accessor value.
    """

    #: Names defined for the standard /Info dictionary keys per PDF 32000-1:2008
    #: §14.3.3, Table 317. Anything else stored on the dictionary is treated as
    #: custom metadata.
    STANDARD_KEYS: frozenset[str] = _STANDARD_KEYS

    #: PDF spec values for /Trapped (PDF 32000-1:2008 §14.11.6). Exposed at
    #: class level so callers can write
    #: ``info.set_trapped(PDDocumentInformation.TRAPPED_TRUE)`` without having
    #: to import the module-level constants.
    TRAPPED_TRUE: str = TRAPPED_TRUE
    TRAPPED_FALSE: str = TRAPPED_FALSE
    TRAPPED_UNKNOWN: str = TRAPPED_UNKNOWN

    def __init__(self, info: COSDictionary | None = None) -> None:
        self._info = info if info is not None else COSDictionary()

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._info

    # ---------- low-level passthrough ----------

    def get_property_string_value(self, property_key: str) -> str | None:
        """Return the raw string at ``property_key`` (no type coercion).

        Allows callers to pull date strings unparsed for validation.
        """
        return _get_info_string(self._info, property_key)

    def set_property_string_value(
        self, property_key: str, property_value: str | bytes | None
    ) -> None:
        """Set the raw string at ``property_key``.

        Mirrors the upstream ``setPropertyStringValue`` helper. Passing
        ``None`` removes the entry, matching the standard-field setters.
        """
        self._info.set_string(property_key, property_value)

    # ---------- standard fields ----------

    def get_title(self) -> str | None:
        return _get_info_string(self._info, _TITLE)

    def set_title(self, title: str | None) -> None:
        self._info.set_string(_TITLE, title)

    def get_author(self) -> str | None:
        return _get_info_string(self._info, _AUTHOR)

    def set_author(self, author: str | None) -> None:
        self._info.set_string(_AUTHOR, author)

    def get_subject(self) -> str | None:
        return _get_info_string(self._info, _SUBJECT)

    def set_subject(self, subject: str | None) -> None:
        self._info.set_string(_SUBJECT, subject)

    def get_keywords(self) -> str | None:
        return _get_info_string(self._info, _KEYWORDS)

    def set_keywords(self, keywords: str | None) -> None:
        self._info.set_string(_KEYWORDS, keywords)

    def get_creator(self) -> str | None:
        return _get_info_string(self._info, _CREATOR)

    def set_creator(self, creator: str | None) -> None:
        self._info.set_string(_CREATOR, creator)

    def get_producer(self) -> str | None:
        return _get_info_string(self._info, _PRODUCER)

    def set_producer(self, producer: str | None) -> None:
        self._info.set_string(_PRODUCER, producer)

    # ---------- dates ----------

    def get_creation_date(self) -> _dt.datetime | None:
        # Upstream ``getCreationDate`` delegates straight to
        # ``COSDictionary.getDate`` (which itself routes through the faithful
        # DateConverter port). Delegating here keeps the Info-dict date
        # leniency identical to the COS layer rather than carrying a separate,
        # narrower regex copy.
        return self._info.get_date(_CREATION_DATE)

    def set_creation_date(self, date: _dt.datetime | None) -> None:
        self._info.set_date(_CREATION_DATE, _anchor_naive(date))

    def get_modification_date(self) -> _dt.datetime | None:
        return self._info.get_date(_MOD_DATE)

    def set_modification_date(self, date: _dt.datetime | None) -> None:
        self._info.set_date(_MOD_DATE, _anchor_naive(date))

    # ---------- trapped ----------

    def get_trapped(self) -> str | None:
        # Mirrors upstream ``getNameAsString`` semantics: real-world PDFs
        # occasionally store /Trapped as a COSString instead of the
        # spec-mandated COSName. Accept both so we don't surprise readers
        # with ``None`` for files Java PDFBox happily reads.
        v = self._info.get_dictionary_object(_TRAPPED)
        if isinstance(v, COSName):
            return v.name
        if isinstance(v, COSString):
            return v.get_string()
        return None

    def set_trapped(self, value: str | None) -> None:
        if value is not None and value not in _VALID_TRAPPED:
            raise ValueError(
                "Valid values for trapped are 'True', 'False', or 'Unknown'"
            )
        if value is None:
            self._info.remove_item(_TRAPPED)
        else:
            self._info.set_name(_TRAPPED, value)

    def is_trapped(self) -> bool | None:
        """Return ``True`` / ``False`` for /Trapped, ``None`` otherwise.

        Pypdfbox addition. Maps the spec values ``True``/``False`` to native
        booleans for callers that just want a tri-state answer:

        * ``True``     → trapping was performed
        * ``False``    → trapping was *not* performed
        * ``Unknown``  → ``None`` (matches the spec's "not known" semantic)
        * absent / unexpected types → ``None``
        """
        v = self.get_trapped()
        if v == TRAPPED_TRUE:
            return True
        if v == TRAPPED_FALSE:
            return False
        return None

    def set_trapped_bool(self, value: bool | None) -> None:
        """Set /Trapped from a tri-state ``bool | None``.

        Pypdfbox addition — the inverse of :meth:`is_trapped`. Converts a
        Python tri-state into the spec's name values so callers can pipe a
        boolean predicate straight back into the info dictionary:

        * ``True``  → /Trapped = ``True``
        * ``False`` → /Trapped = ``False``
        * ``None``  → /Trapped = ``Unknown`` (matches the spec's
          "not known" semantic; symmetric with :meth:`is_trapped` round-trip)
        """
        if value is True:
            self.set_trapped(TRAPPED_TRUE)
        elif value is False:
            self.set_trapped(TRAPPED_FALSE)
        else:
            self.set_trapped(TRAPPED_UNKNOWN)

    def set_trapped_true(self) -> None:
        """Convenience setter — equivalent to ``set_trapped("True")``.

        Pypdfbox addition. Lets callers express trap-state without spelling
        out the spec literal."""
        self.set_trapped(TRAPPED_TRUE)

    def set_trapped_false(self) -> None:
        """Convenience setter — equivalent to ``set_trapped("False")``.

        Pypdfbox addition."""
        self.set_trapped(TRAPPED_FALSE)

    def set_trapped_unknown(self) -> None:
        """Convenience setter — equivalent to ``set_trapped("Unknown")``.

        Pypdfbox addition."""
        self.set_trapped(TRAPPED_UNKNOWN)

    # ---------- custom metadata ----------

    def get_metadata_keys(self) -> list[str]:
        """Return all metadata key names present in the info dictionary, in
        sorted order (upstream returns ``TreeSet`` — sorted ``list`` matches
        the documented ordering and stays stable for callers that iterate)."""
        return sorted(key.get_name() for key in self._info.key_set())

    def get_metadata_keys_set(self) -> set[str]:
        """Return all metadata key names as a ``set``. Mirrors the upstream
        ``Set<String> getMetadataKeys()`` contract for callers that want
        membership-test semantics rather than the sorted list. The two
        accessors share underlying state — order is the only difference."""
        return {key.get_name() for key in self._info.key_set()}

    def contains_property(self, property_key: str) -> bool:
        """Return ``True`` when ``property_key`` is present in the underlying
        info dictionary. A convenience over inspecting
        ``get_metadata_keys()`` for a one-off membership check."""
        return self._info.contains_key(property_key)

    def has_property(self, property_key: str) -> bool:
        """Return ``True`` when ``property_key`` is present in the info dictionary."""
        return self.contains_property(property_key)

    def get_custom_metadata_value(self, field_name: str) -> str | None:
        return _get_info_string(self._info, field_name)

    def set_custom_metadata_value(
        self, field_name: str, field_value: str | None
    ) -> None:
        self._info.set_string(field_name, field_value)

    def has_custom_metadata_value(self, field_name: str) -> bool:
        """Return ``True`` when ``field_name`` is present in the info dictionary."""
        return self._info.contains_key(field_name)

    def clear_custom_metadata_value(self, field_name: str) -> None:
        """Remove ``field_name`` from the info dictionary. No-op if absent."""
        self._info.remove_item(field_name)

    def clear_property(self, property_key: str) -> None:
        """Remove ``property_key`` from the info dictionary. No-op if absent."""
        self._info.remove_item(property_key)

    def get_standard_metadata_keys(self) -> list[str]:
        """Return only the *standard* metadata keys (per PDF 32000-1:2008
        §14.3.3) that are actually present in the info dictionary, in
        sorted order.

        Pypdfbox addition — the inverse of :meth:`get_custom_metadata_keys`.
        Useful for callers iterating only the spec-defined fields.
        """
        return sorted(
            key.get_name()
            for key in self._info.key_set()
            if key.get_name() in _STANDARD_KEYS
        )

    def get_custom_metadata_keys(self) -> list[str]:
        """Return only the *non-standard* metadata keys present in the info
        dictionary, in sorted order. Filters out keys defined by PDF
        32000-1:2008 §14.3.3 (``Title``, ``Author``, ..., ``Trapped``).

        Pypdfbox addition — upstream PDFBox returns *all* keys via
        ``getMetadataKeys()``; this convenience layers on top of the same
        underlying state for callers iterating only custom fields.
        """
        return sorted(
            key.get_name()
            for key in self._info.key_set()
            if key.get_name() not in _STANDARD_KEYS
        )

    # ---------- predicates ----------

    def has_title(self) -> bool:
        """Return ``True`` when /Title is present in the info dictionary."""
        return self._info.contains_key(_TITLE)

    def has_author(self) -> bool:
        """Return ``True`` when /Author is present in the info dictionary."""
        return self._info.contains_key(_AUTHOR)

    def has_subject(self) -> bool:
        """Return ``True`` when /Subject is present in the info dictionary."""
        return self._info.contains_key(_SUBJECT)

    def has_keywords(self) -> bool:
        """Return ``True`` when /Keywords is present in the info dictionary."""
        return self._info.contains_key(_KEYWORDS)

    def has_creator(self) -> bool:
        """Return ``True`` when /Creator is present in the info dictionary."""
        return self._info.contains_key(_CREATOR)

    def has_producer(self) -> bool:
        """Return ``True`` when /Producer is present in the info dictionary."""
        return self._info.contains_key(_PRODUCER)

    def has_creation_date(self) -> bool:
        """Return ``True`` when /CreationDate is present in the info dictionary."""
        return self._info.contains_key(_CREATION_DATE)

    def has_modification_date(self) -> bool:
        """Return ``True`` when /ModDate is present in the info dictionary."""
        return self._info.contains_key(_MOD_DATE)

    def has_trapped(self) -> bool:
        """Return ``True`` when /Trapped is present in the info dictionary."""
        return self._info.contains_key(_TRAPPED)

    # ---------- clear_* helpers ----------
    # Explicit one-call removers for each standard /Info entry. Equivalent
    # to ``set_<field>(None)``; provided as named methods so call-sites that
    # just want to drop an entry read more naturally and don't have to
    # spell out the ``None`` argument. pypdfbox addition — Apache PDFBox 3.0
    # leaves callers to spell ``setTitle(null)``.

    def clear_title(self) -> None:
        """Remove ``/Title`` from the info dictionary. No-op if absent."""
        self._info.remove_item(_TITLE)

    def clear_author(self) -> None:
        """Remove ``/Author`` from the info dictionary. No-op if absent."""
        self._info.remove_item(_AUTHOR)

    def clear_subject(self) -> None:
        """Remove ``/Subject`` from the info dictionary. No-op if absent."""
        self._info.remove_item(_SUBJECT)

    def clear_keywords(self) -> None:
        """Remove ``/Keywords`` from the info dictionary. No-op if absent."""
        self._info.remove_item(_KEYWORDS)

    def clear_creator(self) -> None:
        """Remove ``/Creator`` from the info dictionary. No-op if absent."""
        self._info.remove_item(_CREATOR)

    def clear_producer(self) -> None:
        """Remove ``/Producer`` from the info dictionary. No-op if absent."""
        self._info.remove_item(_PRODUCER)

    def clear_creation_date(self) -> None:
        """Remove ``/CreationDate`` from the info dictionary. No-op if absent."""
        self._info.remove_item(_CREATION_DATE)

    def clear_modification_date(self) -> None:
        """Remove ``/ModDate`` from the info dictionary. No-op if absent."""
        self._info.remove_item(_MOD_DATE)

    def clear_trapped(self) -> None:
        """Remove ``/Trapped`` from the info dictionary. No-op if absent."""
        self._info.remove_item(_TRAPPED)

    # ---------- bulk operations ----------

    def clear(self) -> None:
        """Remove all entries from the underlying info dictionary.

        Pypdfbox addition — convenience over ``get_cos_object().clear()``.
        Leaves the wrapper attached to the same dictionary instance so any
        prior reference (e.g. on the document trailer) remains valid.
        """
        self._info.clear()

    def copy_from(self, other: PDDocumentInformation) -> None:
        """Copy every entry from ``other`` into this info dictionary,
        overwriting any colliding keys but leaving non-colliding existing
        entries intact.

        Pypdfbox addition — mirrors ``Map.putAll`` semantics on top of
        :meth:`COSDictionary.add_all`. Useful when stamping fresh metadata
        onto an existing document without dropping unrelated custom keys.
        """
        self._info.add_all(other.get_cos_object())

    # ---------- introspection ----------

    def is_empty(self) -> bool:
        """Return ``True`` if the underlying info dictionary holds no entries."""
        return self._info.is_empty()

    def is_pristine(self) -> bool:
        """Return ``True`` when the info dictionary either holds no entries
        at all or only carries the writer-supplied ``/Producer`` field.

        Pypdfbox addition — many PDF producers (including pypdfbox itself
        and Apache PDFBox) stamp ``/Producer`` automatically when a fresh
        document is saved, so the strict :meth:`is_empty` check rejects
        documents callers would intuitively classify as "no metadata
        supplied". This predicate reports ``True`` for both the truly
        empty info dict and the ``/Producer``-only shape, letting callers
        gate "metadata was supplied" decisions without manual key
        inspection.
        """
        keys = self._info.key_set()
        if not keys:
            return True
        return all(key.get_name() == "Producer" for key in keys)

    def __len__(self) -> int:
        return self._info.size()

    def __iter__(self) -> Iterator[str]:
        """Iterate metadata key names in sorted order.

        Pypdfbox addition — pairs with :meth:`__len__` and :meth:`__contains__`
        so callers can treat the wrapper as a read-only mapping of metadata
        keys::

            for key in info:
                print(key, info.get_property_string_value(key))
        """
        return iter(self.get_metadata_keys())

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, (str, COSName)):
            return False
        return self._info.contains_key(key)

    def to_dict(self) -> dict[str, str]:
        """Return a snapshot of every string-valued entry as a plain ``dict``.

        Pypdfbox addition — useful for logging / serialization. Only entries
        whose value coerces to text via
        :meth:`COSDictionary.get_name_as_string` (i.e. ``COSString`` and
        ``COSName`` values) appear; entries holding non-string types
        (numbers, arrays, etc.) are skipped rather than stringified. The
        returned dict is a copy, not a live view — mutating it does not
        affect the underlying info dict.
        """
        out: dict[str, str] = {}
        for key in self._info.key_set():
            name = key.get_name()
            value = self._info.get_name_as_string(name)
            if value is not None:
                out[name] = value
        return out

    def __repr__(self) -> str:
        return (
            f"PDDocumentInformation(title={self.get_title()!r}, "
            f"author={self.get_author()!r})"
        )


__all__ = [
    "PDDocumentInformation",
    "TRAPPED_TRUE",
    "TRAPPED_FALSE",
    "TRAPPED_UNKNOWN",
]
