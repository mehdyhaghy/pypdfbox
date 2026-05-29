from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_REGISTRY: COSName = COSName.get_pdf_name("Registry")
_ORDERING: COSName = COSName.get_pdf_name("Ordering")
_SUPPLEMENT: COSName = COSName.get_pdf_name("Supplement")


class PDCIDSystemInfo:
    """Wraps a ``/CIDSystemInfo`` dictionary. Mirrors PDFBox ``PDCIDSystemInfo``.

    A ``CIDSystemInfo`` identifies the character collection of a CIDFont:
    ``/Registry`` (e.g. ``Adobe``), ``/Ordering`` (e.g. ``Japan1``), and
    integer ``/Supplement``.
    """

    # ---------- registry / ordering constants ----------
    #
    # Mirror the registry / ordering name strings used by Adobe's predefined
    # CIDSystemInfo collections (PDF 32000-1 §9.7.5.2 Table 118 plus
    # Adobe's "Predefined CMaps" technical note 5094). Surfaced as class
    # attributes so callers don't have to spell the strings literally —
    # parity with how upstream PDFBox callers compare against
    # ``COSName.ADOBE`` / ``"Identity"``.

    REGISTRY_ADOBE: str = "Adobe"

    ORDERING_IDENTITY: str = "Identity"
    ORDERING_GB1: str = "GB1"
    ORDERING_CNS1: str = "CNS1"
    ORDERING_JAPAN1: str = "Japan1"
    ORDERING_KOREA1: str = "Korea1"
    ORDERING_KR: str = "KR"

    def __init__(
        self,
        registry_or_dictionary: COSDictionary | str | None = None,
        ordering: str | None = None,
        supplement: int | None = None,
    ) -> None:
        """Construct from an existing dictionary or from
        ``(registry, ordering, supplement)`` parts.

        Mirrors both upstream constructors:

        * ``PDCIDSystemInfo(COSDictionary)`` — wrap an existing CIDSystemInfo
          dictionary (zero or one positional arg).
        * ``PDCIDSystemInfo(String registry, String ordering, int supplement)``
          — build a fresh dictionary from the three identifying values
          (Registry, Ordering, Supplement). Used by ``PDType0Font`` /
          ``PDCIDFontType2`` embedders that build a CIDFont dictionary
          from scratch.

        Passing no arguments yields an empty wrapper around a fresh
        ``COSDictionary`` — the original lite-surface signature.
        """
        if (
            isinstance(registry_or_dictionary, str)
            or ordering is not None
            or supplement is not None
        ):
            # Three-argument form. ``ordering`` and ``supplement`` are
            # required when ``registry_or_dictionary`` is a string;
            # surface a clear TypeError rather than silently defaulting.
            if not isinstance(registry_or_dictionary, str):
                raise TypeError(
                    "PDCIDSystemInfo(registry, ordering, supplement): "
                    "registry must be a str"
                )
            if ordering is None or supplement is None:
                raise TypeError(
                    "PDCIDSystemInfo(registry, ordering, supplement) "
                    "requires all three arguments"
                )
            self._dict = COSDictionary()
            self._dict.set_string(_REGISTRY, registry_or_dictionary)
            self._dict.set_string(_ORDERING, ordering)
            self._dict.set_int(_SUPPLEMENT, int(supplement))
            return
        # Single-argument (or no-argument) form: wrap an existing dict
        # or build an empty one.
        if registry_or_dictionary is None:
            self._dict = COSDictionary()
            return
        if isinstance(registry_or_dictionary, COSDictionary):
            self._dict = registry_or_dictionary
            return
        raise TypeError(
            "PDCIDSystemInfo() expects no argument, a COSDictionary, "
            "or (registry, ordering, supplement)"
        )

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Registry ----------

    def get_registry(self) -> str | None:
        # Upstream uses getNameAsString — accept COSName or COSString.
        return self._dict.get_name_as_string(_REGISTRY)

    def set_registry(self, registry: str | None) -> None:
        if registry is None:
            self._dict.remove_item(_REGISTRY)
            return
        self._dict.set_string(_REGISTRY, registry)

    # ---------- /Ordering ----------

    def get_ordering(self) -> str | None:
        # Upstream uses getNameAsString — accept COSName or COSString.
        return self._dict.get_name_as_string(_ORDERING)

    def set_ordering(self, ordering: str | None) -> None:
        if ordering is None:
            self._dict.remove_item(_ORDERING)
            return
        self._dict.set_string(_ORDERING, ordering)

    # ---------- /Supplement ----------

    def get_supplement(self) -> int:
        return self._dict.get_int(_SUPPLEMENT, 0)

    def set_supplement(self, supplement: int) -> None:
        self._dict.set_int(_SUPPLEMENT, int(supplement))

    # ---------- predicates ----------

    def is_identity(self) -> bool:
        """``True`` when this is the canonical Adobe ``Identity`` collection
        (``Registry=Adobe``, ``Ordering=Identity``).

        The Identity composition is the marker for a CIDFont whose CIDs
        equal glyph indices (no /CIDToGIDMap stream needed). pypdfbox
        extension over upstream — equivalent to manually checking
        ``getRegistry() == "Adobe" && getOrdering() == "Identity"`` and
        used by callers that branch on Identity-vs-predefined collections.
        """
        return (
            self.get_registry() == self.REGISTRY_ADOBE
            and self.get_ordering() == self.ORDERING_IDENTITY
        )

    def is_adobe(self) -> bool:
        """``True`` when ``/Registry`` is ``Adobe`` (the only registry
        whose CMaps PDFBox bundles via ``Adobe-*-UCS2`` predefined CMaps).
        """
        return self.get_registry() == self.REGISTRY_ADOBE

    def __str__(self) -> str:
        registry = self.get_registry()
        ordering = self.get_ordering()
        return (
            f"{registry if registry is not None else 'null'}-"
            f"{ordering if ordering is not None else 'null'}-"
            f"{self.get_supplement()}"
        )

    def to_string(self) -> str:
        """Mirror upstream ``PDCIDSystemInfo.toString()`` —
        ``"<registry>-<ordering>-<supplement>"``. Delegates to
        :meth:`__str__` so the two stay in lock-step; kept as an explicit
        method so callers porting Java code that calls ``info.toString()``
        get byte-identical output."""
        return str(self)

    # ---------- value-equality / hashing ----------

    def __eq__(self, other: object) -> bool:
        """Compare by ``(registry, ordering, supplement)`` triple.

        Two ``PDCIDSystemInfo`` objects backed by different ``COSDictionary``
        instances compare equal when their three identifying entries
        match. pypdfbox extension — upstream relies on dictionary
        identity, but value semantics are far more useful in tests and
        in callers that build CIDSystemInfo wrappers fresh from the
        three-arg constructor.
        """
        if not isinstance(other, PDCIDSystemInfo):
            return NotImplemented
        return (
            self.get_registry() == other.get_registry()
            and self.get_ordering() == other.get_ordering()
            and self.get_supplement() == other.get_supplement()
        )

    def __hash__(self) -> int:
        return hash(
            (self.get_registry(), self.get_ordering(), self.get_supplement())
        )


__all__ = ["PDCIDSystemInfo"]
