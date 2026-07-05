from __future__ import annotations

from typing import TYPE_CHECKING

from .name_record import NameRecord
from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream
    from .ttf_parser import FontHeaders


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
        """Read the ``name`` table.

        Mirrors upstream ``NamingTable#read(TrueTypeFont, TTFDataStream)``
        (NamingTable.java line 59).
        """
        self._read(ttf, data, only_headers=False)
        self.initialized = True

    def read_headers(
        self,
        ttf: TrueTypeFont,
        data: TTFDataStream,
        out_headers: FontHeaders,
    ) -> None:
        """Populate ``out_headers`` with the PostScript name and font family /
        sub-family.

        Mirrors upstream ``NamingTable#readHeaders`` (NamingTable.java
        line 67) — the ``FileSystemFontProvider`` fast path uses this to skip
        decoding records that aren't useful for header-only metadata.
        """
        self._read(ttf, data, only_headers=True)
        out_headers.set_name(self._ps_name)
        out_headers.set_font_family(self._font_family, self._font_sub_family)

    def _read(
        self,
        ttf: TrueTypeFont,
        data: TTFDataStream,
        only_headers: bool,  # noqa: FBT001 — upstream private overload
    ) -> None:
        data.read_unsigned_short()  # format selector
        number_of_name_records = data.read_unsigned_short()
        data.read_unsigned_short()  # declared string-storage offset — unused upstream

        self._name_records = []
        for _i in range(number_of_name_records):
            nr = NameRecord()
            nr.init_data(ttf, data)
            if not only_headers or self.is_useful_for_only_headers(nr):
                self._name_records.append(nr)

        for nr in self._name_records:
            # Don't try to read invalid offsets — see PDFBOX-2608. Upstream
            # guards ONLY the record's raw string offset against the table
            # length (NamingTable.java line 93); it does not clamp
            # offset+length, so a string that starts inside the table but
            # runs past its end is read from whatever file bytes follow,
            # and a read past EOF propagates (``OSError``, mirroring the
            # Java ``IOException`` that fails the whole parse).
            if nr.get_string_offset() > self.get_length():
                nr.set_string(None)
                continue

            # The string storage base is COMPUTED as the end of the record
            # array — 6 header bytes + 12 bytes per declared record — from
            # the table start (NamingTable.java line 99). The header's
            # declared storage offset is ignored, even when it differs
            # (oracle-verified against PDFBox 3.0.7, wave 1598).
            data.seek(
                self.get_offset()
                + 2 * 3
                + number_of_name_records * 2 * 6
                + nr.get_string_offset()
            )
            charset = self._charset_for(nr)
            raw = data.read_bytes(nr.get_string_length())
            try:
                string = self._decode_string(raw, charset)
            except LookupError:
                # best-effort fallback for monkeypatched unknown codec names
                string = raw.decode("latin-1")
            nr.set_string(string)

        self._lookup_table = {}
        self.fill_lookup_table()
        self.read_interesting_strings()

    @staticmethod
    def get_charset(nr: NameRecord) -> str:
        """Return the Python codec name to decode ``nr``'s raw bytes with.

        Mirrors upstream ``NamingTable#getCharset`` (NamingTable.java
        line 110), expressed in Python codec strings rather than
        ``java.nio.charset.Charset`` instances.

        Behaviour matches upstream PDFBox 3.0.7 exactly (oracle-verified
        against the 3.0.7 bytecode + live probe, wave 1598):

        * platform=3 (Windows) encoding 0 (Symbol) / 1 (Unicode BMP) →
          ``"utf-16"``, meaning Java's ``StandardCharsets.UTF_16``: a
          leading BOM is consumed and selects the byte order; without a
          BOM the decode is BIG-endian (``_decode_string`` implements
          this — Python's bare ``utf-16`` codec would default to
          little-endian). Encoding 10 (UCS-4) is **not** special-cased
          upstream and falls through to Latin-1.
        * platform=0 (Unicode) → ``"utf-16"`` (any encoding).
        * platform=2 (ISO) encoding 0 → US-ASCII; encoding 1 →
          ``"utf-16-be"`` — the *strict* big-endian charset: a BOM is NOT
          consumed and surfaces as U+FEFF/U+FFFE in the decoded string,
          exactly like Java's ``StandardCharsets.UTF_16BE``.
        * **everything else, including platform=1 (Macintosh)** →
          ISO-8859-1 (Latin-1). Upstream does NOT decode Macintosh records
          as ``MacRoman``; this surfaces as a parity-visible byte at e.g.
          ``0xAA`` (Latin-1 ``ª`` vs Mac-Roman ``™``) in NID 10 of
          ``LiberationSans-Regular``. PDFBox itself has chosen the Latin-1
          decode, so the port mirrors it — see wave 1449 ``NameTableProbe``
          differential parity.
        """
        platform = nr.get_platform_id()
        encoding = nr.get_platform_encoding_id()
        if platform == NameRecord.PLATFORM_WINDOWS and encoding in (
            NameRecord.ENCODING_WINDOWS_SYMBOL,
            NameRecord.ENCODING_WINDOWS_UNICODE_BMP,
        ):
            return "utf-16"
        if platform == NameRecord.PLATFORM_UNICODE:
            return "utf-16"
        if platform == NameRecord.PLATFORM_ISO:
            if encoding == 0:
                return "us-ascii"
            if encoding == 1:
                return "utf-16-be"
        # platform=1 (Macintosh), Windows encoding 10 (UCS-4) and every
        # other unrecognised combination falls through to the upstream
        # default — Latin-1 / ISO-8859-1.
        return "iso-8859-1"

    @classmethod
    def _charset_for(cls, nr: NameRecord) -> str:
        """Backwards-compatible alias kept so historical monkeypatch fixtures
        continue to override the codec lookup. Prefer :meth:`get_charset`."""
        return cls.get_charset(nr)

    @staticmethod
    def _decode_string(raw: bytes, charset: str) -> str:
        """Decode ``raw`` with Java charset semantics.

        ``"utf-16"`` reproduces ``java.nio.charset.StandardCharsets.UTF_16``:
        a leading BOM is consumed and selects the byte order; without a BOM
        the input decodes as big-endian (Python's bare ``utf-16`` codec
        defaults to little-endian, so the no-BOM case is routed through
        ``utf-16-be`` explicitly). Every other codec — including strict
        ``"utf-16-be"``, which retains a BOM as U+FEFF/U+FFFE — decodes
        directly. Malformed input is replaced (U+FFFD), matching Java's
        ``new String(bytes, charset)``.
        """
        if charset == "utf-16":
            if raw.startswith(b"\xfe\xff"):
                return NamingTable._decode_utf16_units(raw[2:], big_endian=True)
            if raw.startswith(b"\xff\xfe"):
                return NamingTable._decode_utf16_units(raw[2:], big_endian=False)
            return NamingTable._decode_utf16_units(raw, big_endian=True)
        if charset == "utf-16-be":
            return NamingTable._decode_utf16_units(raw, big_endian=True)
        return raw.decode(charset, errors="replace")

    @staticmethod
    def _decode_utf16_units(raw: bytes, *, big_endian: bool) -> str:
        """UTF-16 code-unit decode with Java ``CharsetDecoder`` malformed
        handling.

        Java's decoder replaces a high surrogate AND the following
        (non-low-surrogate) code unit with ONE U+FFFD — a 4-byte malformed
        sequence — where Python's built-in codec replaces only the high
        surrogate's two bytes and resumes at the next unit. E.g.
        ``D8 00 00 41`` decodes to ``\\ufffd`` in Java but ``\\ufffdA``
        via the Python codec (oracle-verified, wave 1598). A high
        surrogate with fewer than two bytes left swallows the remainder
        into one U+FFFD; a lone LOW surrogate replaces only itself; a
        trailing odd byte becomes one U+FFFD.
        """
        out: list[str] = []
        i = 0
        n = len(raw)
        while i + 1 < n:
            unit = (raw[i] << 8) | raw[i + 1] if big_endian else (raw[i + 1] << 8) | raw[i]
            if 0xD800 <= unit <= 0xDBFF:
                if i + 3 < n:
                    if big_endian:
                        unit2 = (raw[i + 2] << 8) | raw[i + 3]
                    else:
                        unit2 = (raw[i + 3] << 8) | raw[i + 2]
                    if 0xDC00 <= unit2 <= 0xDFFF:
                        out.append(
                            chr(0x10000 + ((unit - 0xD800) << 10) + (unit2 - 0xDC00))
                        )
                    else:
                        # Java consumes BOTH units as one malformed sequence.
                        out.append("�")
                    i += 4
                else:
                    # high surrogate with <2 bytes left: the remainder
                    # collapses into a single replacement char.
                    out.append("�")
                    i = n
            elif 0xDC00 <= unit <= 0xDFFF:
                out.append("�")
                i += 2
            else:
                out.append(chr(unit))
                i += 2
        if i < n:
            out.append("�")
        return "".join(out)

    @staticmethod
    def _java_trim(value: str) -> str:
        """Mirror ``java.lang.String.trim()``: strip leading/trailing chars
        with code point <= U+0020 (which includes NUL and other C0
        controls but — unlike Python ``str.strip()`` — NOT Unicode
        whitespace such as U+00A0)."""
        start = 0
        end = len(value)
        while start < end and value[start] <= " ":
            start += 1
        while end > start and value[end - 1] <= " ":
            end -= 1
        return value[start:end]

    def fill_lookup_table(self) -> None:
        """Build the ``(name, platform, encoding, language) → string`` lookup.

        Mirrors upstream ``NamingTable#fillLookupTable`` (NamingTable.java
        line 141).
        """
        for nr in self._name_records:
            platform_lookup = self._lookup_table.setdefault(nr.get_name_id(), {})
            encoding_lookup = platform_lookup.setdefault(nr.get_platform_id(), {})
            language_lookup = encoding_lookup.setdefault(nr.get_platform_encoding_id(), {})
            language_lookup[nr.get_language_id()] = nr.get_string()

    def _fill_lookup_table(self) -> None:
        """Backwards-compatible alias for :meth:`fill_lookup_table`."""
        self.fill_lookup_table()

    def read_interesting_strings(self) -> None:
        """Cache the family / sub-family / PostScript name etc. for fast access.

        Mirrors upstream ``NamingTable#readInterestingStrings``
        (NamingTable.java line 157).
        """
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
        # Upstream trims with String.trim() — Java-trim, not Python strip.
        self._ps_name = self._java_trim(ps_name) if ps_name is not None else None

        self._unique_id = self._get_english_name(NameRecord.NAME_UNIQUE_FONT_ID)
        self._full_name = self._get_english_name(NameRecord.NAME_FULL_FONT_NAME)
        self._version = self._get_english_name(NameRecord.NAME_VERSION)
        self._copyright = self._get_english_name(NameRecord.NAME_COPYRIGHT)
        self._trademark = self._get_english_name(NameRecord.NAME_TRADEMARK)

    def _read_interesting_strings(self) -> None:
        """Backwards-compatible alias for :meth:`read_interesting_strings`."""
        self.read_interesting_strings()

    @staticmethod
    def is_useful_for_only_headers(nr: NameRecord) -> bool:
        """Filter for ``read_headers``: keep only the records consulted by
        :meth:`read_interesting_strings` so the header-only fast path can
        skip decoding everything else.

        Mirrors upstream ``NamingTable#isUsefulForOnlyHeaders``
        (NamingTable.java line 181).
        """
        name_id = nr.get_name_id()
        if name_id in (
            NameRecord.NAME_POSTSCRIPT_NAME,
            NameRecord.NAME_FONT_FAMILY_NAME,
            NameRecord.NAME_FONT_SUB_FAMILY_NAME,
        ):
            language_id = nr.get_language_id()
            return language_id in (
                NameRecord.LANGUAGE_UNICODE,
                NameRecord.LANGUAGE_WINDOWS_EN_US,
            )
        return False

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

    def iter_name_records(self) -> list[NameRecord]:
        """Alias for :meth:`get_name_records` returning a fresh list copy.

        Upstream returns the live ``ArrayList`` from ``getNameRecords``;
        a copy here makes per-call mutation safe for Python callers that
        accidentally append.
        """
        return list(self._name_records)

    def get_font_family(self, language_id: int | None = None) -> str | None:
        """Font family name. With no argument, returns the English-language
        record (Unicode platform → Microsoft Unicode BMP en-US → Macintosh
        Roman English). With ``language_id`` supplied, looks up the record
        in any platform under that language id, or returns ``None`` if no
        such record exists."""
        if language_id is None:
            return self._font_family
        return self._lookup_by_language(NameRecord.NAME_FONT_FAMILY_NAME, language_id)

    def get_font_sub_family(self, language_id: int | None = None) -> str | None:
        if language_id is None:
            return self._font_sub_family
        return self._lookup_by_language(
            NameRecord.NAME_FONT_SUB_FAMILY_NAME, language_id
        )

    def get_post_script_name(self, language_id: int | None = None) -> str | None:
        if language_id is None:
            return self._ps_name
        v = self._lookup_by_language(NameRecord.NAME_POSTSCRIPT_NAME, language_id)
        return self._java_trim(v) if v is not None else None

    def get_unique_id(self, language_id: int | None = None) -> str | None:
        if language_id is None:
            return self._unique_id
        return self._lookup_by_language(NameRecord.NAME_UNIQUE_FONT_ID, language_id)

    def get_full_name(self, language_id: int | None = None) -> str | None:
        if language_id is None:
            return self._full_name
        return self._lookup_by_language(NameRecord.NAME_FULL_FONT_NAME, language_id)

    def get_version(self, language_id: int | None = None) -> str | None:
        if language_id is None:
            return self._version
        return self._lookup_by_language(NameRecord.NAME_VERSION, language_id)

    def get_copyright(self, language_id: int | None = None) -> str | None:
        if language_id is None:
            return self._copyright
        return self._lookup_by_language(NameRecord.NAME_COPYRIGHT, language_id)

    def get_trademark(self, language_id: int | None = None) -> str | None:
        if language_id is None:
            return self._trademark
        return self._lookup_by_language(NameRecord.NAME_TRADEMARK, language_id)

    # ---- language / record discovery (no upstream equivalent — additions) ----

    def language_records(self, name_id: int) -> list[NameRecord]:
        """Every :class:`NameRecord` for ``name_id`` in read order.

        Mirrors upstream callers that traverse
        ``lookupTable.get(nameId)`` to enumerate language variants of one
        name; this returns the underlying records so the platform /
        encoding / language ids remain accessible on each entry.
        """
        return [nr for nr in self._name_records if nr.get_name_id() == name_id]

    def language_ids(self, name_id: int) -> list[int]:
        """Distinct ``language_id`` values present for ``name_id``."""
        seen: list[int] = []
        for nr in self._name_records:
            if nr.get_name_id() != name_id:
                continue
            lid = nr.get_language_id()
            if lid not in seen:
                seen.append(lid)
        return seen

    def name_ids(self) -> list[int]:
        """Sorted list of distinct ``name_id`` values present in this table.
        Useful for tools that enumerate everything the font advertises
        (translators, font inspectors)."""
        return sorted(self._lookup_table.keys())

    def has_name(
        self,
        name_id: int,
        platform_id: int | None = None,
        encoding_id: int | None = None,
        language_id: int | None = None,
    ) -> bool:
        """``True`` if a record exists matching the supplied ids. With
        only ``name_id`` supplied, returns ``True`` if any record carries
        that name id."""
        if platform_id is None and encoding_id is None and language_id is None:
            return name_id in self._lookup_table
        return self.get_name(name_id, platform_id, encoding_id, language_id) is not None

    def _lookup_by_language(self, name_id: int, language_id: int) -> str | None:
        """Search every (platform, encoding) for a record matching
        ``(name_id, language_id)``; return its decoded string or ``None``."""
        platforms = self._lookup_table.get(name_id)
        if platforms is None:
            return None
        for encodings in platforms.values():
            for languages in encodings.values():
                if language_id in languages:
                    v = languages[language_id]
                    if v is not None:
                        return v
        return None
