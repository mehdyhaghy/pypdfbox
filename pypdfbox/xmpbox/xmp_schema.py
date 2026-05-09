from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .type.abstract_simple_property import AbstractSimpleProperty
from .type.array_property import ArrayProperty

if TYPE_CHECKING:
    from .type.text_type import TextType
    from .xmp_metadata import XMPMetadata


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

    def get_all_properties(self) -> dict[str, object]:
        return dict(self._properties)

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
            return
        self._properties[local_name] = value

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
        self, local_name: str, lang: str | None, value: str
    ) -> None:
        existing = self._properties.get(local_name)
        if not isinstance(existing, dict):
            existing = {}
            self._properties[local_name] = existing
        language = lang or X_DEFAULT
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
            return
        self._properties[qualified_name] = bool(value)

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
            return
        # Reject Python booleans here: ``bool`` is a subclass of ``int`` but
        # upstream treats integers and booleans as distinct types.
        if isinstance(value, bool):
            raise TypeError("set_integer_property_value expects int, got bool")
        self._properties[qualified_name] = int(value)

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
            return
        if not isinstance(value, datetime):
            raise TypeError(
                "set_date_property_value expects a datetime, got "
                f"{type(value).__name__}"
            )
        self._properties[qualified_name] = value

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
