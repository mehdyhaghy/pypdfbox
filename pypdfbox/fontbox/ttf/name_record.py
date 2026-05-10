from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class NameRecord:
    """A single record inside the ``name`` table.

    Mirrors ``org.apache.fontbox.ttf.NameRecord`` — including its public
    integer constants used by callers to look up names by
    ``(name_id, platform_id, encoding_id, language_id)``.
    """

    # platform ids
    PLATFORM_UNICODE: int = 0
    PLATFORM_MACINTOSH: int = 1
    PLATFORM_ISO: int = 2
    PLATFORM_WINDOWS: int = 3

    # Unicode encoding ids
    ENCODING_UNICODE_1_0: int = 0
    ENCODING_UNICODE_1_1: int = 1
    ENCODING_UNICODE_2_0_BMP: int = 3
    ENCODING_UNICODE_2_0_FULL: int = 4

    # Unicode language ids
    LANGUAGE_UNICODE: int = 0
    # FontBox 2.x exposed these misspelled public constants. Keep aliases so
    # code ported from that API keeps working while the correctly spelled
    # FontBox 3.x names remain canonical.
    LANGUGAE_UNICODE: int = LANGUAGE_UNICODE

    # Windows encoding ids
    ENCODING_WINDOWS_SYMBOL: int = 0
    ENCODING_WINDOWS_UNICODE_BMP: int = 1
    ENCODING_WINDOWS_UNICODE_UCS4: int = 10

    # Windows language ids
    LANGUAGE_WINDOWS_EN_US: int = 0x0409
    LANGUGAE_WINDOWS_EN_US: int = LANGUAGE_WINDOWS_EN_US

    # Macintosh encoding ids
    ENCODING_MACINTOSH_ROMAN: int = 0

    # Macintosh language ids
    LANGUAGE_MACINTOSH_ENGLISH: int = 0
    LANGUGAE_MACINTOSH_ENGLISH: int = LANGUAGE_MACINTOSH_ENGLISH

    # name ids
    NAME_COPYRIGHT: int = 0
    NAME_FONT_FAMILY_NAME: int = 1
    NAME_FONT_SUB_FAMILY_NAME: int = 2
    NAME_UNIQUE_FONT_ID: int = 3
    NAME_FULL_FONT_NAME: int = 4
    NAME_VERSION: int = 5
    NAME_POSTSCRIPT_NAME: int = 6
    NAME_TRADEMARK: int = 7

    def __init__(self) -> None:
        self._platform_id: int = 0
        self._platform_encoding_id: int = 0
        self._language_id: int = 0
        self._name_id: int = 0
        self._string_length: int = 0
        self._string_offset: int = 0
        self._string: str | None = None

    def init_data(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        self._platform_id = data.read_unsigned_short()
        self._platform_encoding_id = data.read_unsigned_short()
        self._language_id = data.read_unsigned_short()
        self._name_id = data.read_unsigned_short()
        self._string_length = data.read_unsigned_short()
        self._string_offset = data.read_unsigned_short()

    def get_platform_id(self) -> int:
        return self._platform_id

    def getPlatformId(self) -> int:  # noqa: N802 - upstream Java name
        return self.get_platform_id()

    def set_platform_id(self, value: int) -> None:
        self._platform_id = value

    def setPlatformId(self, value: int) -> None:  # noqa: N802
        self.set_platform_id(value)

    def get_platform_encoding_id(self) -> int:
        return self._platform_encoding_id

    def getPlatformEncodingId(self) -> int:  # noqa: N802
        return self.get_platform_encoding_id()

    def set_platform_encoding_id(self, value: int) -> None:
        self._platform_encoding_id = value

    def setPlatformEncodingId(self, value: int) -> None:  # noqa: N802
        self.set_platform_encoding_id(value)

    def get_language_id(self) -> int:
        return self._language_id

    def getLanguageId(self) -> int:  # noqa: N802
        return self.get_language_id()

    def set_language_id(self, value: int) -> None:
        self._language_id = value

    def setLanguageId(self, value: int) -> None:  # noqa: N802
        self.set_language_id(value)

    def get_name_id(self) -> int:
        return self._name_id

    def getNameId(self) -> int:  # noqa: N802
        return self.get_name_id()

    def set_name_id(self, value: int) -> None:
        self._name_id = value

    def setNameId(self, value: int) -> None:  # noqa: N802
        self.set_name_id(value)

    def get_string_length(self) -> int:
        return self._string_length

    def getStringLength(self) -> int:  # noqa: N802
        return self.get_string_length()

    def set_string_length(self, value: int) -> None:
        self._string_length = value

    def setStringLength(self, value: int) -> None:  # noqa: N802
        self.set_string_length(value)

    def get_string_offset(self) -> int:
        return self._string_offset

    def getStringOffset(self) -> int:  # noqa: N802
        return self.get_string_offset()

    def set_string_offset(self, value: int) -> None:
        self._string_offset = value

    def setStringOffset(self, value: int) -> None:  # noqa: N802
        self.set_string_offset(value)

    def get_string(self) -> str | None:
        return self._string

    def getString(self) -> str | None:  # noqa: N802
        return self.get_string()

    def set_string(self, value: str | None) -> None:
        self._string = value

    def setString(self, value: str | None) -> None:  # noqa: N802
        self.set_string(value)

    def to_string(self) -> str:
        """Mirror upstream ``NameRecord.toString()``.

        Upstream format (Java lines 186-191):
        ``"platform=" + platformId + " pEncoding=" + platformEncodingId +
        " language=" + languageId + " name=" + nameId + " " + string``.
        """
        return (
            f"platform={self._platform_id} "
            f"pEncoding={self._platform_encoding_id} "
            f"language={self._language_id} "
            f"name={self._name_id} {self._string}"
        )

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return self.to_string()
