from __future__ import annotations

import contextlib
from datetime import date, datetime
from typing import TYPE_CHECKING

from .abstract_field import AbstractField, Attribute
from .abstract_simple_property import AbstractSimpleProperty
from .array_property import ArrayProperty, Cardinality

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata
    from .text_type import TextType


STRUCTURE_ARRAY_NAME = "li"


class AbstractStructuredType(AbstractField):
    """
    Base class for XMP structured property types.

    Ported from ``org.apache.xmpbox.type.AbstractStructuredType``. Upstream
    extends ``AbstractComplexProperty`` which itself owns a
    ``ComplexPropertyContainer`` plus a namespace-to-prefix map; the upstream
    container is folded into a flat ``list[AbstractField]`` here because the
    only operations pypdfbox needs are append / iterate / first-by-localname.

    Concrete subclasses (``DimensionsType``, ``JobType``, ...) carry a
    class-level ``_FIELD_TYPES`` dict mapping field local-name to a simple
    type-name string registered with :class:`TypeMapping`. That stands in for
    the upstream ``@PropertyType`` reflection annotations and lets
    :meth:`add_simple_property` dispatch to the right wrapper class. Subclasses
    that should pick up their namespace + prefix from a ``@StructuredType``
    annotation set ``NAMESPACE`` / ``PREFERRED_PREFIX`` class attributes
    (mirroring the upstream annotation values).
    """

    # Mirrors upstream `protected static final String STRUCTURE_ARRAY_NAME = "li"`.
    # Kept as a class attribute (in addition to the module-level constant above)
    # so subclasses can reach it via `type(self).STRUCTURE_ARRAY_NAME` or
    # `AbstractStructuredType.STRUCTURE_ARRAY_NAME`, matching upstream lookup.
    STRUCTURE_ARRAY_NAME: str = STRUCTURE_ARRAY_NAME

    NAMESPACE: str | None = None
    PREFERRED_PREFIX: str | None = None
    _FIELD_TYPES: dict[str, str] = {}

    def __init__(
        self,
        metadata: XMPMetadata,
        namespace_uri: str | None = None,
        field_prefix: str | None = None,
        property_name: str | None = None,
    ) -> None:
        super().__init__(metadata, property_name)
        annotation_ns = type(self).NAMESPACE
        annotation_prefix = type(self).PREFERRED_PREFIX
        if annotation_ns is not None:
            self._namespace = annotation_ns
            self._preferred_prefix = annotation_prefix
        else:
            if namespace_uri is None:
                raise ValueError(
                    "Both StructuredType annotation and namespace parameter cannot be null"
                )
            self._namespace = namespace_uri
            self._preferred_prefix = field_prefix
        self._prefix = field_prefix if field_prefix is not None else self._preferred_prefix
        self._properties: list[AbstractField] = []
        self._namespace_to_prefix: dict[str, str] = {}

    # --- identity ----------------------------------------------------

    def get_namespace(self) -> str | None:
        return self._namespace

    def set_namespace(self, ns: str) -> None:
        self._namespace = ns

    def get_prefix(self) -> str | None:
        return self._prefix

    def set_prefix(self, pf: str | None) -> None:
        self._prefix = pf

    def get_prefered_prefix(self) -> str | None:
        return self._preferred_prefix

    def get_preferred_prefix(self) -> str | None:
        """Spelling-corrected alias of :meth:`get_prefered_prefix`."""
        return self._preferred_prefix

    # --- namespace map ----------------------------------------------

    def add_namespace(self, namespace: str, prefix: str | None) -> None:
        self._namespace_to_prefix[namespace] = prefix or ""

    def get_namespace_prefix(self, namespace: str) -> str | None:
        return self._namespace_to_prefix.get(namespace)

    def get_all_namespaces_with_prefix(self) -> dict[str, str]:
        return self._namespace_to_prefix

    # --- property container -----------------------------------------

    def add_property(self, obj: AbstractField) -> None:
        # Mirror of upstream AbstractComplexProperty.addProperty: replace any
        # property with the same local name (except for array containers, which
        # we don't expose here — ArrayProperty does its own append).
        name = obj.get_property_name()
        if name is not None:
            self._properties = [
                p for p in self._properties if p.get_property_name() != name
            ]
        self._properties.append(obj)

    def remove_property(self, prop: AbstractField) -> None:
        with contextlib.suppress(ValueError):
            self._properties.remove(prop)

    def get_all_properties(self) -> list[AbstractField]:
        return self._properties

    def get_property(self, field_name: str) -> AbstractField | None:
        for prop in self._properties:
            if prop.get_property_name() == field_name:
                return prop
        return None

    def get_array_property(self, field_name: str) -> ArrayProperty | None:
        prop = self.get_property(field_name)
        if isinstance(prop, ArrayProperty):
            return prop
        return None

    def get_first_equivalent_property(
        self, local_name: str, type_cls: type
    ) -> AbstractField | None:
        for prop in self._properties:
            if prop.get_property_name() == local_name and type(prop) is type_cls:
                return prop
        return None

    # --- typed helpers -----------------------------------------------

    def add_simple_property(self, property_name: str, value: object) -> None:
        type_name = self._FIELD_TYPES.get(property_name, "Text")
        from .type_mapping import TypeMapping

        tm = TypeMapping(self._metadata)
        asp = tm.instanciate_simple_property(
            None, self.get_prefix(), property_name, value, type_name
        )
        self.add_property(asp)

    def get_property_value_as_string(self, field_name: str) -> str | None:
        prop = self.get_property(field_name)
        if isinstance(prop, AbstractSimpleProperty):
            return prop.get_string_value()
        return None

    def get_date_property_as_calendar(self, field_name: str) -> datetime | None:
        from .date_type import DateType

        prop = self.get_first_equivalent_property(field_name, DateType)
        if isinstance(prop, DateType):
            return prop.get_value()
        return None

    def create_text_type(self, property_name: str, value: str) -> TextType:
        from .text_type import TextType

        return TextType(
            self._metadata, self.get_namespace(), self.get_prefix(), property_name, value
        )

    def create_array_property(
        self, property_name: str, cardinality: Cardinality
    ) -> ArrayProperty:
        return ArrayProperty(
            self._metadata,
            self.get_namespace(),
            self.get_prefix(),
            property_name,
            cardinality,
        )

    # --- conversion utilities ---------------------------------------

    @staticmethod
    def _is_calendar_like(value: object) -> bool:
        return isinstance(value, (datetime, date))

    def _new_attribute(self, ns_uri: str | None, name: str, value: str) -> Attribute:
        return Attribute(ns_uri, name, value)
