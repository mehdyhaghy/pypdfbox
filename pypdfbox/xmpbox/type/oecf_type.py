from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .array_property import ArrayProperty, Cardinality
from .integer_type import IntegerType
from .real_type import RealType
from .text_type import TextType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class OECFType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.OECFType``. Represents the EXIF
    Opto-Electronic Conversion Function structure used by ``exif:OECF`` and
    ``exif:SpatialFrequencyResponse`` properties. The struct carries the
    matrix shape (``Columns`` / ``Rows`` integers) plus parallel ``Names``
    (Seq<Text>) and ``Values`` (Seq<Real>) describing the per-cell
    measurement labels and floating-point readings.

    Upstream lives under the ``exif`` prefix in the EXIF namespace
    (``http://ns.adobe.com/exif/1.0/``); the ``@PropertyType`` annotations
    are: ``Columns`` (Integer), ``Rows`` (Integer), ``Names`` (Seq of
    Text), ``Values`` (Seq of Real).
    """

    NAMESPACE = "http://ns.adobe.com/exif/1.0/"
    PREFERRED_PREFIX = "exif"

    COLUMNS = "Columns"
    ROWS = "Rows"
    NAMES = "Names"
    VALUES = "Values"

    _FIELD_TYPES = {
        COLUMNS: "Integer",
        ROWS: "Integer",
        # ``Names`` and ``Values`` are Seq containers; the array container is
        # built explicitly through the ``add_name`` / ``add_value`` helpers
        # below because ``_FIELD_TYPES`` only carries the simple-type contract
        # for :meth:`AbstractStructuredType.add_simple_property`.
        NAMES: "Text",
        VALUES: "Real",
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

    # --- Names (Seq<Text>) -------------------------------------------

    def get_names_property(self) -> ArrayProperty | None:
        prop = self.get_first_equivalent_property(self.NAMES, ArrayProperty)
        return prop if isinstance(prop, ArrayProperty) else None

    def get_names(self) -> list[str] | None:
        seq = self.get_names_property()
        if seq is None:
            return None
        out: list[str] = []
        for child in seq.get_all_properties():
            if isinstance(child, TextType):
                value = child.get_string_value()
                if isinstance(value, str):
                    out.append(value)
        return out

    def add_name(self, value: str) -> None:
        seq = self.get_names_property()
        if seq is None:
            seq = ArrayProperty(
                self._metadata,
                None,
                self.get_prefered_prefix(),
                self.NAMES,
                Cardinality.Seq,
            )
            self.add_property(seq)
        seq.add_property(
            TextType(self._metadata, None, "rdf", "li", value)
        )

    # --- Values (Seq<Real>) ------------------------------------------

    def get_values_property(self) -> ArrayProperty | None:
        prop = self.get_first_equivalent_property(self.VALUES, ArrayProperty)
        return prop if isinstance(prop, ArrayProperty) else None

    def get_values(self) -> list[float] | None:
        seq = self.get_values_property()
        if seq is None:
            return None
        out: list[float] = []
        for child in seq.get_all_properties():
            if isinstance(child, RealType):
                value = child.get_value()
                if value is not None:
                    out.append(value)
        return out

    def add_value(self, value: float) -> None:
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
            RealType(self._metadata, None, "rdf", "li", value)
        )
