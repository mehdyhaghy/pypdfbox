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
        self._unique_id: str | None = None
        self._full_name: str | None = None
        self._version: str | None = None
        self._copyright: str | None = None
        self._trademark: str | None = None

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
            raw = data.read_bytes(nr.get_string_length())
            try:
                string = raw.decode(charset)
            except (UnicodeDecodeError, LookupError):
                # best-effort fallback for unknown Macintosh script codes
                string = raw.decode("latin-1")
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
            NameRecord.ENCODING_WINDOWS_UNICODE_UCS4,
        ):
            return "utf-16-be"
        if platform == NameRecord.PLATFORM_UNICODE:
            return "utf-16-be"
        if platform == NameRecord.PLATFORM_ISO:
            if encoding == 0:
                return "us-ascii"
            if encoding == 1:
                return "utf-16-be"
        if platform == NameRecord.PLATFORM_MACINTOSH:
            # Macintosh script manager codes — encoding 0 = Roman, 1 = Japanese.
            # Python ships ``mac_roman`` and ``shift_jis`` (a superset of MacJapanese
            # for ASCII-only data) — fall back to latin-1 on lookup failure.
            if encoding == NameRecord.ENCODING_MACINTOSH_ROMAN:
                return "mac_roman"
            if encoding == 1:
                return "shift_jis"
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

        self._unique_id = self._get_english_name(NameRecord.NAME_UNIQUE_FONT_ID)
        self._full_name = self._get_english_name(NameRecord.NAME_FULL_FONT_NAME)
        self._version = self._get_english_name(NameRecord.NAME_VERSION)
        self._copyright = self._get_english_name(NameRecord.NAME_COPYRIGHT)
        self._trademark = self._get_english_name(NameRecord.NAME_TRADEMARK)

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

    def get_english_name(self, name_id: int) -> str | None:
        """Return the English-language string for ``name_id``.

        Walks the Unicode platform first (encodings 4 → 0), then Microsoft
        Unicode BMP / English-US, then Macintosh Roman / English. Returns
        ``None`` if no English record is present.
        """
        return self._get_english_name(name_id)

    def get_names_by_id(self, name_id: int) -> list[NameRecord]:
        """Return every record matching ``name_id`` in read order.

        Useful when callers need to enumerate language variants of a single
        name (upstream callers traverse the per-name-id sub-map directly,
        but exposing a list keeps the API ergonomic from Python).
        """
        return [nr for nr in self._name_records if nr.get_name_id() == name_id]

    def get_name(
        self,
        name_id: int,
        platform_id: int | None = None,
        encoding_id: int | None = None,
        language_id: int | None = None,
    ) -> str | None:
        """Look up a string by name id.

        With only ``name_id`` supplied, mirrors upstream's ``getName(int)`` —
        prefers the Microsoft Unicode BMP (English-US) record, then falls back
        to other Microsoft Unicode languages, then Unicode platform, then
        Macintosh Roman English.

        With all four ids supplied, mirrors upstream's
        ``getName(int, int, int, int)``.
        """
        if platform_id is None and encoding_id is None and language_id is None:
            return self._get_name_by_id(name_id)
        if platform_id is None or encoding_id is None or language_id is None:
            raise TypeError(
                "get_name(name_id, ...) requires either name_id alone or all four ids"
            )
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

    def _get_name_by_id(self, name_id: int) -> str | None:
        # Microsoft Unicode BMP, English-US — preferred.
        v = self.get_name(
            name_id,
            NameRecord.PLATFORM_WINDOWS,
            NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
            NameRecord.LANGUAGE_WINDOWS_EN_US,
        )
        if v is not None:
            return v
        # Microsoft Unicode BMP, any other language.
        platforms = self._lookup_table.get(name_id)
        if platforms is not None:
            ms_encodings = platforms.get(NameRecord.PLATFORM_WINDOWS)
            if ms_encodings is not None:
                ms_langs = ms_encodings.get(NameRecord.ENCODING_WINDOWS_UNICODE_BMP)
                if ms_langs:
                    for lang_id, value in ms_langs.items():
                        if value is not None and lang_id != NameRecord.LANGUAGE_WINDOWS_EN_US:
                            return value
        # Unicode platform.
        for enc in (
            NameRecord.ENCODING_UNICODE_2_0_FULL,
            NameRecord.ENCODING_UNICODE_2_0_BMP,
            NameRecord.ENCODING_UNICODE_1_1,
            NameRecord.ENCODING_UNICODE_1_0,
        ):
            v = self.get_name(
                name_id,
                NameRecord.PLATFORM_UNICODE,
                enc,
                NameRecord.LANGUAGE_UNICODE,
            )
            if v is not None:
                return v
        # Macintosh Roman English.
        return self.get_name(
            name_id,
            NameRecord.PLATFORM_MACINTOSH,
            NameRecord.ENCODING_MACINTOSH_ROMAN,
            NameRecord.LANGUAGE_MACINTOSH_ENGLISH,
        )

    def get_name_records(self) -> list[NameRecord]:
        return self._name_records

    def get_font_family(self) -> str | None:
        return self._font_family

    def get_font_sub_family(self) -> str | None:
        return self._font_sub_family

    def get_post_script_name(self) -> str | None:
        return self._ps_name

    def get_unique_id(self) -> str | None:
        return self._unique_id

    def get_full_name(self) -> str | None:
        return self._full_name

    def get_version(self) -> str | None:
        return self._version

    def get_copyright(self) -> str | None:
        return self._copyright

    def get_trademark(self) -> str | None:
        return self._trademark
