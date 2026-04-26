from __future__ import annotations

from typing import TYPE_CHECKING

from .name_record import NameRecord
from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class NamingTable(TTFTable):
    """``name`` — required TrueType table. Mirrors upstream."""

    TAG: str = "name"

    def __init__(self) -> None:
        super().__init__()
        self._name_records: list[NameRecord] = []
        self._lookup_table: dict[int, dict[int, dict[int, dict[int, str | None]]]] = {}
        self._font_family: str | None = None
        self._font_sub_family: str | None = None
        self._ps_name: str | None = None

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        format_selector = data.read_unsigned_short()  # noqa: F841
        number_of_name_records = data.read_unsigned_short()
        offset_to_start_of_string_storage = data.read_unsigned_short()  # noqa: F841

        self._name_records = []
        for _i in range(number_of_name_records):
            nr = NameRecord()
            nr.init_data(ttf, data)
            self._name_records.append(nr)

        for nr in self._name_records:
            # don't try to read invalid offsets — see PDFBOX-2608
            if nr.get_string_offset() > self.get_length():
                nr.set_string(None)
                continue

            data.seek(
                self.get_offset()
                + (2 * 3)
                + number_of_name_records * 2 * 6
                + nr.get_string_offset()
            )
            charset = self._charset_for(nr)
            string = data.read_string(nr.get_string_length(), charset)
            nr.set_string(string)

        self._lookup_table = {}
        self._fill_lookup_table()
        self._read_interesting_strings()
        self.initialized = True

    @staticmethod
    def _charset_for(nr: NameRecord) -> str:
        platform = nr.get_platform_id()
        encoding = nr.get_platform_encoding_id()
        if platform == NameRecord.PLATFORM_WINDOWS and encoding in (
            NameRecord.ENCODING_WINDOWS_SYMBOL,
            NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
        ):
            return "utf-16-be"
        if platform == NameRecord.PLATFORM_UNICODE:
            return "utf-16-be"
        if platform == NameRecord.PLATFORM_ISO:
            if encoding == 0:
                return "us-ascii"
            if encoding == 1:
                return "utf-16-be"
        return "iso-8859-1"

    def _fill_lookup_table(self) -> None:
        for nr in self._name_records:
            platform_lookup = self._lookup_table.setdefault(nr.get_name_id(), {})
            encoding_lookup = platform_lookup.setdefault(nr.get_platform_id(), {})
            language_lookup = encoding_lookup.setdefault(nr.get_platform_encoding_id(), {})
            language_lookup[nr.get_language_id()] = nr.get_string()

    def _read_interesting_strings(self) -> None:
        self._font_family = self._get_english_name(NameRecord.NAME_FONT_FAMILY_NAME)
        self._font_sub_family = self._get_english_name(NameRecord.NAME_FONT_SUB_FAMILY_NAME)

        ps_name = self.get_name(
            NameRecord.NAME_POSTSCRIPT_NAME,
            NameRecord.PLATFORM_MACINTOSH,
            NameRecord.ENCODING_MACINTOSH_ROMAN,
            NameRecord.LANGUAGE_MACINTOSH_ENGLISH,
        )
        if ps_name is None:
            ps_name = self.get_name(
                NameRecord.NAME_POSTSCRIPT_NAME,
                NameRecord.PLATFORM_WINDOWS,
                NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
                NameRecord.LANGUAGE_WINDOWS_EN_US,
            )
        self._ps_name = ps_name.strip() if ps_name is not None else None

    def _get_english_name(self, name_id: int) -> str | None:
        # try Unicode platform first (Full, BMP, 1.1, 1.0)
        for i in range(4, -1, -1):
            v = self.get_name(
                name_id,
                NameRecord.PLATFORM_UNICODE,
                i,
                NameRecord.LANGUAGE_UNICODE,
            )
            if v is not None:
                return v
        v = self.get_name(
            name_id,
            NameRecord.PLATFORM_WINDOWS,
            NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
            NameRecord.LANGUAGE_WINDOWS_EN_US,
        )
        if v is not None:
            return v
        return self.get_name(
            name_id,
            NameRecord.PLATFORM_MACINTOSH,
            NameRecord.ENCODING_MACINTOSH_ROMAN,
            NameRecord.LANGUAGE_MACINTOSH_ENGLISH,
        )

    def get_name(
        self,
        name_id: int,
        platform_id: int,
        encoding_id: int,
        language_id: int,
    ) -> str | None:
        platforms = self._lookup_table.get(name_id)
        if platforms is None:
            return None
        encodings = platforms.get(platform_id)
        if encodings is None:
            return None
        languages = encodings.get(encoding_id)
        if languages is None:
            return None
        return languages.get(language_id)

    def get_name_records(self) -> list[NameRecord]:
        return self._name_records

    def get_font_family(self) -> str | None:
        return self._font_family

    def get_font_sub_family(self) -> str | None:
        return self._font_sub_family

    def get_post_script_name(self) -> str | None:
        return self._ps_name
