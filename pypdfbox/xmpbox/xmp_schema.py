from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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

    The upstream ``AbstractField`` / ``ArrayProperty`` / ``TextType`` hierarchy
    is intentionally deferred — see CLAUDE.md ("Behavior over style") and the
    cluster #1 plan: this is the read path only. Writers, type validation and
    structured types arrive in later clusters.
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

    def set_about_as_simple(self, about: str) -> None:
        # Upstream method name is setAboutAsSimple; mirrored verbatim.
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

    def set_property(self, local_name: str, value: object) -> None:
        """Generic setter used by the parser and by subclass helpers."""
        self._properties[local_name] = value

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
            if default is not None:
                return default
            for item in v.values():
                if isinstance(item, str):
                    return item
        return None

    def set_text_property_value(self, local_name: str, value: str) -> None:
        self._properties[local_name] = value

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

    def remove_unqualified_bag_value(self, local_name: str, value: str) -> None:
        existing = self._properties.get(local_name)
        if isinstance(existing, list):
            with suppress(ValueError):
                existing.remove(value)

    def get_unqualified_bag_value_list(self, local_name: str) -> list[str] | None:
        v = self._properties.get(local_name)
        if v is None:
            return None
        if isinstance(v, list):
            return list(v)
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

    def get_unqualified_language_property_languages_value(
        self, local_name: str
    ) -> list[str] | None:
        v = self._properties.get(local_name)
        if not isinstance(v, dict):
            return None
        return list(v.keys())
