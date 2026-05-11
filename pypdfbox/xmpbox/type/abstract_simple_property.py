from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from .abstract_field import AbstractField

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class AbstractSimpleProperty(AbstractField):
    """
    Abstract base class for simple (scalar) XMP properties.

    Ported from ``org.apache.xmpbox.type.AbstractSimpleProperty``. Subclasses
    implement :meth:`set_value` (which validates and stores), :meth:`get_value`
    (returns the typed Python value) and :meth:`get_string_value` (returns the
    canonical XML serialization). The raw constructor argument is kept around
    via :meth:`get_raw_value` for downstream validation use.
    """

    def __init__(
        self,
        metadata: XMPMetadata,
        namespace_uri: str | None,
        prefix: str | None,
        property_name: str,
        value: Any,
    ) -> None:
        super().__init__(metadata, property_name)
        self.set_value(value)
        self._namespace = namespace_uri
        self._prefix = prefix
        self._raw_value = value

    @abstractmethod
    def set_value(self, value: Any) -> None:
        """Validate and store the property's typed value.

        Mirrors upstream ``AbstractSimpleProperty.setValue(Object)`` — abstract
        in Java; each simple-property subclass (Boolean, Integer, Real, Text,
        Date, …) is responsible for type-checking and storing the value.
        """

    def setValue(self, value: Any) -> None:  # noqa: N802 - upstream Java name
        self.set_value(value)

    @abstractmethod
    def get_string_value(self) -> str:
        """Return the property's value as its canonical XML serialization.

        Mirrors upstream ``AbstractSimpleProperty.getStringValue()`` — abstract
        in Java. Subclasses convert the stored typed value back to the textual
        form expected in XMP packets (e.g. ``"True"``/``"False"`` for booleans).
        """

    def getStringValue(self) -> str:  # noqa: N802 - upstream Java name
        return self.get_string_value()

    @abstractmethod
    def get_value(self) -> Any:
        """Return the property's typed Python value.

        Mirrors upstream ``AbstractSimpleProperty.getValue()`` — abstract in
        Java. Subclasses return the stored value coerced to the expected
        Python type (``bool``, ``int``, ``float``, ``str``, ``datetime``…).
        """

    def getValue(self) -> Any:  # noqa: N802 - upstream Java name
        return self.get_value()

    def get_raw_value(self) -> Any:
        return self._raw_value

    def getRawValue(self) -> Any:  # noqa: N802 - upstream Java name
        return self.get_raw_value()

    def to_string(self) -> str:
        """Mirror upstream ``AbstractSimpleProperty.toString()``.

        Upstream format (Java line 102):
        ``"[" + getPropertyName() + "=" + getClass().getSimpleName() +
        ":" + getStringValue() + "]"``.
        """
        return (
            f"[{self.get_property_name()}="
            f"{type(self).__name__}:{self.get_string_value()}]"
        )

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return self.to_string()

    def get_namespace(self) -> str | None:
        return self._namespace

    def getNamespace(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_namespace()

    def get_prefix(self) -> str | None:
        return self._prefix

    def getPrefix(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_prefix()
