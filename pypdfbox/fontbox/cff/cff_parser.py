from __future__ import annotations

import io
import struct
from typing import Any

from .byte_source import ByteSource
from .cff_cid_font import CFFCIDFont
from .cff_font import CFFFont
from .cff_type1_font import CFFType1Font
from .data_input import DataInput
from .data_input_byte_array import DataInputByteArray
from .dict_data import DictData
from .dict_data import Entry as _DictEntry
from .header import Header


class _BytesSource(ByteSource):
    """Default :class:`ByteSource` implementation backed by an in-memory
    ``bytes`` buffer.

    Mirrors upstream ``CFFBytesource`` (``CFFParser.java`` lines
    1713-1727); upstream this is package-private. We keep it module-
    private (underscore-prefixed). Subclasses :class:`ByteSource` from
    ``byte_source.py`` so isinstance checks work uniformly."""

    def __init__(self, data: bytes | bytearray | memoryview) -> None:
        self._data = bytes(data)

    def get_bytes(self) -> bytes:
        return self._data


class CFFParser:
    """Top-level CFF font parser.

    Mirrors the public surface of upstream
    ``org.apache.fontbox.cff.CFFParser`` (``CFFParser.java`` lines
    39-1734). Method names are snake_cased per project rules.

    Library-first: rather than reimplementing CFF binary parsing
    (header / INDEX / DICT / charstrings / charsets / encodings /
    FDSelect — upstream is ~1700 lines for this), we delegate to
    ``fontTools.cffLib.CFFFontSet`` (MIT). fontTools is the de-facto
    Python reference for OpenType / CFF; it covers all three charset
    formats, both encoding formats with supplement, both FDSelect
    formats, and the full DICT operator table — exactly the surface
    upstream re-implements by hand.

    The parser then lifts the fontTools-decompiled font set into
    pypdfbox's own :class:`CFFFont` / :class:`CFFType1Font` /
    :class:`CFFCIDFont` wrappers (constructed via :meth:`from_bytes`)
    so callers see the upstream class hierarchy.

    Each upstream private helper (``readHeader``, ``readIndexData``,
    ``readDictData``, ``readEncoding``, ``readCharset``, ``readFDSelect``
    and friends) gets a Python mirror below. The ``parse_*`` /
    ``read_*`` family operate on a :class:`DataInput` exactly like
    upstream so callers porting from Java keep a familiar surface.
    """

    def __init__(self) -> None:
        self._source: ByteSource | None = None
        self._debug_font_name: str | None = None
        # Mirrors upstream's mutable ``stringIndex`` field
        # (``CFFParser.java`` line 50). Populated by ``parse_*`` /
        # ``parse_first_sub_font_ros`` and consulted by ``read_string``.
        self._string_index: list[str] | None = None

    def parse(
        self,
        byte_source: ByteSource | bytes | bytearray | memoryview,
        source: ByteSource | None = None,
    ) -> list[CFFFont]:
        """PDFBox: ``CFFParser.parse(byte[], ByteSource)``
        (``CFFParser.java`` lines 78-83) and
        ``CFFParser.parse(RandomAccessRead)`` (lines 92-107) collapsed
        into one Python overload.

        Accepts either:
          * a raw ``bytes``-like buffer (upstream's first overload), or
          * a :class:`ByteSource`-shaped object whose ``get_bytes()``
            returns the payload (upstream's second overload, where the
            payload is read out of a ``RandomAccessRead`` first).

        ``source``, when supplied, is stored as the ByteSource handed to
        each parsed :class:`CFFFont` (mirrors upstream's
        ``font.setData(source)`` call on line 216).

        Returns the list of parsed :class:`CFFFont` instances — one per
        font in the CFF FontSet's NameINDEX.
        """
        # Resolve the input to a flat ``bytes`` payload and pick the
        # ByteSource we'll attach to each parsed font.
        if isinstance(byte_source, (bytes, bytearray, memoryview)):
            data = bytes(byte_source)
            ext_source: ByteSource = (
                source if source is not None else _BytesSource(data)
            )
        else:
            # Duck-typed ByteSource: must have ``get_bytes()``.
            data = bytes(byte_source.get_bytes())
            ext_source = source if source is not None else byte_source

        self._source = ext_source

        # Library-first: delegate the full CFF binary parse to fontTools.
        # ``CFFFontSet`` handles OTF wrapping (CFF inside an OpenType
        # ``CFF `` table) automatically when the font is exposed via
        # ``TTFont``, but at the raw-bytes layer we strip the OTF
        # wrapper ourselves to mirror upstream's ``skipHeader`` switch
        # on the OTTO / ttcf / TTF tags (``CFFParser.java`` lines
        # 168-180). We forward only the inner ``CFF `` table to
        # fontTools so the ``decompile`` call stays pure-CFF.
        cff_payload = _strip_otf_wrapper(data)
        from fontTools.cffLib import CFFFontSet  # type: ignore[import-untyped]  # noqa: PLC0415

        fontset = CFFFontSet()
        # fontTools validates the CFF binary with bare ``assert`` statements
        # (e.g. ``assert offSize <= 4``) and can raise struct/index/key errors
        # on malformed data. Adapt all of that to the parser's own error type:
        # a raw ``AssertionError`` would surprise callers catching ``OSError``,
        # and — worse — ``python -O`` strips ``assert`` entirely, removing the
        # validation. Mirrors upstream ``CFFParser``, which throws
        # ``IOException`` on a malformed CFF. Our own intentional ``OSError``
        # raises below (missing name index, synthetic fonts) pass through.
        try:
            fontset.decompile(io.BytesIO(cff_payload), otFont=None)

            if not fontset.fontNames:
                msg = "Name index missing in CFF font"
                raise OSError(msg)

            fonts: list[CFFFont] = []
            for name in fontset.fontNames:
                top = fontset[name]
                # Synthetic-base fonts are unsupported (upstream raises in
                # ``parseFont``, ``CFFParser.java`` lines 557-561). fontTools
                # surfaces the operator on the raw Top DICT.
                raw = getattr(top, "rawDict", {})
                if "SyntheticBase" in raw:
                    msg = "Synthetic Fonts are not supported"
                    raise OSError(msg)

                # Pick the upstream subtype: ROS present → CIDKeyed, else
                # name-keyed Type 1 (mirrors ``CFFParser.parseFont``,
                # ``CFFParser.java`` lines 564-574).
                base = CFFFont.from_bytes(cff_payload)
                # ``from_bytes`` always picks the first font in the set.
                # When the set has multiple fonts (rare for /FontFile3) we
                # re-point ``_top`` to the named one to preserve upstream's
                # one-CFFFont-per-NameINDEX-entry contract.
                base._top = top
                font: CFFFont
                if base.is_cid_font():
                    font = CFFCIDFont.from_cff_font(base)
                else:
                    font = CFFType1Font.from_cff_font(base)
                font.set_name(name)
                font.set_data(cff_payload)
                # GSubrs are shared across the whole FontSet — pull them
                # from the parsed Top DICT and propagate (mirrors
                # ``font.setGlobalSubrIndex(globalSubrIndex)``,
                # ``CFFParser.java`` line 215).
                font.set_global_subr_index(font.get_global_subr_index())
                self._debug_font_name = name
                fonts.append(font)
        except OSError:
            raise
        except Exception as exc:  # noqa: BLE001 - adapt fontTools failure modes
            raise OSError(f"Invalid CFF font data: {exc}") from exc

        return fonts

    def parse_first_sub_font_ros(
        self,
        random_access_read: ByteSource | bytes | bytearray | memoryview,
        out_headers: Any,
    ) -> None:
        """PDFBox: ``CFFParser.parseFirstSubFontROS``
        (``CFFParser.java`` lines 117-162). Extracts ``Registry``,
        ``Ordering`` and ``Supplement`` from the first CFF subfont and
        pushes them into ``out_headers`` (a ``FontHeaders``-shaped
        object exposing ``set_error`` / ``set_otf_ros``).

        Library-first: we reuse ``parse`` to do the heavy lifting and
        then lift the ROS off the first :class:`CFFCIDFont`.
        """
        try:
            fonts = self.parse(random_access_read)
        except OSError as err:
            if hasattr(out_headers, "set_error"):
                out_headers.set_error(str(err))
            return

        if not fonts:
            if hasattr(out_headers, "set_error"):
                out_headers.set_error("Name index missing in CFF font")
            return

        first = fonts[0]
        if isinstance(first, CFFCIDFont) and hasattr(out_headers, "set_otf_ros"):
            out_headers.set_otf_ros(
                first.get_registry(),
                first.get_ordering(),
                first.get_supplement(),
            )

    # ------------------------------------------------------------------
    # Top-level binary readers (skipHeader / createTaggedCFFDataInput).
    # Mirrors upstream so direct ports of Java callers retain the same
    # surface; the in-process ``parse`` above already uses the
    # higher-level ``_strip_otf_wrapper`` helper.
    # ------------------------------------------------------------------

    def skip_header(self, input_: DataInput) -> DataInput:
        """PDFBox: ``CFFParser.skipHeader``
        (``CFFParser.java`` lines 164-185). Branches on the leading
        4-byte tag (``OTTO`` / ``ttcf`` / ``\\x00\\x01\\x00\\x00``) and
        rewinds plain CFF streams. Returns the (possibly inner) input
        positioned after the CFF header."""
        first_tag = self.read_tag_name(input_)
        if first_tag == "OTTO":
            input_ = self.create_tagged_cff_data_input(input_)
        elif first_tag == "ttcf":
            msg = "True Type Collection fonts are not supported."
            raise OSError(msg)
        elif first_tag == "\x00\x01\x00\x00":
            msg = "OpenType fonts containing a true type font are not supported."
            raise OSError(msg)
        else:
            input_.set_position(0)
        # Consume the 4-byte CFF header so callers land on the NameINDEX.
        self.read_header(input_)
        return input_

    def create_tagged_cff_data_input(self, input_: DataInput) -> DataInput:
        """PDFBox: ``CFFParser.createTaggedCFFDataInput``
        (``CFFParser.java`` lines 222-248). Walks the OpenType table
        directory and returns a fresh :class:`DataInputByteArray`
        wrapping the inner ``CFF `` table bytes."""
        num_tables = input_.read_unsigned_short()
        # searchRange / entrySelector / rangeShift — upstream reads and
        # discards (lines 228-232). We mirror the consumption.
        input_.read_unsigned_short()
        input_.read_unsigned_short()
        input_.read_unsigned_short()
        for _ in range(num_tables):
            tag_name = self.read_tag_name(input_)
            self.read_long(input_)  # checksum (discarded)
            offset = self.read_long(input_)
            length = self.read_long(input_)
            if tag_name == "CFF ":
                input_.set_position(int(offset))
                bytes2 = input_.read_bytes(int(length))
                return DataInputByteArray(bytes2)
        msg = "CFF tag not found in this OpenType font."
        raise OSError(msg)

    # ------------------------------------------------------------------
    # Static byte-stream helpers — direct ports. These are pure DataInput
    # operations; using the upstream algorithms verbatim is simpler and
    # safer than wrapping fontTools.
    # ------------------------------------------------------------------

    @staticmethod
    def read_tag_name(input_: DataInput) -> str:
        """PDFBox: ``CFFParser.readTagName``
        (``CFFParser.java`` lines 250-254). 4 ISO-8859-1 bytes."""
        b = input_.read_bytes(4)
        return bytes(b).decode("iso-8859-1")

    @staticmethod
    def read_long(input_: DataInput) -> int:
        """PDFBox: ``CFFParser.readLong``
        (``CFFParser.java`` lines 256-259). Two big-endian unsigned
        shorts shifted into a 32-bit value."""
        return (input_.read_unsigned_short() << 16) | input_.read_unsigned_short()

    @staticmethod
    def read_off_size(input_: DataInput) -> int:
        """PDFBox: ``CFFParser.readOffSize``
        (``CFFParser.java`` lines 261-270). Validates the OffSize byte
        is in [1, 4]."""
        off_size = input_.read_unsigned_byte()
        if off_size < 1 or off_size > 4:
            msg = (
                f"Illegal (< 1 or > 4) offSize value {off_size}"
                f" in CFF font at position {input_.get_position() - 1}"
            )
            raise OSError(msg)
        return off_size

    @staticmethod
    def read_header(input_: DataInput) -> Header:
        """PDFBox: ``CFFParser.readHeader``
        (``CFFParser.java`` lines 272-279). Reads major / minor /
        hdrSize / offSize bytes into a :class:`Header`."""
        major = input_.read_unsigned_byte()
        minor = input_.read_unsigned_byte()
        hdr_size = input_.read_unsigned_byte()
        off_size = CFFParser.read_off_size(input_)
        return Header(major, minor, hdr_size, off_size)

    @staticmethod
    def read_index_data_offsets(input_: DataInput) -> list[int]:
        """PDFBox: ``CFFParser.readIndexDataOffsets``
        (``CFFParser.java`` lines 281-300). Returns the count+1 offsets
        for an INDEX, or an empty list if count is 0."""
        count = input_.read_unsigned_short()
        if count == 0:
            return []
        off_size = CFFParser.read_off_size(input_)
        offsets: list[int] = []
        for _ in range(count + 1):
            offset = input_.read_offset(off_size)
            if offset > input_.length():
                msg = f"illegal offset value {offset} in CFF font"
                raise OSError(msg)
            offsets.append(offset)
        return offsets

    @staticmethod
    def read_index_data(input_: DataInput) -> list[bytes]:
        """PDFBox: ``CFFParser.readIndexData``
        (``CFFParser.java`` lines 302-317). Returns the per-entry byte
        slices of an INDEX."""
        offsets = CFFParser.read_index_data_offsets(input_)
        if not offsets:
            return []
        count = len(offsets) - 1
        index_data: list[bytes] = []
        for i in range(count):
            length = offsets[i + 1] - offsets[i]
            index_data.append(bytes(input_.read_bytes(length)))
        return index_data

    @staticmethod
    def read_string_index_data(input_: DataInput) -> list[str]:
        """PDFBox: ``CFFParser.readStringIndexData``
        (``CFFParser.java`` lines 319-340). Returns the INDEX as ISO-
        8859-1 decoded strings."""
        offsets = CFFParser.read_index_data_offsets(input_)
        if not offsets:
            return []
        count = len(offsets) - 1
        values: list[str] = []
        for i in range(count):
            length = offsets[i + 1] - offsets[i]
            if length < 0:
                msg = (
                    f"Negative index data length + {length} at {i}: "
                    f"offsets[{i + 1}]={offsets[i + 1]}, "
                    f"offsets[{i}]={offsets[i]}"
                )
                raise OSError(msg)
            values.append(bytes(input_.read_bytes(length)).decode("iso-8859-1"))
        return values

    # ------------------------------------------------------------------
    # DICT readers
    # ------------------------------------------------------------------

    @staticmethod
    def read_dict_data(
        input_: DataInput,
        offset: int | None = None,
        dict_size: int | None = None,
    ) -> DictData:
        """PDFBox: ``CFFParser.readDictData`` — both overloads
        collapsed (``CFFParser.java`` lines 342-366). With no
        ``offset``/``dict_size`` reads to EOF; otherwise reads the
        given window."""
        dict_ = DictData()
        if offset is None and dict_size is None:
            while input_.has_remaining():
                dict_.add(CFFParser.read_entry(input_))
            return dict_
        if dict_size is not None and dict_size > 0 and offset is not None:
            input_.set_position(offset)
            end_position = offset + dict_size
            while input_.get_position() < end_position:
                dict_.add(CFFParser.read_entry(input_))
        return dict_

    @staticmethod
    def read_entry(input_: DataInput) -> Any:
        """PDFBox: ``CFFParser.readEntry``
        (``CFFParser.java`` lines 368-398). Reads a single
        operator/operands DICT entry."""
        entry = _DictEntry()
        while True:
            b0 = input_.read_unsigned_byte()
            if 0 <= b0 <= 21:
                entry.operator_name = CFFParser.read_operator(input_, b0)
                break
            if b0 in (28, 29):
                entry.add_operand(CFFParser.read_integer_number(input_, b0))
            elif b0 == 30:
                entry.add_operand(CFFParser.read_real_number(input_))
            elif 32 <= b0 <= 254:
                entry.add_operand(CFFParser.read_integer_number(input_, b0))
            else:
                msg = f"invalid DICT data b0 byte: {b0}"
                raise OSError(msg)
        return entry

    @staticmethod
    def read_operator(input_: DataInput, b0: int) -> str | None:
        """PDFBox: ``CFFParser.readOperator``
        (``CFFParser.java`` lines 400-409). Resolves the (possibly
        two-byte ``12 xx``) operator code through CFFOperator."""
        from .cff_operator import CFFOperator  # noqa: PLC0415

        if b0 == 12:
            b1 = input_.read_unsigned_byte()
            return CFFOperator.get_operator(b0, b1)
        return CFFOperator.get_operator(b0)

    @staticmethod
    def read_integer_number(input_: DataInput, b0: int) -> int:
        """PDFBox: ``CFFParser.readIntegerNumber``
        (``CFFParser.java`` lines 411-439). Decodes a CFF DICT integer
        per Table 3 in the CFF spec."""
        if b0 == 28:
            return input_.read_short()
        if b0 == 29:
            return input_.read_int()
        if 32 <= b0 <= 246:
            return b0 - 139
        if 247 <= b0 <= 250:
            b1 = input_.read_unsigned_byte()
            return (b0 - 247) * 256 + b1 + 108
        if 251 <= b0 <= 254:
            b1 = input_.read_unsigned_byte()
            return -(b0 - 251) * 256 - b1 - 108
        raise ValueError

    @staticmethod
    def read_real_number(input_: DataInput) -> float:
        """PDFBox: ``CFFParser.readRealNumber``
        (``CFFParser.java`` lines 441-526). Decodes the BCD-style real
        number stream (nibbles 0-9, ``.``, ``E``/``E-``, ``-``,
        end-marker ``0xF``)."""
        sb: list[str] = []
        done = False
        exponent_missing = False
        has_exponent = False
        while not done:
            b = input_.read_unsigned_byte()
            nibbles = (b // 16, b % 16)
            for nibble in nibbles:
                if 0x0 <= nibble <= 0x9:
                    sb.append(str(nibble))
                    exponent_missing = False
                elif nibble == 0xA:
                    sb.append(".")
                elif nibble == 0xB:
                    if has_exponent:
                        continue
                    sb.append("E")
                    exponent_missing = True
                    has_exponent = True
                elif nibble == 0xC:
                    if has_exponent:
                        continue
                    sb.append("E-")
                    exponent_missing = True
                    has_exponent = True
                elif nibble == 0xD:
                    pass
                elif nibble == 0xE:
                    sb.append("-")
                elif nibble == 0xF:
                    done = True
                    break
                else:  # pragma: no cover - nibble is always 0x0-0xF
                    msg = f"illegal nibble {nibble}"
                    raise ValueError(msg)
        if exponent_missing:
            sb.append("0")
        if not sb:
            return 0.0
        try:
            return float("".join(sb))
        except ValueError as err:
            raise OSError(str(err)) from err

    # ------------------------------------------------------------------
    # SID / String index helpers.
    # ------------------------------------------------------------------

    def read_string(self, index: int) -> str:
        """PDFBox: ``CFFParser.readString``
        (``CFFParser.java`` lines 909-925). Resolves an SID against
        the CFF standard strings, falling back to the parsed string
        INDEX, or returns ``SID<n>`` for out-of-range indices."""
        from .cff_standard_string import CFFStandardString  # noqa: PLC0415

        if index < 0:
            msg = "Invalid negative index when reading a string"
            raise OSError(msg)
        if index <= 390:
            return CFFStandardString.get_name(index)
        if (
            self._string_index is not None
            and index - 391 < len(self._string_index)
        ):
            return self._string_index[index - 391]
        return f"SID{index}"

    def get_string(self, dict_: DictData, name: str) -> str | None:
        """PDFBox: ``CFFParser.getString``
        (``CFFParser.java`` lines 927-931). Resolves a string-typed
        DICT entry through ``read_string``."""
        entry = dict_.get_entry(name)
        if entry is not None and entry.has_operands():
            return self.read_string(int(entry.get_number(0)))
        return None

    # ------------------------------------------------------------------
    # ROS + per-font dispatch.
    # ------------------------------------------------------------------

    def parse_ros(self, top_dict: DictData) -> CFFCIDFont | None:
        """PDFBox: ``CFFParser.parseROS``
        (``CFFParser.java`` lines 531-548). Returns a populated
        :class:`CFFCIDFont` when the Top DICT carries a ROS triplet,
        else ``None``."""
        ros_entry = top_dict.get_entry("ROS")
        if ros_entry is None:
            return None
        if ros_entry.size() < 3:
            msg = "ROS entry must have 3 elements"
            raise OSError(msg)
        cid_font = CFFCIDFont()
        cid_font.set_registry(self.read_string(int(ros_entry.get_number(0))))
        cid_font.set_ordering(self.read_string(int(ros_entry.get_number(1))))
        cid_font.set_supplement(int(ros_entry.get_number(2)))
        return cid_font

    def parse_font(
        self,
        input_: DataInput,
        name: str,
        top_dict_index: bytes,
    ) -> CFFFont:
        """PDFBox: ``CFFParser.parseFont``
        (``CFFParser.java`` lines 550-712). Library-first wrapper:
        delegates to fontTools by re-parsing the byte stream around
        ``input_``'s payload, since the Java path does its own
        DICT/charset/encoding plumbing that fontTools already covers.
        Used by direct Java-port callers — the public ``parse``
        already takes the same library-first path."""
        # Build a payload that fontTools can parse: we expect callers
        # to have a complete CFF byte buffer in ``input_`` (mirrors
        # upstream's direct DataInput consumption). Read everything,
        # parse, and return the matching font.
        input_.set_position(0)
        cff_bytes = bytes(input_.read_bytes(input_.length()))
        fonts = self.parse(cff_bytes)
        for font in fonts:
            if font.get_name() == name:
                return font
        if fonts:
            return fonts[0]
        msg = f"Font {name!r} not found in CFF data"
        raise OSError(msg)

    # ------------------------------------------------------------------
    # Encodings.
    # ------------------------------------------------------------------

    def read_encoding(
        self,
        data_input: DataInput,
        charset: Any,
    ) -> Any:
        """PDFBox: ``CFFParser.readEncoding``
        (``CFFParser.java`` lines 933-947). Dispatches between Format0
        and Format1 encodings."""
        format_ = data_input.read_unsigned_byte()
        base_format = format_ & 0x7F
        if base_format == 0:
            return self.read_format0_encoding(data_input, charset, format_)
        if base_format == 1:
            return self.read_format1_encoding(data_input, charset, format_)
        msg = f"Invalid encoding base format {base_format}"
        raise OSError(msg)

    def read_format0_encoding(
        self,
        data_input: DataInput,
        charset: Any,
        format_: int,
    ) -> Any:
        """PDFBox: ``CFFParser.readFormat0Encoding``
        (``CFFParser.java`` lines 949-966). Single-byte-per-glyph
        encoding."""
        from .format0_encoding import Format0Encoding  # noqa: PLC0415

        encoding = Format0Encoding(data_input.read_unsigned_byte())
        encoding.add(0, 0, ".notdef")
        for gid in range(1, encoding.n_codes + 1):
            code = data_input.read_unsigned_byte()
            sid = charset.get_sid_for_gid(gid)
            encoding.add(code, sid, self.read_string(sid))
        if (format_ & 0x80) != 0:
            self.read_supplement(data_input, encoding)
        return encoding

    def read_format1_encoding(
        self,
        data_input: DataInput,
        charset: Any,
        format_: int,
    ) -> Any:
        """PDFBox: ``CFFParser.readFormat1Encoding``
        (``CFFParser.java`` lines 968-990). Range-based encoding."""
        from .format1_encoding import Format1Encoding  # noqa: PLC0415

        encoding = Format1Encoding(data_input.read_unsigned_byte())
        encoding.add(0, 0, ".notdef")
        gid = 1
        for _ in range(encoding.n_ranges):
            range_first = data_input.read_unsigned_byte()
            range_left = data_input.read_unsigned_byte()
            for j in range(range_left + 1):
                sid = charset.get_sid_for_gid(gid)
                encoding.add(range_first + j, sid, self.read_string(sid))
                gid += 1
        if (format_ & 0x80) != 0:
            self.read_supplement(data_input, encoding)
        return encoding

    def read_supplement(self, data_input: DataInput, encoding: Any) -> None:
        """PDFBox: ``CFFParser.readSupplement``
        (``CFFParser.java`` lines 992-1005). Reads the optional
        supplemental encoding table appended after Format0/Format1."""
        from .cff_built_in_encoding import Supplement  # noqa: PLC0415

        n_sups = data_input.read_unsigned_byte()
        supplements = []
        for _ in range(n_sups):
            code = data_input.read_unsigned_byte()
            sid = data_input.read_unsigned_short()
            sup = Supplement(code, sid, self.read_string(sid))
            supplements.append(sup)
            encoding.add_supplement(sup)
        encoding.supplement = supplements

    # ------------------------------------------------------------------
    # FDSelect.
    # ------------------------------------------------------------------

    @staticmethod
    def read_fd_select(data_input: DataInput, n_glyphs: int) -> Any:
        """PDFBox: ``CFFParser.readFDSelect``
        (``CFFParser.java`` lines 1014-1026). Dispatches Format0 vs
        Format3 FDSelect."""
        format_ = data_input.read_unsigned_byte()
        if format_ == 0:
            return CFFParser.read_format0_fd_select(data_input, n_glyphs)
        if format_ == 3:
            return CFFParser.read_format3_fd_select(data_input)
        raise ValueError

    @staticmethod
    def read_format0_fd_select(data_input: DataInput, n_glyphs: int) -> Any:
        """PDFBox: ``CFFParser.readFormat0FDSelect``
        (``CFFParser.java`` lines 1035-1044). One FD index per glyph."""
        from .fd_select import Format0FDSelect  # noqa: PLC0415

        fds = [data_input.read_unsigned_byte() for _ in range(n_glyphs)]
        return Format0FDSelect(fds)

    @staticmethod
    def read_format3_fd_select(data_input: DataInput) -> Any:
        """PDFBox: ``CFFParser.readFormat3FDSelect``
        (``CFFParser.java`` lines 1053-1064). Range-encoded FDSelect.

        Stored as ``(first, fd)`` tuples plus a sentinel — the
        Pythonic ``Format3FDSelect`` constructor takes the same shape
        upstream's package-private ``Range3[]`` array carries."""
        from .fd_select import Format3FDSelect  # noqa: PLC0415

        nb_ranges = data_input.read_unsigned_short()
        ranges = [
            (data_input.read_unsigned_short(), data_input.read_unsigned_byte())
            for _ in range(nb_ranges)
        ]
        sentinel = data_input.read_unsigned_short()
        return Format3FDSelect(ranges, sentinel)

    # ------------------------------------------------------------------
    # Charsets.
    # ------------------------------------------------------------------

    def read_charset(
        self,
        data_input: DataInput,
        n_glyphs: int,
        is_cid_font: bool,
    ) -> Any:
        """PDFBox: ``CFFParser.readCharset``
        (``CFFParser.java`` lines 1167-1183). Dispatches the three
        charset formats."""
        format_ = data_input.read_unsigned_byte()
        if format_ == 0:
            return self.read_format0_charset(data_input, n_glyphs, is_cid_font)
        if format_ == 1:
            return self.read_format1_charset(data_input, n_glyphs, is_cid_font)
        if format_ == 2:
            return self.read_format2_charset(data_input, n_glyphs, is_cid_font)
        msg = f"Incorrect charset format {format_}"
        raise OSError(msg)

    def read_format0_charset(
        self,
        data_input: DataInput,
        n_glyphs: int,
        is_cid_font: bool,
    ) -> Any:
        """PDFBox: ``CFFParser.readFormat0Charset``
        (``CFFParser.java`` lines 1185-1207). Single-SID-per-glyph."""
        from .embedded_charset import EmbeddedCharset  # noqa: PLC0415

        charset = EmbeddedCharset(is_cid_font)
        if is_cid_font:
            charset.add_cid(0, 0)
            for gid in range(1, n_glyphs):
                charset.add_cid(gid, data_input.read_unsigned_short())
        else:
            charset.add_sid(0, 0, ".notdef")
            for gid in range(1, n_glyphs):
                sid = data_input.read_unsigned_short()
                charset.add_sid(gid, sid, self.read_string(sid))
        return charset

    def read_format1_charset(
        self,
        data_input: DataInput,
        n_glyphs: int,
        is_cid_font: bool,
    ) -> Any:
        """PDFBox: ``CFFParser.readFormat1Charset``
        (``CFFParser.java`` lines 1209-1242). Range-based charset
        (1-byte ``nLeft``)."""
        from .format1_charset import Format1Charset  # noqa: PLC0415
        from .range_mapping import RangeMapping  # noqa: PLC0415

        charset = Format1Charset(is_cid_font)
        if is_cid_font:
            charset.add_cid(0, 0)
            gid = 1
            while gid < n_glyphs:
                range_first = data_input.read_unsigned_short()
                range_left = data_input.read_unsigned_byte()
                charset.add_range_mapping(RangeMapping(gid, range_first, range_left))
                gid += range_left + 1
        else:
            charset.add_sid(0, 0, ".notdef")
            gid = 1
            while gid < n_glyphs:
                range_first = data_input.read_unsigned_short()
                range_left = data_input.read_unsigned_byte() + 1
                for j in range(range_left):
                    sid = range_first + j
                    charset.add_sid(gid + j, sid, self.read_string(sid))
                gid += range_left
        return charset

    def read_format2_charset(
        self,
        data_input: DataInput,
        n_glyphs: int,
        is_cid_font: bool,
    ) -> Any:
        """PDFBox: ``CFFParser.readFormat2Charset``
        (``CFFParser.java`` lines 1244-1277). Range-based charset
        (2-byte ``nLeft``)."""
        from .format2_charset import Format2Charset  # noqa: PLC0415
        from .range_mapping import RangeMapping  # noqa: PLC0415

        charset = Format2Charset(is_cid_font)
        if is_cid_font:
            charset.add_cid(0, 0)
            gid = 1
            while gid < n_glyphs:
                first = data_input.read_unsigned_short()
                n_left = data_input.read_unsigned_short()
                charset.add_range_mapping(RangeMapping(gid, first, n_left))
                gid += n_left + 1
        else:
            charset.add_sid(0, 0, ".notdef")
            gid = 1
            while gid < n_glyphs:
                first = data_input.read_unsigned_short()
                n_left = data_input.read_unsigned_short() + 1
                for j in range(n_left):
                    sid = first + j
                    charset.add_sid(gid + j, sid, self.read_string(sid))
                gid += n_left
        return charset

    # ------------------------------------------------------------------
    # Per-font-class private dictionaries.
    # ------------------------------------------------------------------

    def parse_cid_font_dicts(
        self,
        input_: DataInput,
        top_dict: DictData,
        font: CFFCIDFont,
        nr_of_char_strings: int,
    ) -> None:
        """PDFBox: ``CFFParser.parseCIDFontDicts``
        (``CFFParser.java`` lines 745-834). Walks the FDArray, builds
        font + private dict maps, and attaches them to ``font``."""
        fd_array_entry = top_dict.get_entry("FDArray")
        if fd_array_entry is None or not fd_array_entry.has_operands():
            msg = "FDArray is missing for a CIDKeyed Font."
            raise OSError(msg)

        font_dict_offset = int(fd_array_entry.get_number(0))
        input_.set_position(font_dict_offset)
        fd_index = self.read_index_data(input_)
        if not fd_index:
            msg = "Font dict index is missing for a CIDKeyed Font"
            raise OSError(msg)

        private_dictionaries: list[dict[str, Any]] = []
        font_dictionaries: list[dict[str, Any]] = []
        private_dict_populated = False

        for entry_bytes in fd_index:
            font_dict_input = DataInputByteArray(entry_bytes)
            font_dict = self.read_dict_data(font_dict_input)

            font_dict_map: dict[str, Any] = {}
            font_dict_map["FontName"] = self.get_string(font_dict, "FontName")
            font_dict_map["FontType"] = font_dict.get_number("FontType", 0)
            font_dict_map["FontBBox"] = font_dict.get_array("FontBBox", None)
            font_dict_map["FontMatrix"] = font_dict.get_array("FontMatrix", None)
            font_dictionaries.append(font_dict_map)

            private_entry = font_dict.get_entry("Private")
            if private_entry is None or private_entry.size() < 2:
                private_dictionaries.append({})
                continue

            private_offset = int(private_entry.get_number(1))
            private_size = int(private_entry.get_number(0))
            private_dict = self.read_dict_data(input_, private_offset, private_size)

            private_dict_populated = True
            priv_dict = self.read_private_dict(private_dict)
            private_dictionaries.append(priv_dict)

            local_subr_offset = private_dict.get_number("Subrs", 0)
            if isinstance(local_subr_offset, int) and local_subr_offset > 0:
                input_.set_position(private_offset + local_subr_offset)
                priv_dict["Subrs"] = self.read_index_data(input_)

        if not private_dict_populated:
            msg = 'Font DICT invalid without "Private" entry'
            raise OSError(msg)

        fd_select_entry = top_dict.get_entry("FDSelect")
        if fd_select_entry is None or not fd_select_entry.has_operands():
            msg = "FDSelect is missing or empty"
            raise OSError(msg)
        fd_select_pos = int(fd_select_entry.get_number(0))
        input_.set_position(fd_select_pos)
        fd_select = self.read_fd_select(input_, nr_of_char_strings)

        font.set_font_dict(font_dictionaries)
        font.set_priv_dict(private_dictionaries)
        font.set_fd_select(fd_select)

    def parse_type1_dicts(
        self,
        input_: DataInput,
        top_dict: DictData,
        font: CFFType1Font,
        charset: Any,
    ) -> None:
        """PDFBox: ``CFFParser.parseType1Dicts``
        (``CFFParser.java`` lines 862-907). Builds the encoding +
        private dict for a Type 1-equivalent font."""
        from .cff_expert_encoding import CFFExpertEncoding  # noqa: PLC0415
        from .cff_standard_encoding import CFFStandardEncoding  # noqa: PLC0415

        encoding_entry = top_dict.get_entry("Encoding")
        if encoding_entry is not None and encoding_entry.has_operands():
            encoding_id = int(encoding_entry.get_number(0))
        else:
            encoding_id = 0

        if encoding_id == 0:
            encoding = CFFStandardEncoding.get_instance()
        elif encoding_id == 1:
            encoding = CFFExpertEncoding.get_instance()
        else:
            input_.set_position(encoding_id)
            encoding = self.read_encoding(input_, charset)
        font.set_encoding(encoding)

        private_entry = top_dict.get_entry("Private")
        if private_entry is None or private_entry.size() < 2:
            msg = f"Private dictionary entry missing for font {font.get_name()}"
            raise OSError(msg)
        private_offset = int(private_entry.get_number(1))
        private_size = int(private_entry.get_number(0))
        private_dict = self.read_dict_data(input_, private_offset, private_size)

        priv_dict = self.read_private_dict(private_dict)
        for key, value in priv_dict.items():
            font.add_to_private_dict(key, value)

        local_subr_offset = private_dict.get_number("Subrs", 0)
        if isinstance(local_subr_offset, int) and local_subr_offset > 0:
            input_.set_position(private_offset + local_subr_offset)
            font.add_to_private_dict("Subrs", self.read_index_data(input_))

    @staticmethod
    def read_private_dict(private_dict: DictData) -> dict[str, Any]:
        """PDFBox: ``CFFParser.readPrivateDict``
        (``CFFParser.java`` lines 836-857). Materialises the private
        DICT defaults into an ordered dict."""
        priv: dict[str, Any] = {}
        priv["BlueValues"] = private_dict.get_delta("BlueValues", None)
        priv["OtherBlues"] = private_dict.get_delta("OtherBlues", None)
        priv["FamilyBlues"] = private_dict.get_delta("FamilyBlues", None)
        priv["FamilyOtherBlues"] = private_dict.get_delta("FamilyOtherBlues", None)
        priv["BlueScale"] = private_dict.get_number("BlueScale", 0.039625)
        priv["BlueShift"] = private_dict.get_number("BlueShift", 7)
        priv["BlueFuzz"] = private_dict.get_number("BlueFuzz", 1)
        priv["StdHW"] = private_dict.get_number("StdHW", None)
        priv["StdVW"] = private_dict.get_number("StdVW", None)
        priv["StemSnapH"] = private_dict.get_delta("StemSnapH", None)
        priv["StemSnapV"] = private_dict.get_delta("StemSnapV", None)
        priv["ForceBold"] = private_dict.get_boolean("ForceBold", False)  # noqa: FBT003
        priv["LanguageGroup"] = private_dict.get_number("LanguageGroup", 0)
        priv["ExpansionFactor"] = private_dict.get_number("ExpansionFactor", 0.06)
        priv["initialRandomSeed"] = private_dict.get_number("initialRandomSeed", 0)
        priv["defaultWidthX"] = private_dict.get_number("defaultWidthX", 0)
        priv["nominalWidthX"] = private_dict.get_number("nominalWidthX", 0)
        return priv

    # ------------------------------------------------------------------
    # Helpers reused from upstream's anonymous code paths.
    # ------------------------------------------------------------------

    @staticmethod
    def concatenate_matrix(
        matrix_dest: list[float],
        matrix_concat: list[float],
    ) -> None:
        """PDFBox: ``CFFParser.concatenateMatrix``
        (``CFFParser.java`` lines 714-740). Multiplies two 3x3
        transform matrices (stored as 6-element row vectors) in place
        on ``matrix_dest``."""
        a1, b1, c1, d1, x1, y1 = (float(v) for v in matrix_dest[:6])
        a2, b2, c2, d2, x2, y2 = (float(v) for v in matrix_concat[:6])

        matrix_dest[0] = a1 * a2 + b1 * c2
        # Mirror upstream bug-compatibility: line 735 uses ``d1`` not
        # ``d2`` in the (1) slot. We preserve it so parity callers see
        # the exact same number — see PDFBOX issue tracking around
        # ``concatenateMatrix``.
        matrix_dest[1] = a1 * b2 + b1 * d1
        matrix_dest[2] = c1 * a2 + d1 * c2
        matrix_dest[3] = c1 * b2 + d1 * d2
        matrix_dest[4] = x1 * a2 + y1 * c2 + x2
        matrix_dest[5] = x1 * b2 + y1 * d2 + y2

    @staticmethod
    def as_list(*values: Any) -> list[Any]:
        """Helper used in ports of upstream's ``Arrays.<Number>asList``
        calls (e.g. ``CFFParser.java`` lines 593-595, 597-598,
        693-694). Returns its arguments as a plain Python list — the
        Python equivalent of ``Arrays.asList(...)``."""
        return list(values)

    def to_string(self) -> str:
        """PDFBox: ``CFFParser.toString()``
        (``CFFParser.java`` lines 1729-1733)."""
        return f"{type(self).__name__}[{self._debug_font_name}]"

    def __repr__(self) -> str:
        return self.to_string()


def _strip_otf_wrapper(data: bytes) -> bytes:
    """If ``data`` is an OpenType font ('OTTO' magic) extract the inner
    ``CFF `` table. Plain CFF byte streams are returned unchanged.

    Mirrors upstream ``CFFParser.skipHeader`` /
    ``createTaggedCFFDataInput`` (``CFFParser.java`` lines 164-185 and
    222-248) — including the explicit refusal to handle TrueType
    Collection ('ttcf') and pure-TrueType ('\\0\\1\\0\\0') containers.
    """
    if len(data) < 4:
        return data
    tag = data[:4]
    if tag == b"OTTO":
        return _extract_cff_table(data)
    if tag == b"ttcf":
        msg = "True Type Collection fonts are not supported."
        raise OSError(msg)
    if tag == b"\x00\x01\x00\x00":
        msg = "OpenType fonts containing a true type font are not supported."
        raise OSError(msg)
    return data


def _extract_cff_table(otf_bytes: bytes) -> bytes:
    """Walk the OTF table directory and return the bytes of the
    ``CFF `` table.

    Mirrors upstream ``createTaggedCFFDataInput``
    (``CFFParser.java`` lines 222-248). 16-byte directory records:
    ``tag(4) checksum(4) offset(4) length(4)``.
    """
    if len(otf_bytes) < 12:
        msg = "Truncated OTF header"
        raise OSError(msg)
    num_tables = struct.unpack(">H", otf_bytes[4:6])[0]
    # Skip searchRange/entrySelector/rangeShift (3 × Card16) — upstream
    # reads them but discards the values.
    record_offset = 12
    for _ in range(num_tables):
        if len(otf_bytes) < record_offset + 16:
            msg = "Truncated OTF table directory"
            raise OSError(msg)
        record = otf_bytes[record_offset : record_offset + 16]
        tag = record[0:4]
        offset = struct.unpack(">I", record[8:12])[0]
        length = struct.unpack(">I", record[12:16])[0]
        if tag == b"CFF ":
            return otf_bytes[offset : offset + length]
        record_offset += 16
    msg = "CFF tag not found in this OpenType font."
    raise OSError(msg)


__all__ = ["CFFParser"]
