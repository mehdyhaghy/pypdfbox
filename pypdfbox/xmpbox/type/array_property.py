from __future__ import annotations

import contextlib
from enum import Enum
from typing import TYPE_CHECKING

from .abstract_field import AbstractField
from .abstract_simple_property import AbstractSimpleProperty

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class Cardinality(Enum):
    """
    Ported from ``org.apache.xmpbox.type.Cardinality``. ``Simple`` is the
    scalar-property marker; the three array flavours are ``Bag`` (unordered),
    ``Seq`` (ordered) and ``Alt`` (alternative — language alternatives, etc).
    """

    Simple = False
    Bag = True
    Seq = True
    Alt = True

    def is_array(self) -> bool:
        return bool(self.value)


class ArrayProperty(AbstractField):
    """
    XMP array property representation, used for ``rdf:Bag`` / ``rdf:Seq`` /
    ``rdf:Alt`` containers.

    Ported from ``org.apache.xmpbox.type.ArrayProperty``. Children are
    :class:`AbstractField` instances (typically :class:`AbstractSimpleProperty`
    or nested :class:`ArrayProperty`); the upstream ``ComplexPropertyContainer``
    is folded into a plain Python list here because the only operations
    pypdfbox needs are append / iterate / by-name lookup.
    """

    def __init__(
        self,
        metadata: XMPMetadata,
        namespace: str | None,
        prefix: str | None,
        property_name: str,
        array_type: Cardinality,
    ) -> None:
        super().__init__(metadata, property_name)
        self._array_type = array_type
        self._namespace = namespace
        self._prefix = prefix
        self._properties: list[AbstractField] = []

    def get_array_type(self) -> Cardinality:
        return self._array_type

    def get_namespace(self) -> str | None:
        return self._namespace

    def get_prefix(self) -> str | None:
        return self._prefix

    def add_property(self, obj: AbstractField) -> None:
        # Upstream's AbstractComplexProperty.addProperty removes existing
        # properties with the same local name unless `this instanceof
        # ArrayProperty` — array containers append, so we mirror that here.
        self._properties.append(obj)

    def remove_property(self, prop: AbstractField) -> None:
        with contextlib.suppress(ValueError):
            self._properties.remove(prop)

    def get_all_properties(self) -> list[AbstractField]:
        return list(self._properties)

    def get_elements_as_string(self) -> list[str]:
        result: list[str] = []
        for child in self._properties:
            if isinstance(child, AbstractSimpleProperty):
                result.append(child.get_string_value())
        return result
