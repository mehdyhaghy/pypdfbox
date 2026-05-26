from __future__ import annotations

from typing import TYPE_CHECKING

from .abstract_structured_type import AbstractStructuredType
from .array_property import ArrayProperty, Cardinality
from .integer_type import IntegerType
from .text_type import TextType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


class DeviceSettingsType(AbstractStructuredType):
    """
    Ported from ``org.apache.xmpbox.type.DeviceSettingsType``. Represents the
    EXIF device-settings description used by the ``exif:DeviceSettingDescription``
    property: the matrix shape (``Columns`` / ``Rows`` integers) plus a
    ``Settings`` (Seq<Text>) list of free-form setting strings.

    Upstream carries the ``@StructuredType(preferedPrefix = "exif", namespace =
    "http://ns.adobe.com/exif/1.0/")`` annotation, mirrored here by the
    ``NAMESPACE`` / ``PREFERRED_PREFIX`` class attributes. The ``@PropertyType``
    annotations are: ``Columns`` (Integer), ``Rows`` (Integer), ``Settings``
    (Seq of Text).
    """

    NAMESPACE = "http://ns.adobe.com/exif/1.0/"
    PREFERRED_PREFIX = "exif"

    COLUMNS = "Columns"
    ROWS = "Rows"
    SETTINGS = "Settings"

    _FIELD_TYPES = {
        COLUMNS: "Integer",
        ROWS: "Integer",
        # ``Settings`` is a Seq<Text>; the array container is built explicitly
        # through :meth:`add_setting` because ``_FIELD_TYPES`` only carries the
        # simple-type contract for ``add_simple_property``.
        SETTINGS: "Text",
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

    # --- Settings (Seq<Text>) ----------------------------------------

    def get_settings_property(self) -> ArrayProperty | None:
        prop = self.get_first_equivalent_property(self.SETTINGS, ArrayProperty)
        return prop if isinstance(prop, ArrayProperty) else None

    def get_settings(self) -> list[str] | None:
        seq = self.get_settings_property()
        if seq is None:
            return None
        out: list[str] = []
        for child in seq.get_all_properties():
            if isinstance(child, TextType):
                value = child.get_string_value()
                if isinstance(value, str):
                    out.append(value)
        return out

    def add_setting(self, value: str) -> None:
        seq = self.get_settings_property()
        if seq is None:
            seq = ArrayProperty(
                self._metadata,
                None,
                self.get_prefered_prefix(),
                self.SETTINGS,
                Cardinality.Seq,
            )
            self.add_property(seq)
        seq.add_property(
            TextType(self._metadata, None, "rdf", "li", value)
        )
