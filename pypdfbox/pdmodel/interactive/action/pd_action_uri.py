from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString

from .pd_action import PDAction

_URI: COSName = COSName.get_pdf_name("URI")
_IS_MAP: COSName = COSName.get_pdf_name("IsMap")


class PDActionURI(PDAction):
    """URI action. Mirrors PDFBox ``PDActionURI``."""

    SUB_TYPE = "URI"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_uri(self) -> str | None:
        """Return ``/URI`` decoded per upstream ``PDActionURI.getURI``: UTF-16
        when a BOM is present, otherwise UTF-8 (not PDFDocEncoding). Returns
        ``None`` when the entry is absent or not a ``COSString``.

        PDF 32000-1 §12.6.4.7 specifies the entry should be 7-bit ASCII;
        upstream additionally tolerates UTF-8 / UTF-16 since real-world
        producers stray from the spec."""
        base = self._action.get_dictionary_object(_URI)
        if not isinstance(base, COSString):
            return None
        raw = base.get_bytes()
        if len(raw) >= 2:
            b0, b1 = raw[0], raw[1]
            # UTF-16 BE / LE BOM — defer to COSString.get_string() which
            # already strips the BOM and decodes accordingly.
            if (b0 == 0xFE and b1 == 0xFF) or (b0 == 0xFF and b1 == 0xFE):
                return base.get_string()
        return raw.decode("utf-8", errors="replace")

    def set_uri(self, uri: str | None) -> None:
        self._action.set_string(_URI, uri)

    def should_track_mouse_position(self) -> bool:
        return self._action.get_boolean(_IS_MAP, False)

    def set_track_mouse_position(self, value: bool) -> None:
        self._action.set_boolean(_IS_MAP, value)

    # Aliases mirroring the raw PDF dictionary entry name (`/IsMap`).
    def get_is_map(self) -> bool:
        """Return ``/IsMap``. Defaults to ``False`` when absent. Synonym of
        :meth:`should_track_mouse_position` matching the dictionary key
        name verbatim."""
        return self._action.get_boolean(_IS_MAP, False)

    def set_is_map(self, value: bool) -> None:
        """Set ``/IsMap``. Synonym of :meth:`set_track_mouse_position`."""
        self._action.set_boolean(_IS_MAP, value)

    # Predicate accessors — useful for callers that need to distinguish
    # "absent" from "explicitly empty" without re-fetching the entry.
    def has_uri(self) -> bool:
        """Return ``True`` iff a ``/URI`` entry is present (regardless of
        whether it decodes to an empty string)."""
        return self._action.contains_key(_URI)

    def has_is_map(self) -> bool:
        """Return ``True`` iff an explicit ``/IsMap`` entry is present.
        Useful for distinguishing the spec default from an explicit
        ``false``."""
        return self._action.contains_key(_IS_MAP)

    # Typed COS-level accessor for the raw ``/URI`` entry. Lets callers
    # inspect the underlying bytes / encoding without going through the
    # tolerant decode in :meth:`get_uri`.
    def get_uri_as_cos_string(self) -> COSString | None:
        """Return the raw ``/URI`` :class:`COSString`, or ``None`` when
        the entry is absent or not a ``COSString``."""
        base = self._action.get_dictionary_object(_URI)
        if isinstance(base, COSString):
            return base
        return None

    # ---------- explicit clear helpers ----------

    def clear_uri(self) -> None:
        """Remove ``/URI``. Equivalent to ``set_uri(None)`` but reads as a
        named intent at call sites; matches the ``clear_flags`` /
        ``clear_*`` pattern used by sibling action wrappers
        (e.g. :class:`PDActionSubmitForm.clear_flags`)."""
        self._action.remove_item(_URI)

    def clear_is_map(self) -> None:
        """Remove ``/IsMap``. After this call :meth:`has_is_map` reports
        ``False`` and :meth:`get_is_map` falls back to the spec default of
        ``False`` (PDF 32000-1 §12.6.4.7 Table 206). Distinct from
        :meth:`set_is_map(False)` which explicitly stamps a ``COSBoolean``
        ``false`` on the dictionary — useful for callers that want to
        return the entry to the implicit-default state."""
        self._action.remove_item(_IS_MAP)

    def clear_track_mouse_position(self) -> None:
        """Remove ``/IsMap`` using the track-mouse-position naming used by
        :meth:`should_track_mouse_position` and
        :meth:`set_track_mouse_position`.

        Synonym of :meth:`clear_is_map`.
        """
        self.clear_is_map()

    # ---------- URI emptiness / scheme predicates ----------

    def is_empty(self) -> bool:
        """Return ``True`` when ``/URI`` is absent or decodes to an empty
        string. Treats both states as semantically empty for the common
        case of a viewer that needs to skip activation when no actual
        target is set; use :meth:`has_uri` to distinguish them."""
        uri = self.get_uri()
        return uri is None or uri == ""

    def get_scheme(self) -> str | None:
        """Return the URI scheme (lower-cased per RFC 3986 §3.1) parsed
        from the raw decoded ``/URI`` value, or ``None`` when the entry
        is absent, empty, or has no ``":"`` separator (e.g. a relative
        reference like ``"page2.pdf"``).

        Mirrors the lightweight scheme-only parsing in :func:`urllib.parse.urlparse`
        (``urlparse(uri).scheme.lower() or None``) without paying for the
        rest of the URL split."""
        uri = self.get_uri()
        if uri is None or uri == "":
            return None
        # Per RFC 3986 §3.1: scheme is ALPHA *(ALPHA / DIGIT / "+" / "-" / ".")
        # then ":". A leading non-alpha character means the value isn't a
        # spec scheme — treat as relative.
        sep = uri.find(":")
        if sep <= 0:
            return None
        prefix = uri[:sep]
        if not prefix[0].isalpha():
            return None
        for ch in prefix[1:]:
            if not (ch.isalnum() or ch in "+-."):
                return None
        return prefix.lower()

    def is_http(self) -> bool:
        """Return ``True`` when ``/URI`` starts with the ``http:`` scheme
        (case-insensitive). Convenience over :meth:`get_scheme` for the
        very common HTTP-link case."""
        return self.get_scheme() == "http"

    def is_https(self) -> bool:
        """Return ``True`` when ``/URI`` starts with the ``https:`` scheme
        (case-insensitive)."""
        return self.get_scheme() == "https"

    def is_mailto(self) -> bool:
        """Return ``True`` when ``/URI`` starts with the ``mailto:`` scheme
        (case-insensitive). PDF 32000-1 §12.6.4.7 explicitly calls out
        ``mailto:`` as a valid URI form for email-link actions."""
        return self.get_scheme() == "mailto"

    def is_relative(self) -> bool:
        """Return ``True`` when ``/URI`` is present, non-empty, and lacks
        a scheme (e.g. ``"chapter2.pdf"`` or ``"#anchor"``). Returns
        ``False`` for absent or empty values — use :meth:`is_empty` to
        cover those cases."""
        uri = self.get_uri()
        if uri is None or uri == "":
            return False
        return self.get_scheme() is None


__all__ = ["PDActionURI"]
