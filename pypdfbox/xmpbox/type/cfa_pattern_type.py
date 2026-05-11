from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .array_property import ArrayProperty, Cardinality
from .integer_type import IntegerType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class CFAPatternType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.CFAPatternType``. Represents the
    EXIF colour-filter-array description (``Columns`` / ``Rows`` plus a
    ``Seq`` of per-cell integer ``Values``) carried inside the
    ``exif:CFAPattern`` / ``exif:CFAPatternType`` properties.

    Upstream lives under the ``exif`` prefix in the EXIF namespace
    (``http://ns.adobe.com/exif/1.0/``); the ``@PropertyType`` annotations
    are: ``Columns`` (Integer), ``Rows`` (Integer), ``Values`` (Seq of
    Integer).
    """

    NAMESPACE = "http://ns.adobe.com/exif/1.0/"
    PREFERRED_PREFIX = "exif"

    COLUMNS = "Columns"
    ROWS = "Rows"
    VALUES = "Values"

    _FIELD_TYPES = {
        COLUMNS: "Integer",
        ROWS: "Integer",
        # ``Values`` is a Seq<Integer>; the array container is built
        # explicitly through :meth:`add_value` since ``_FIELD_TYPES`` only
        # carries the simple-type contract for ``add_simple_property``.
        VALUES: "Integer",
    }

    def __init__(self, metadata: XMPMetadata) -> None:
        super().__init__(metadata)

    # --- Columns -----------------------------------------------------

    def get_columns(self) -> int | None:
        prop = self.get_first_equivalent_property(self.COLUMNS, IntegerType)
        if isinstance(prop, IntegerType):
            return prop.get_value()
        return None

    def set_columns(self, value: int) -> None:
        self.add_simple_property(self.COLUMNS, value)

    def get_columns_property(self) -> IntegerType | None:
        prop = self.get_first_equivalent_property(self.COLUMNS, IntegerType)
        return prop if isinstance(prop, IntegerType) else None

    # --- Rows --------------------------------------------------------

    def get_rows(self) -> int | None:
        prop = self.get_first_equivalent_property(self.ROWS, IntegerType)
        if isinstance(prop, IntegerType):
            return prop.get_value()
        return None

    def set_rows(self, value: int) -> None:
        self.add_simple_property(self.ROWS, value)

    def get_rows_property(self) -> IntegerType | None:
        prop = self.get_first_equivalent_property(self.ROWS, IntegerType)
        return prop if isinstance(prop, IntegerType) else None

    # --- Values (Seq<Integer>) ---------------------------------------

    def get_values_property(self) -> ArrayProperty | None:
        prop = self.get_first_equivalent_property(self.VALUES, ArrayProperty)
        return prop if isinstance(prop, ArrayProperty) else None

    def get_values(self) -> list[int] | None:
        seq = self.get_values_property()
        if seq is None:
            return None
        out: list[int] = []
        for child in seq.get_all_properties():
            if isinstance(child, IntegerType):
                value = child.get_value()
                if value is not None:
                    out.append(value)
        return out

    def add_value(self, value: int) -> None:
        seq = self.get_values_property()
        if seq is None:
            seq = ArrayProperty(
                self._metadata,
                None,
                self.get_prefered_prefix(),
                self.VALUES,
                Cardinality.Seq,
            )
            self.add_property(seq)
        seq.add_property(
            IntegerType(self._metadata, None, "rdf", "li", value)
        )
