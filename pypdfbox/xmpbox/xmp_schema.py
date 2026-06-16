from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .type.abstract_simple_property import AbstractSimpleProperty
from .type.array_property import ArrayProperty

if TYPE_CHECKING:
    from .type.boolean_type import BooleanType
    from .type.date_type import DateType
    from .type.integer_type import IntegerType
    from .type.text_type import TextType
    from .xmp_metadata import XMPMetadata


class BadFieldValueException(ValueError):
    """
    Mirror of upstream ``org.apache.xmpbox.type.BadFieldValueException``.

    Raised by typed-property accessors when the property at a requested name
    exists but is stored with a different XMP type than the caller asked for.
    Subclasses :class:`ValueError` so callers that aren't aware of the upstream
    class can still catch it idiomatically. Re-exported under the same name as
    the type-package class via :mod:`pypdfbox.xmpbox`.
    """


# Sentinel value used to distinguish "no language" from an explicit "x-default".
X_DEFAULT = "x-default"


class XMPSchema:
    """
    Base for all XMP schema representations. Ported (subset) from
    ``org.apache.xmpbox.schema.XMPSchema``.

    Cluster #1 stores property values directly as Python primitives:

      * simple TextType values  -> ``str``
      * Bag / Seq array values  -> ``list[str]``
      * LangAlt values          -> ``dict[str, str]`` keyed by language code,
                                   with the upstream ``"x-default"`` sentinel
                                   used when no explicit language is supplied.

    Later waves add typed ``AbstractField`` / ``ArrayProperty`` / ``TextType``
    wrappers. This base class still accepts primitive storage for parsed packets,
    but exposes upstream-named hooks such as ``add_property`` for typed callers.
    """

    # Subclasses should set these to mirror upstream's @StructuredType
    # annotations (preferedPrefix / namespace).
    NAMESPACE: str = ""
    PREFERRED_PREFIX: str = ""

    def __init__(
        self,
        metadata: XMPMetadata,
        namespace_uri: str | None = None,
        prefix: str | None = None,
        name: str | None = None,
    ) -> None:
        self._metadata = metadata
        self._namespace = namespace_uri or self.NAMESPACE
        self._prefix = prefix or self.PREFERRED_PREFIX
        self._name = name
        # property local-name -> stored value (str | list[str] | dict[str,str])
        self._properties: dict[str, object] = {}
        # property local-name -> typed wrapper (TextType / BooleanType / ...).
        # Mirrors the typed-cache pattern used by :mod:`adobe_pdf_schema`: the
        # raw value in ``_properties`` is authoritative for string-form readers,
        # while ``_typed_properties`` lets typed-form getters return the same
        # ``AbstractSimpleProperty`` instance the caller installed.
        self._typed_properties: dict[str, AbstractSimpleProperty] = {}
        # property local-name -> parsed container cardinality. Populated by
        # ``DomXmpParser`` when an array property is read from a packet so the
        # serializer can re-emit the *same* container kind (``rdf:Seq`` vs
        # ``rdf:Bag``) on round-trip. Upstream ``DomXmpParser`` stores the array
        # as an ``ArrayProperty`` carrying its parsed ``Cardinality``; the
        # flat-dict storage here loses that distinction, so this side-table
        # restores it for unknown-schema arrays whose cardinality isn't in
        # ``_FIELD_CARDINALITIES``.
        self._parsed_array_cardinalities: dict[str, object] = {}
        # rdf:about attribute on the surrounding rdf:Description
        self._about: str = ""
        # extra namespace declarations seen on the description element
        self._namespaces: dict[str, str] = {}
        if self._prefix and self._namespace:
            self._namespaces[self._prefix] = self._namespace

    # --- identity ------------------------------------------------------

    def get_metadata(self) -> XMPMetadata:
        return self._metadata

    def get_namespace(self) -> str:
        return self._namespace

    def get_prefix(self) -> str:
        return self._prefix

    def get_about(self) -> str:
        return self._about

    def get_about_attribute(self) -> str | None:
        """
        Mirror of upstream ``getAboutAttribute()``: returns the ``rdf:about``
        value, or ``None`` when none has been set. Upstream returns the backing
        ``Attribute`` instance; cluster #1 stores the value as a plain string,
        so we return that string (or ``None``) until the ``Attribute``
        hierarchy lands.
        """
        return self._about or None

    def get_about_value(self) -> str | None:
        """Alias of :meth:`get_about_attribute` (upstream ``getAboutValue``)."""
        return self.get_about_attribute()

    def set_about(self, about: str) -> None:
        self._about = about

    def set_about_as_simple(self, about: str | None) -> None:
        """
        Mirror of upstream ``setAboutAsSimple(String)``: passing ``None``
        clears the ``rdf:about`` attribute (upstream removes the attribute
        outright, which surfaces as ``getAboutValue()`` returning ``""`` and
        ``getAboutAttribute()`` returning ``null``).
        """
        if about is None:
            self._about = ""
            return
        self._about = about

    def add_namespace(self, prefix: str, uri: str) -> None:
        self._namespaces[prefix] = uri

    def get_namespaces(self) -> dict[str, str]:
        return dict(self._namespaces)

    # --- generic property accessors -----------------------------------

    def get_property(self, local_name: str) -> object | None:
        """
        Return the raw stored value for ``local_name``, or ``None`` if missing.
        Callers that know the cardinality should prefer the typed variants
        (``get_unqualified_text_property_value``, ``get_unqualified_bag_value_list``,
        ``get_unqualified_language_property_value``).
        """
        return self._properties.get(local_name)

    def get_unqualified_property(self, local_name: str) -> object | None:
        """
        Mirror of upstream ``getUnqualifiedProperty(String)``. Cluster #1
        returns the raw stored value (str / list / dict); when the
        ``AbstractField`` hierarchy lands this will return the field instance.
        """
        return self.get_property(local_name)

    def get_abstract_property(self, qualified_name: str) -> object | None:
        """
        Mirror of upstream ``getAbstractProperty(String)`` — returns the
        property registered under ``qualified_name`` (or ``None`` if absent).
        Upstream returns the ``AbstractField`` child whose property name
        matches; cluster #1 stores values directly so we return the raw
        value, matching :meth:`get_property` until the field hierarchy lands.
        """
        return self.get_property(qualified_name)

    def set_property(self, local_name: str, value: object) -> None:
        """Generic setter used by the parser and by subclass helpers."""
        self._properties[local_name] = value

    def has_property(self, local_name: str) -> bool:
        """
        Return ``True`` when ``local_name`` is present in this schema's raw
        property store. This is intentionally a key-presence check, so falsy
        values such as ``""``, ``[]`` and ``{}`` still count as set.
        """
        return local_name in self._properties

    def clear_property(self, local_name: str) -> None:
        """Remove ``local_name`` from this schema. No-op when it is absent."""
        self.remove_property(local_name)

    def clear(self) -> None:
        """Remove every property stored on this schema."""
        self._properties.clear()
        self._typed_properties.clear()

    def add_property(self, prop: object) -> None:
        """
        Mirror of upstream ``addProperty(AbstractField)``. Until the field
        hierarchy lands we accept either:

          * any object exposing ``get_property_name()`` + ``get_value()`` (duck
            typed ``AbstractField`` stand-in), or
          * a ``(name, value)`` tuple/list, for callers that just want the
            upstream-named entry point without constructing a field object.
        """
        if isinstance(prop, (tuple, list)) and len(prop) == 2:
            name, value = prop
            self._properties[str(name)] = value
            return
        get_name = getattr(prop, "get_property_name", None)
        get_value = getattr(prop, "get_value", None)
        if callable(get_name) and callable(get_value):
            self._properties[str(get_name())] = get_value()
            return
        raise TypeError(
            "add_property expects an AbstractField-like object or a (name, value) pair"
        )

    def remove_property(self, local_name: str) -> None:
        self._properties.pop(local_name, None)
        self._typed_properties.pop(local_name, None)

    def get_all_properties(self) -> dict[str, object]:
        return dict(self._properties)

    def get_property_cardinality(self, local_name: str) -> object | None:
        """Return the container cardinality recorded for an array property.

        ``DomXmpParser`` records the parsed ``rdf:Bag`` / ``rdf:Seq`` /
        ``rdf:Alt`` container kind here so :class:`XmpSerializer` can re-emit
        the same container on round-trip. Returns ``None`` when the property
        was never parsed as an array (callers then fall back to the schema's
        ``_FIELD_CARDINALITIES`` declaration, matching the pre-existing path).
        """
        return self._parsed_array_cardinalities.get(local_name)

    def set_parsed_array_cardinality(self, local_name: str, cardinality: object) -> None:
        """Record the container cardinality a property was parsed with.

        Used by :class:`DomXmpParser` to preserve the ``rdf:Seq`` vs
        ``rdf:Bag`` distinction for unknown-schema arrays through a
        parse → serialize round-trip.
        """
        self._parsed_array_cardinalities[local_name] = cardinality

    def get_property_as(self, local_name: str, type_cls: type) -> object | None:
        """
        Mirror of upstream ``XMPSchema.getPropertyAs(name, type)`` — return
        the property at ``local_name`` only if it is an instance of
        ``type_cls``, otherwise ``None``. Cluster #1 stores values as plain
        Python primitives, so the type check matches the stored value's type
        (e.g. ``str`` for TextType, ``list`` for Bag/Seq, ``dict`` for LangAlt,
        ``bool`` for BooleanType, ``int`` for IntegerType). Booleans are
        deliberately distinguished from integers, mirroring the upstream
        ``BooleanType`` vs ``IntegerType`` separation (Python's ``bool`` is a
        subclass of ``int`` but is not returned by ``get_property_as(name,
        int)``).
        """
        value = self._properties.get(local_name)
        if value is None:
            return None
        if type_cls is int and isinstance(value, bool):
            return None
        if isinstance(value, type_cls):
            return value
        return None

    # --- simple (TextType) -------------------------------------------

    def get_unqualified_text_property_value(self, local_name: str) -> str | None:
        v = self._properties.get(local_name)
        if v is None:
            return None
        if isinstance(v, str):
            return v
        # If a parser stored a list/dict for this name, expose first item to
        # preserve "best-effort" read behavior similar to upstream.
        if isinstance(v, list) and v:
            first = v[0]
            return first if isinstance(first, str) else None
        if isinstance(v, dict) and v:
            default = v.get(X_DEFAULT)
            if isinstance(default, str):
                return default
            for item in v.values():
                if isinstance(item, str):
                    return item
        return None

    def set_text_property_value(self, local_name: str, value: str | None) -> None:
        """
        Store a TextType value at ``local_name``. Mirrors upstream
        ``setTextPropertyValue``: passing ``None`` clears the property
        (upstream's ``setSpecifiedSimpleTypeProperty`` removes any existing
        child whose property name matches when the value is ``null``).
        """
        if value is None:
            self._properties.pop(local_name, None)
            self._typed_properties.pop(local_name, None)
            return
        self._properties[local_name] = value
        # Drop any cached typed wrapper that no longer reflects the stored
        # string-form value, mirroring the per-subclass cache invalidation
        # already used by :mod:`adobe_pdf_schema`.
        cached = self._typed_properties.get(local_name)
        if cached is not None and cached.get_string_value() != value:
            self._typed_properties.pop(local_name, None)

    def set_text_property_value_as_simple(
        self, simple_name: str, value: str | None
    ) -> None:
        """
        Mirror of upstream ``XMPSchema.setTextPropertyValueAsSimple`` —
        identical to :meth:`set_text_property_value` for properties whose name
        is already unqualified (no prefix). Provided for parity with upstream
        Java callers that distinguish the two overloads.
        """
        self.set_text_property_value(simple_name, value)

    def create_text_type(self, property_name: str, value: str) -> TextType:
        """
        Mirror of upstream ``AbstractStructuredType.createTextType`` (inherited
        by every ``XMPSchema``): build a :class:`TextType` configured with this
        schema's namespace and prefix and the given local name + value. Used by
        upstream subclasses inside their string-form setters (e.g.
        ``setKeywords``, ``setCoverage``); exposed here so pypdfbox callers can
        construct schema-bound ``TextType`` instances without restating the
        namespace/prefix.
        """
        from .type.text_type import TextType

        return TextType(
            self._metadata, self._namespace, self._prefix, property_name, value
        )

    def add_unqualified_text_property(self, local_name: str, value: str) -> None:
        """
        Mirror of upstream ``addUnqualifiedTextProperty``. Equivalent to
        :meth:`set_text_property_value`; "add" here matches upstream wording —
        a single TextType property has cardinality one, so adding replaces.
        """
        self.set_text_property_value(local_name, value)

    def get_unqualified_text_property(self, local_name: str) -> str | None:
        """
        Mirror of upstream ``getUnqualifiedTextProperty`` — returns the raw
        string value, or ``None`` when absent. Until ``TextType`` lands this
        is the same as :meth:`get_unqualified_text_property_value`.
        """
        return self.get_unqualified_text_property_value(local_name)

    # --- Array creation ----------------------------------------------

    # Upstream array-type tokens (org.apache.xmpbox.type.ArrayProperty).
    UNORDERED_ARRAY = "Bag"
    ORDERED_ARRAY = "Seq"
    ALTERNATIVE_ARRAY = "Alt"

    def add_unqualified_array(self, local_name: str, array_type: str) -> list[str]:
        """
        Mirror of upstream ``addUnqualifiedArrayProperty`` — install an empty
        array property of the requested type. ``array_type`` is one of
        :attr:`UNORDERED_ARRAY` / :attr:`ORDERED_ARRAY` / :attr:`ALTERNATIVE_ARRAY`
        (cluster #1 stores all three as plain lists; the type tag is accepted
        for upstream parity but not yet enforced).

        Returns the freshly-installed list so callers can append directly.
        """
        if array_type not in (
            self.UNORDERED_ARRAY,
            self.ORDERED_ARRAY,
            self.ALTERNATIVE_ARRAY,
        ):
            raise ValueError(f"unknown array type: {array_type!r}")
        new_list: list[str] = []
        self._properties[local_name] = new_list
        return new_list

    # --- Bag (unordered) ---------------------------------------------

    def add_qualified_bag_value(self, local_name: str, value: str) -> None:
        existing = self._properties.get(local_name)
        if isinstance(existing, ArrayProperty):
            from .type.text_type import TextType

            existing.add_property(
                TextType(self._metadata, self._namespace, self._prefix, "li", value)
            )
            return
        if not isinstance(existing, list):
            existing = []
            self._properties[local_name] = existing
        existing.append(value)

    def add_unqualified_bag_value(self, local_name: str, value: str) -> None:
        """
        Mirror of upstream ``addBagValue`` / ``addUnqualifiedBagValue``.
        Alias of :meth:`add_qualified_bag_value`; in upstream the qualified
        and unqualified flavors only differ in how the namespace prefix is
        looked up, which cluster #1 sidesteps by storing local names directly.
        """
        self.add_qualified_bag_value(local_name, value)

    def add_bag_value_as_simple(self, simple_name: str, value: str) -> None:
        """
        Mirror of upstream ``addBagValueAsSimple`` — append ``value`` to the
        bag at ``simple_name`` (a local name in the schema's prefix). Cluster
        #1 stores names unqualified, so this is an alias for
        :meth:`add_qualified_bag_value`.
        """
        self.add_qualified_bag_value(simple_name, value)

    def remove_unqualified_bag_value(self, local_name: str, value: str) -> None:
        existing = self._properties.get(local_name)
        if isinstance(existing, list):
            existing[:] = [item for item in existing if item != value]
            return
        if isinstance(existing, ArrayProperty):
            for child in existing.get_all_properties():
                if (
                    isinstance(child, AbstractSimpleProperty)
                    and child.get_string_value() == value
                ):
                    existing.remove_property(child)

    def remove_unqualified_array_value(self, array_name: str, value: str) -> None:
        """
        Mirror of upstream ``removeUnqualifiedArrayValue`` (the public
        string-valued overload) — generic array entry removal that removes
        every matching ``value`` from the Bag / Seq / Alt array stored at
        ``array_name``. No-op when the property is absent or not an array.
        Cluster #1 stores Bag, Seq and Alt arrays uniformly as ``list``, so
        this delegates to :meth:`remove_unqualified_bag_value` (which already
        scrubs all matches).
        """
        self.remove_unqualified_bag_value(array_name, value)

    def get_unqualified_bag_value_list(self, local_name: str) -> list[str] | None:
        v = self._properties.get(local_name)
        if v is None:
            return None
        if isinstance(v, list):
            return list(v)
        if isinstance(v, ArrayProperty):
            return v.get_elements_as_string()
        if isinstance(v, str):
            return [v]
        return None

    def get_unqualified_array_list(self, local_name: str) -> list[str] | None:
        """
        Mirror of upstream ``getUnqualifiedArrayList`` — return the items of
        the array property at ``local_name`` (Bag, Seq or Alt), or ``None``
        when the property is absent. Cluster #1 stores all array types as
        plain lists, so this delegates to :meth:`get_unqualified_bag_value_list`.
        """
        return self.get_unqualified_bag_value_list(local_name)

    # --- Seq (ordered) — same storage as bag, kept distinct for API parity --

    def add_unqualified_sequence_value(self, local_name: str, value: str) -> None:
        self.add_qualified_bag_value(local_name, value)

    def remove_unqualified_sequence_value(self, local_name: str, value: str) -> None:
        self.remove_unqualified_bag_value(local_name, value)

    def get_unqualified_sequence_value_list(self, local_name: str) -> list[str] | None:
        return self.get_unqualified_bag_value_list(local_name)

    # --- LangAlt ------------------------------------------------------

    def set_unqualified_language_property_value(
        self, local_name: str, lang: str | None, value: str | None
    ) -> None:
        """
        Mirror of upstream ``setUnqualifiedLanguagePropertyValue``: install a
        Lang Alt entry for ``lang`` (defaulting to ``x-default``). Passing
        ``None`` for ``value`` removes the existing entry — upstream's
        behavior, see XMPSchema.java line 1026 ("// the same language has been
        found ... if (value != null)") where a null value triggers the
        entry-removal path with no replacement.
        """
        language = lang or X_DEFAULT
        existing = self._properties.get(local_name)
        if value is None:
            # Remove-only path: drop the language entry if present.
            if isinstance(existing, dict):
                existing.pop(language, None)
            return
        if not isinstance(existing, dict):
            existing = {}
            self._properties[local_name] = existing
        existing[language] = value
        if language == X_DEFAULT:
            self._reorganize_alt_order(existing)

    @staticmethod
    def _reorganize_alt_order(values: dict[str, str]) -> None:
        """Mirror upstream ``reorganizeAltOrder``: keep x-default first."""
        if X_DEFAULT not in values:
            return
        default = values.pop(X_DEFAULT)
        rest = list(values.items())
        values.clear()
        values[X_DEFAULT] = default
        values.update(rest)

    def get_unqualified_language_property_value(
        self, local_name: str, lang: str | None = None
    ) -> str | None:
        v = self._properties.get(local_name)
        if not isinstance(v, dict):
            return None
        return v.get(lang or X_DEFAULT)

    def remove_unqualified_language_property_value(
        self, local_name: str, lang: str | None = None
    ) -> None:
        v = self._properties.get(local_name)
        if not isinstance(v, dict):
            return
        v.pop(lang or X_DEFAULT, None)

    def get_unqualified_language_property_languages_value(
        self, local_name: str
    ) -> list[str] | None:
        v = self._properties.get(local_name)
        if not isinstance(v, dict):
            return None
        return list(v.keys())

    # --- Boolean ------------------------------------------------------
    #
    # Upstream stores booleans as ``BooleanType`` instances; cluster #1 stores
    # the Python ``bool`` directly. Passing ``None`` to either setter mirrors
    # upstream's null-clear semantics (see ``setSpecifiedSimpleTypeProperty``).

    def set_boolean_property_value(
        self, qualified_name: str, value: bool | None
    ) -> None:
        """
        Mirror of upstream ``setBooleanPropertyValue`` — store ``value`` at
        ``qualified_name``. Passing ``None`` removes the property.
        """
        if value is None:
            self._properties.pop(qualified_name, None)
            self._typed_properties.pop(qualified_name, None)
            return
        self._properties[qualified_name] = bool(value)
        cached = self._typed_properties.get(qualified_name)
        if cached is not None and cached.get_value() != bool(value):
            self._typed_properties.pop(qualified_name, None)

    def set_boolean_property_value_as_simple(
        self, simple_name: str, value: bool | None
    ) -> None:
        """Mirror of upstream ``setBooleanPropertyValueAsSimple``."""
        self.set_boolean_property_value(simple_name, value)

    def get_boolean_property_value(self, qualified_name: str) -> bool | None:
        """
        Mirror of upstream ``getBooleanPropertyValue`` — returns the stored
        boolean or ``None`` when absent.
        """
        v = self._properties.get(qualified_name)
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        return None

    def get_boolean_property_value_as_simple(self, simple_name: str) -> bool | None:
        """Mirror of upstream ``getBooleanPropertyValueAsSimple``."""
        return self.get_boolean_property_value(simple_name)

    # --- Integer ------------------------------------------------------

    def set_integer_property_value(
        self, qualified_name: str, value: int | None
    ) -> None:
        """
        Mirror of upstream ``setIntegerPropertyValue`` — store ``value`` at
        ``qualified_name``. Passing ``None`` removes the property.
        """
        if value is None:
            self._properties.pop(qualified_name, None)
            self._typed_properties.pop(qualified_name, None)
            return
        # Reject Python booleans here: ``bool`` is a subclass of ``int`` but
        # upstream treats integers and booleans as distinct types.
        if isinstance(value, bool):
            raise TypeError("set_integer_property_value expects int, got bool")
        self._properties[qualified_name] = int(value)
        cached = self._typed_properties.get(qualified_name)
        if cached is not None and cached.get_value() != int(value):
            self._typed_properties.pop(qualified_name, None)

    def set_integer_property_value_as_simple(
        self, simple_name: str, value: int | None
    ) -> None:
        """Mirror of upstream ``setIntegerPropertyValueAsSimple``."""
        self.set_integer_property_value(simple_name, value)

    def get_integer_property_value(self, qualified_name: str) -> int | None:
        """
        Mirror of upstream ``getIntegerPropertyValue`` — returns the stored
        integer or ``None`` when absent.
        """
        v = self._properties.get(qualified_name)
        if v is None:
            return None
        # Booleans are an int subclass in Python; exclude them so the typed
        # accessor doesn't shadow ``get_boolean_property_value``.
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v
        return None

    def get_integer_property_value_as_simple(self, simple_name: str) -> int | None:
        """Mirror of upstream ``getIntegerPropertyValueAsSimple``."""
        return self.get_integer_property_value(simple_name)

    # --- Date ---------------------------------------------------------
    #
    # Upstream stores dates as ``DateType`` instances wrapping a
    # ``java.util.Calendar``; the Python port stores a timezone-aware
    # :class:`datetime.datetime` directly (matching ``DateType.set_value``'s
    # internal storage). Passing ``None`` to either setter mirrors upstream's
    # null-clear semantics (see ``setSpecifiedSimpleTypeProperty``).

    def set_date_property_value(
        self, qualified_name: str, value: datetime | None
    ) -> None:
        """
        Mirror of upstream ``setDatePropertyValue`` — store ``value`` at
        ``qualified_name``. Passing ``None`` removes the property.
        """
        if value is None:
            self._properties.pop(qualified_name, None)
            self._typed_properties.pop(qualified_name, None)
            return
        if not isinstance(value, datetime):
            raise TypeError(
                "set_date_property_value expects a datetime, got "
                f"{type(value).__name__}"
            )
        self._properties[qualified_name] = value
        cached = self._typed_properties.get(qualified_name)
        if cached is not None and cached.get_value() != value:
            self._typed_properties.pop(qualified_name, None)

    def set_date_property_value_as_simple(
        self, simple_name: str, value: datetime | None
    ) -> None:
        """Mirror of upstream ``setDatePropertyValueAsSimple``."""
        self.set_date_property_value(simple_name, value)

    def get_date_property_value(self, qualified_name: str) -> datetime | None:
        """
        Mirror of upstream ``getDatePropertyValue`` — returns the stored
        :class:`datetime` or ``None`` when absent or when the stored value is
        not a datetime (upstream raises ``BadFieldValueException`` in the
        type-mismatch case; cluster #1 returns ``None`` to keep the call site
        type-safe — see ``get_property_as`` for the strict typed accessor).
        """
        v = self._properties.get(qualified_name)
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        return None

    def get_date_property_value_as_simple(self, simple_name: str) -> datetime | None:
        """Mirror of upstream ``getDatePropertyValueAsSimple``."""
        return self.get_date_property_value(simple_name)

    def add_unqualified_sequence_date_value(
        self, seq_name: str, value: datetime
    ) -> None:
        """
        Mirror of upstream ``addUnqualifiedSequenceDateValue`` — append a
        :class:`datetime` to the Seq array stored at ``seq_name``. Cluster #1
        stores Seq arrays as plain lists, so this lifts the datetime directly
        into the existing list (creating it when absent).
        """
        if not isinstance(value, datetime):
            raise TypeError(
                "add_unqualified_sequence_date_value expects a datetime, got "
                f"{type(value).__name__}"
            )
        existing = self._properties.get(seq_name)
        if not isinstance(existing, list):
            existing = []
            self._properties[seq_name] = existing
        existing.append(value)

    def add_sequence_date_value_as_simple(
        self, simple_name: str, value: datetime
    ) -> None:
        """Mirror of upstream ``addSequenceDateValueAsSimple``."""
        self.add_unqualified_sequence_date_value(simple_name, value)

    def get_unqualified_sequence_date_value_list(
        self, seq_name: str
    ) -> list[datetime] | None:
        """
        Mirror of upstream ``getUnqualifiedSequenceDateValueList`` — return the
        :class:`datetime` entries of the Seq array at ``seq_name``, or ``None``
        when the property is absent / not an array. Non-datetime entries are
        silently skipped, matching upstream's ``instanceof DateType`` filter.
        """
        v = self._properties.get(seq_name)
        if not isinstance(v, list):
            return None
        return [item for item in v if isinstance(item, datetime)]

    def remove_unqualified_sequence_date_value(
        self, seq_name: str, value: datetime
    ) -> None:
        """
        Mirror of upstream ``removeUnqualifiedSequenceDateValue`` — drop every
        :class:`datetime` entry equal to ``value`` from the Seq array at
        ``seq_name``. No-op when the property is absent or not an array.
        """
        existing = self._properties.get(seq_name)
        if not isinstance(existing, list):
            return
        existing[:] = [
            item
            for item in existing
            if not (isinstance(item, datetime) and item == value)
        ]

    # --- typed simple-property setters / getters ----------------------
    #
    # These mirror upstream's ``setXxxProperty(XxxType)`` / ``getXxxProperty``
    # entry points (XMPSchema.java lines 258, 391, 493, 588 for the setters and
    # 333, 430, 532 for the getters). Passing a typed wrapper installs both
    # the raw value (so the existing string-form readers keep working) and
    # caches the wrapper itself, which the typed getters then return so callers
    # see the very instance they handed in (matching upstream's
    # ``addProperty`` semantics inside ``setSpecifiedSimpleTypeProperty``).
    #
    # Type-mismatched lookups raise :class:`BadFieldValueException`, mirroring
    # upstream's ``throws BadFieldValueException`` declarations on the
    # ``getXxxProperty`` family.

    def set_specified_simple_type_property(
        self, prop: AbstractSimpleProperty
    ) -> None:
        """
        Port of upstream ``setSpecifiedSimpleTypeProperty(AbstractSimpleProperty)``
        (XMPSchema.java line 236) — install ``prop`` under its property name,
        replacing any existing entry. The raw value is stored so existing
        string-form accessors keep working; the typed wrapper is cached so the
        typed getter returns the same instance.
        """
        name = prop.get_property_name()
        self._properties[name] = prop.get_value()
        self._typed_properties[name] = prop

    def set_text_property(self, prop: TextType) -> None:
        """
        Mirror of upstream ``setTextProperty(TextType)`` (XMPSchema.java
        line 258) — install ``prop``, replacing any existing entry under the
        same property name.
        """
        self.set_specified_simple_type_property(prop)

    def set_boolean_property(self, prop: BooleanType) -> None:
        """
        Mirror of upstream ``setBooleanProperty(BooleanType)`` (XMPSchema.java
        line 493) — install ``prop``, replacing any existing entry under the
        same property name.
        """
        self.set_specified_simple_type_property(prop)

    def set_integer_property(self, prop: IntegerType) -> None:
        """
        Mirror of upstream ``setIntegerProperty(IntegerType)`` (XMPSchema.java
        line 588) — install ``prop``, replacing any existing entry under the
        same property name.
        """
        self.set_specified_simple_type_property(prop)

    def set_date_property(self, prop: DateType) -> None:
        """
        Mirror of upstream ``setDateProperty(DateType)`` (XMPSchema.java
        line 391) — install ``prop``, replacing any existing entry under the
        same property name.
        """
        self.set_specified_simple_type_property(prop)

    def _typed_property_or_raise(
        self, qualified_name: str, expected_cls: type, type_label: str
    ) -> AbstractSimpleProperty | None:
        """
        Shared body for typed-property getters: return the cached typed
        wrapper, lazily rehydrating one from the raw value when none is
        cached. Returns ``None`` when the property is absent. Raises
        :class:`BadFieldValueException` when the stored value's Python type
        doesn't match the requested XMP type.
        """
        cached = self._typed_properties.get(qualified_name)
        raw = self._properties.get(qualified_name)
        if raw is None and cached is None:
            return None
        if cached is not None and isinstance(cached, expected_cls):
            return cached
        # Raw value present but no (or wrong-type) cached wrapper. Decide based
        # on the raw value's Python type, mirroring upstream's
        # ``instanceof XxxType`` check on the stored field.
        return None if raw is None else self._rehydrate_simple_or_raise(
            qualified_name, raw, expected_cls, type_label
        )

    def _rehydrate_simple_or_raise(
        self,
        qualified_name: str,
        raw: object,
        expected_cls: type,
        type_label: str,
    ) -> AbstractSimpleProperty:
        # Lazy import to avoid an import cycle with the type submodules.
        from .type.boolean_type import BooleanType
        from .type.date_type import DateType
        from .type.integer_type import IntegerType
        from .type.text_type import TextType

        # Booleans are an int subclass in Python; check ``bool`` first.
        if isinstance(raw, bool):
            actual_cls: type = BooleanType
        elif isinstance(raw, int):
            actual_cls = IntegerType
        elif isinstance(raw, datetime):
            actual_cls = DateType
        elif isinstance(raw, str):
            actual_cls = TextType
        else:
            raise BadFieldValueException(
                f"Property asked is not a {type_label} Property"
            )
        if actual_cls is not expected_cls:
            raise BadFieldValueException(
                f"Property asked is not a {type_label} Property"
            )
        wrapper = actual_cls(
            self._metadata, self._namespace, self._prefix, qualified_name, raw
        )
        self._typed_properties[qualified_name] = wrapper
        return wrapper

    def get_boolean_property(self, qualified_name: str) -> BooleanType | None:
        """
        Mirror of upstream ``getBooleanProperty(String)`` (XMPSchema.java
        line 430) — return the :class:`BooleanType` wrapping the value at
        ``qualified_name``, or ``None`` when the property is absent. Raises
        :class:`BadFieldValueException` when the property exists but is not a
        boolean.
        """
        from .type.boolean_type import BooleanType

        result = self._typed_property_or_raise(
            qualified_name, BooleanType, "Boolean"
        )
        return result  # type: ignore[return-value]

    def get_integer_property(self, qualified_name: str) -> IntegerType | None:
        """
        Mirror of upstream ``getIntegerProperty(String)`` (XMPSchema.java
        line 532) — return the :class:`IntegerType` wrapping the value at
        ``qualified_name``, or ``None`` when the property is absent. Raises
        :class:`BadFieldValueException` when the property exists but is not
        an integer.
        """
        from .type.integer_type import IntegerType

        result = self._typed_property_or_raise(
            qualified_name, IntegerType, "Integer"
        )
        return result  # type: ignore[return-value]

    def get_date_property(self, qualified_name: str) -> DateType | None:
        """
        Mirror of upstream ``getDateProperty(String)`` (XMPSchema.java
        line 333) — return the :class:`DateType` wrapping the value at
        ``qualified_name``, or ``None`` when the property is absent. Raises
        :class:`BadFieldValueException` when the property exists but is not a
        date.
        """
        from .type.date_type import DateType

        result = self._typed_property_or_raise(qualified_name, DateType, "Date")
        return result  # type: ignore[return-value]

    # --- typed bag helpers --------------------------------------------

    def add_bag_value(self, qualified_name: str, value: object) -> None:
        """
        Mirror of upstream ``addBagValue(String, AbstractField)`` (XMPSchema
        .java line 806) — append a typed :class:`AbstractField` to the Bag at
        ``qualified_name``, creating the array when absent. Cluster #1 stores
        Bag arrays as plain lists; if ``value`` is an
        :class:`AbstractSimpleProperty`, its underlying string value is
        appended so existing string-form readers keep working.
        """
        self.internal_add_bag_value(qualified_name, value)

    def internal_add_bag_value(self, qualified_name: str, value: object) -> None:
        """
        Port of upstream ``internalAddBagValue(String, String)`` (XMPSchema
        .java line 672). Cluster #1 stores Bag arrays as plain lists, so this
        unwraps an :class:`AbstractSimpleProperty` to its string value before
        appending.
        """
        existing = self._properties.get(qualified_name)
        if isinstance(value, AbstractSimpleProperty):
            string_value = value.get_string_value()
        else:
            string_value = str(value)
        if isinstance(existing, ArrayProperty):
            from .type.text_type import TextType

            existing.add_property(
                TextType(
                    self._metadata,
                    self._namespace,
                    self._prefix,
                    "li",
                    string_value,
                )
            )
            return
        if not isinstance(existing, list):
            existing = []
            self._properties[qualified_name] = existing
        existing.append(string_value)

    # --- LangAlt helpers ----------------------------------------------

    def reorganize_alt_order(self, values: dict[str, str] | object) -> None:
        """
        Mirror of upstream ``reorganizeAltOrder(ComplexPropertyContainer)``
        (XMPSchema.java line 954) — keep the ``x-default`` entry first when an
        Alt array contains one. Cluster #1 stores Alt arrays as ``dict`` keyed
        by language; this delegates to :meth:`_reorganize_alt_order` for that
        shape and is a no-op for any other shape.
        """
        if isinstance(values, dict):
            self._reorganize_alt_order(values)

    # --- protected helpers (subclass-facing) --------------------------

    def instanciate_simple(
        self, property_name: str, value: object
    ) -> AbstractSimpleProperty:
        """
        Port of upstream ``instanciateSimple(String, Object)`` (XMPSchema.java
        line 1224) — build an :class:`AbstractSimpleProperty` whose concrete
        type is inferred from ``value``'s Python type. Used by subclasses that
        want to install a typed wrapper without restating the namespace /
        prefix. Naming preserves the upstream typo (``instanciate`` not
        ``instantiate``) for diff parity. Raises :class:`TypeError` for values
        whose type can't be mapped to a supported XMP simple type.
        """
        from .type.boolean_type import BooleanType
        from .type.date_type import DateType
        from .type.integer_type import IntegerType
        from .type.text_type import TextType

        # ``bool`` first — it is an ``int`` subclass.
        if isinstance(value, bool):
            cls: type[AbstractSimpleProperty] = BooleanType
        elif isinstance(value, int):
            cls = IntegerType
        elif isinstance(value, datetime):
            cls = DateType
        elif isinstance(value, str):
            cls = TextType
        else:
            raise TypeError(
                f"Cannot instanciate a simple property for value of type "
                f"{type(value).__name__}"
            )
        return cls(self._metadata, self._namespace, self._prefix, property_name, value)

    # --- merge --------------------------------------------------------

    def merge(self, other: XMPSchema) -> None:
        """
        Mirror of upstream ``XMPSchema.merge`` — basic schema merge:

          * Bag / Seq / Alt array properties union their contents (existing
            entries are preserved; entries already present in this schema are
            not duplicated, matching upstream's ``mergeComplexProperty`` short
            -circuit on the first match).
          * LangAlt (dict-backed) properties merge entry-by-entry; entries
            already present in this schema's value win, matching the upstream
            "first match wins" semantics.
          * All other properties (simple text, boolean, integer, ...) replace
            the existing value (upstream's ``addProperty`` overwrites by local
            name).
          * Extra namespace declarations from ``other`` are copied over.

        Schemas of differing concrete types raise :class:`OSError`, mirroring
        upstream's ``IOException`` ("Can only merge schemas of the same
        type.").
        """
        if type(other) is not type(self):
            raise OSError("Can only merge schemas of the same type.")
        # Copy across extra namespace declarations.
        for prefix, uri in other.get_namespaces().items():
            self._namespaces.setdefault(prefix, uri)
        for name, new_value in other.get_all_properties().items():
            existing = self._properties.get(name)
            if isinstance(new_value, list) and isinstance(existing, list):
                # Array merge: append entries that aren't already present.
                for item in new_value:
                    if item not in existing:
                        existing.append(item)
            elif isinstance(new_value, dict) and isinstance(existing, dict):
                # LangAlt merge: keep existing entries, fill in missing ones.
                for lang, val in new_value.items():
                    existing.setdefault(lang, val)
                self._reorganize_alt_order(existing)
            else:
                # Simple / mismatched-shape: replace.
                self._properties[name] = new_value

    def merge_complex_property(
        self, new_values: list[object], existing: list[object]
    ) -> bool:
        """
        Port of upstream ``mergeComplexProperty(Iterator, ArrayProperty)``
        (XMPSchema.java line 1176) — iterate ``new_values`` and append each one
        that doesn't already appear in ``existing``; return ``True`` as soon as
        a duplicate is encountered (upstream's ``return true`` short-circuits
        the iteration so any remaining entries in ``new_values`` are dropped).
        Returns ``False`` when every new entry was appended cleanly.

        ``XMPSchema.merge`` does not call this helper directly because cluster
        #1 prefers a full union (no early short-circuit on duplicates) — see
        ``CHANGES.md``. The helper is provided so callers wanting strict
        upstream behavior can opt in.
        """
        for item in new_values:
            if item in existing:
                return True
            existing.append(item)
        return False
