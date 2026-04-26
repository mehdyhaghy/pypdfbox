from __future__ import annotations

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

    def set_property(self, local_name: str, value: object) -> None:
        """Generic setter used by the parser and by subclass helpers."""
        self._properties[local_name] = value

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

    # --- Bag (unordered) ---------------------------------------------

    def add_qualified_bag_value(self, local_name: str, value: str) -> None:
        existing = self._properties.get(local_name)
        if not isinstance(existing, list):
            existing = []
            self._properties[local_name] = existing
        existing.append(value)

    def remove_unqualified_bag_value(self, local_name: str, value: str) -> None:
        existing = self._properties.get(local_name)
        if isinstance(existing, list):
            try:
                existing.remove(value)
            except ValueError:
                pass

    def get_unqualified_bag_value_list(self, local_name: str) -> list[str] | None:
        v = self._properties.get(local_name)
        if v is None:
            return None
        if isinstance(v, list):
            return list(v)
        if isinstance(v, str):
            return [v]
        return None

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
        existing[lang or X_DEFAULT] = value

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
