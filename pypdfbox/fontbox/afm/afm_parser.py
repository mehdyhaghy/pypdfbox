from __future__ import annotations

from contextlib import suppress
from typing import IO

from pypdfbox.fontbox.ttf.glyph_data import BoundingBox

from .char_metric import CharMetric
from .composite import Composite
from .composite_part import CompositePart
from .font_metrics import FontMetrics
from .kern_pair import KernPair
from .ligature import Ligature
from .track_kern import TrackKern

# Type alias for accepted inputs: a binary file-like object or raw bytes.
_BinaryInput = IO[bytes] | bytes | bytearray


class AFMParser:
    """Parser for Adobe Font Metric files.

    Mirrors ``org.apache.fontbox.afm.AFMParser``. The constructor accepts
    a binary stream (``IO[bytes]``) or raw ``bytes``; calling
    :meth:`parse` returns a :class:`FontMetrics` populated with header,
    char-metric, kerning, and composite data.

    The reduced-dataset switch (``parse(reduced_dataset=True)``) skips
    kern and composite blocks the same way upstream does, and tolerates
    unknown trailing keywords once char metrics have been read so that a
    truncated font can still be parsed for its glyph table.

    Internal helper methods (``read_string``, ``parse_kern_data``,
    ``hex_to_string`` etc.) keep their upstream names without a leading
    underscore so that 1:1 method-level parity with Apache PDFBox's
    ``AFMParser`` is preserved. They remain implementation details and
    are not part of any external pypdfbox API.
    """

    # ------------------------------------------------------------------
    # AFM keyword constants — mirrored from upstream (PDFBox 3.0.x).
    # ------------------------------------------------------------------
    COMMENT = "Comment"
    START_FONT_METRICS = "StartFontMetrics"
    END_FONT_METRICS = "EndFontMetrics"
    METRIC_SETS = "MetricSets"
    FONT_NAME = "FontName"
    FULL_NAME = "FullName"
    FAMILY_NAME = "FamilyName"
    WEIGHT = "Weight"
    FONT_BBOX = "FontBBox"
    VERSION = "Version"
    NOTICE = "Notice"
    ENCODING_SCHEME = "EncodingScheme"
    MAPPING_SCHEME = "MappingScheme"
    ESC_CHAR = "EscChar"
    CHARACTER_SET = "CharacterSet"
    CHARACTERS = "Characters"
    IS_BASE_FONT = "IsBaseFont"
    V_VECTOR = "VVector"
    IS_FIXED_V = "IsFixedV"
    CAP_HEIGHT = "CapHeight"
    X_HEIGHT = "XHeight"
    ASCENDER = "Ascender"
    DESCENDER = "Descender"
    UNDERLINE_POSITION = "UnderlinePosition"
    UNDERLINE_THICKNESS = "UnderlineThickness"
    ITALIC_ANGLE = "ItalicAngle"
    CHAR_WIDTH = "CharWidth"
    IS_FIXED_PITCH = "IsFixedPitch"
    START_CHAR_METRICS = "StartCharMetrics"
    END_CHAR_METRICS = "EndCharMetrics"
    CHARMETRICS_C = "C"
    CHARMETRICS_CH = "CH"
    CHARMETRICS_WX = "WX"
    CHARMETRICS_W0X = "W0X"
    CHARMETRICS_W1X = "W1X"
    CHARMETRICS_WY = "WY"
    CHARMETRICS_W0Y = "W0Y"
    CHARMETRICS_W1Y = "W1Y"
    CHARMETRICS_W = "W"
    CHARMETRICS_W0 = "W0"
    CHARMETRICS_W1 = "W1"
    CHARMETRICS_VV = "VV"
    CHARMETRICS_N = "N"
    CHARMETRICS_B = "B"
    CHARMETRICS_L = "L"
    STD_HW = "StdHW"
    STD_VW = "StdVW"
    START_TRACK_KERN = "StartTrackKern"
    END_TRACK_KERN = "EndTrackKern"
    START_KERN_DATA = "StartKernData"
    END_KERN_DATA = "EndKernData"
    START_KERN_PAIRS = "StartKernPairs"
    END_KERN_PAIRS = "EndKernPairs"
    START_KERN_PAIRS0 = "StartKernPairs0"
    START_KERN_PAIRS1 = "StartKernPairs1"
    START_COMPOSITES = "StartComposites"
    END_COMPOSITES = "EndComposites"
    CC = "CC"
    PCC = "PCC"
    KERN_PAIR_KP = "KP"
    KERN_PAIR_KPH = "KPH"
    KERN_PAIR_KPX = "KPX"
    KERN_PAIR_KPY = "KPY"

    _BITS_IN_HEX = 16

    # ------------------------------------------------------------------

    def __init__(self, source: _BinaryInput) -> None:
        if isinstance(source, (bytes, bytearray)):
            self._buf: bytes = bytes(source)
        else:
            # Read everything up-front; AFMs are small (Helvetica ~50 KB).
            self._buf = source.read()
            with suppress(Exception):
                source.close()
        self._pos: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, reduced_dataset: bool = False) -> FontMetrics:
        """Parse the AFM document and return its :class:`FontMetrics`.

        ``reduced_dataset`` skips kern and composite blocks the same way
        as upstream's ``AFMParser.parse(true)`` overload.
        """
        return self.parse_font_metric(reduced_dataset)

    # ------------------------------------------------------------------
    # Top-level body
    # ------------------------------------------------------------------

    def parse_font_metric(self, reduced_dataset: bool) -> FontMetrics:
        self.read_command(self.START_FONT_METRICS)
        font_metrics = FontMetrics()
        font_metrics.set_afm_version(self.read_float())
        char_metrics_read = False
        while True:
            next_command = self.read_string()
            if next_command == self.END_FONT_METRICS:
                break
            if next_command == self.METRIC_SETS:
                font_metrics.set_metric_sets(self.read_int())
            elif next_command == self.FONT_NAME:
                font_metrics.set_font_name(self.read_line())
            elif next_command == self.FULL_NAME:
                font_metrics.set_full_name(self.read_line())
            elif next_command == self.FAMILY_NAME:
                font_metrics.set_family_name(self.read_line())
            elif next_command == self.WEIGHT:
                font_metrics.set_weight(self.read_line())
            elif next_command == self.FONT_BBOX:
                bbox = BoundingBox()
                bbox.set_lower_left_x(self.read_float())
                bbox.set_lower_left_y(self.read_float())
                bbox.set_upper_right_x(self.read_float())
                bbox.set_upper_right_y(self.read_float())
                font_metrics.set_font_b_box(bbox)
            elif next_command == self.VERSION:
                font_metrics.set_font_version(self.read_line())
            elif next_command == self.NOTICE:
                font_metrics.set_notice(self.read_line())
            elif next_command == self.ENCODING_SCHEME:
                font_metrics.set_encoding_scheme(self.read_line())
            elif next_command == self.MAPPING_SCHEME:
                font_metrics.set_mapping_scheme(self.read_int())
            elif next_command == self.ESC_CHAR:
                font_metrics.set_esc_char(self.read_int())
            elif next_command == self.CHARACTER_SET:
                font_metrics.set_character_set(self.read_line())
            elif next_command == self.CHARACTERS:
                font_metrics.set_characters(self.read_int())
            elif next_command == self.IS_BASE_FONT:
                font_metrics.set_is_base_font(self.read_boolean())
            elif next_command == self.V_VECTOR:
                font_metrics.set_v_vector((self.read_float(), self.read_float()))
            elif next_command == self.IS_FIXED_V:
                font_metrics.set_is_fixed_v(self.read_boolean())
            elif next_command == self.CAP_HEIGHT:
                font_metrics.set_cap_height(self.read_float())
            elif next_command == self.X_HEIGHT:
                font_metrics.set_x_height(self.read_float())
            elif next_command == self.ASCENDER:
                font_metrics.set_ascender(self.read_float())
            elif next_command == self.DESCENDER:
                font_metrics.set_descender(self.read_float())
            elif next_command == self.STD_HW:
                font_metrics.set_standard_horizontal_width(self.read_float())
            elif next_command == self.STD_VW:
                font_metrics.set_standard_vertical_width(self.read_float())
            elif next_command == self.COMMENT:
                font_metrics.add_comment(self.read_line())
            elif next_command == self.UNDERLINE_POSITION:
                font_metrics.set_underline_position(self.read_float())
            elif next_command == self.UNDERLINE_THICKNESS:
                font_metrics.set_underline_thickness(self.read_float())
            elif next_command == self.ITALIC_ANGLE:
                font_metrics.set_italic_angle(self.read_float())
            elif next_command == self.CHAR_WIDTH:
                font_metrics.set_char_width(
                    (self.read_float(), self.read_float())
                )
            elif next_command == self.IS_FIXED_PITCH:
                font_metrics.set_fixed_pitch(self.read_boolean())
            elif next_command == self.START_CHAR_METRICS:
                char_metrics_read = self.parse_char_metrics(font_metrics)
            elif next_command == self.START_KERN_DATA:
                # Upstream simply skips the call in reduced mode (no skip-to-
                # terminator): the main loop then re-encounters the inner kern
                # tokens as unknown keys, which are tolerated once char metrics
                # have been read and otherwise raise. We mirror that exactly.
                if not reduced_dataset:
                    self.parse_kern_data(font_metrics)
            elif next_command == self.START_COMPOSITES:
                if not reduced_dataset:
                    self.parse_composites(font_metrics)
            else:
                if not reduced_dataset or not char_metrics_read:
                    raise OSError(f"Unknown AFM key '{next_command}'")
        return font_metrics

    # ------------------------------------------------------------------
    # Char metrics
    # ------------------------------------------------------------------

    def parse_char_metrics(self, font_metrics: FontMetrics) -> bool:
        # Upstream returns ``true`` after consuming a CharMetrics block;
        # the caller uses that flag to relax unknown-key strictness in
        # reduced-dataset mode.
        count = self.read_int()
        for _ in range(count):
            font_metrics.add_char_metric(self.parse_char_metric())
        self.read_command(self.END_CHAR_METRICS)
        return True

    def parse_char_metric(self) -> CharMetric:
        # Note: this method uses bare ``int()`` / ``float()`` and lets
        # ``ValueError`` bubble up to be wrapped as "Malformed CharMetrics
        # line" by the surrounding try/except. Upstream calls
        # ``parseInt``/``parseFloat`` here, which would surface "Error
        # parsing AFM document"; the wrapped message is a deliberate
        # divergence (see CHANGES.md, wave287).
        line = self.read_line()
        tokens = [t for t in line.replace(";", " ; ").split() if t]
        char_metric = CharMetric()
        i = 0
        n = len(tokens)
        try:
            while i < n:
                tok = tokens[i]
                i += 1
                if tok == self.CHARMETRICS_C:
                    char_metric.set_character_code(int(tokens[i]))
                    i += 1
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_CH:
                    # Hex-encoded character code. The spec is unclear whether
                    # the value is bare hex (``41``) or angle-bracketed
                    # (``<41>``). Upstream parses it as bare hex via
                    # ``parseInt(token, BITS_IN_HEX)`` and therefore rejects
                    # the ``<41>`` form; pypdfbox deliberately accepts both
                    # (a documented intentional leniency — see CHANGES.md
                    # wave316 / wave1522). Bare hex parity is preserved.
                    char_metric.set_character_code(
                        self._parse_hex_character_code(tokens[i])
                    )
                    i += 1
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_WX:
                    char_metric.set_wx(float(tokens[i]))
                    i += 1
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_W0X:
                    char_metric.set_w0x(float(tokens[i]))
                    i += 1
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_W1X:
                    char_metric.set_w1x(float(tokens[i]))
                    i += 1
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_WY:
                    char_metric.set_wy(float(tokens[i]))
                    i += 1
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_W0Y:
                    char_metric.set_w0y(float(tokens[i]))
                    i += 1
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_W1Y:
                    char_metric.set_w1y(float(tokens[i]))
                    i += 1
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_W:
                    char_metric.set_w((float(tokens[i]), float(tokens[i + 1])))
                    i += 2
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_W0:
                    char_metric.set_w0((float(tokens[i]), float(tokens[i + 1])))
                    i += 2
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_W1:
                    char_metric.set_w1((float(tokens[i]), float(tokens[i + 1])))
                    i += 2
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_VV:
                    char_metric.set_vv((float(tokens[i]), float(tokens[i + 1])))
                    i += 2
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_N:
                    char_metric.set_name(tokens[i])
                    i += 1
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_B:
                    bbox = BoundingBox()
                    bbox.set_lower_left_x(float(tokens[i]))
                    bbox.set_lower_left_y(float(tokens[i + 1]))
                    bbox.set_upper_right_x(float(tokens[i + 2]))
                    bbox.set_upper_right_y(float(tokens[i + 3]))
                    i += 4
                    char_metric.set_bounding_box(bbox)
                    i = self.verify_semicolon(tokens, i)
                elif tok == self.CHARMETRICS_L:
                    char_metric.add_ligature(Ligature(tokens[i], tokens[i + 1]))
                    i += 2
                    i = self.verify_semicolon(tokens, i)
                else:
                    raise OSError(f"Unknown CharMetrics command '{tok}'")
        except (IndexError, ValueError) as e:
            raise OSError(f"Malformed CharMetrics line '{line}'") from e
        return char_metric

    @classmethod
    def _parse_hex_character_code(cls, token: str) -> int:
        if token.startswith("<") or token.endswith(">"):
            if not token.startswith("<") or not token.endswith(">"):
                raise ValueError(f"Malformed hex character code '{token}'")
            token = token[1:-1]
        return int(token, cls._BITS_IN_HEX)

    @staticmethod
    def verify_semicolon(tokens: list[str], i: int) -> int:
        # CharMetric lines separate items with ``;``. A trailing ``;`` may be
        # present or absent at end-of-line; we accept either, matching what
        # bundled Adobe Core 14 AFMs ship.
        #
        # Upstream takes a ``StringTokenizer`` and consumes the next token in
        # place; we take ``(tokens, i)`` and return the new cursor. Same
        # semantics, Pythonic shape.
        if i >= len(tokens):
            return i
        if tokens[i] != ";":
            raise OSError(
                f"Error: Expected semicolon in stream actual='{tokens[i]}'"
            )
        return i + 1

    # ------------------------------------------------------------------
    # Kern data
    # ------------------------------------------------------------------

    def parse_kern_data(self, font_metrics: FontMetrics) -> None:
        while True:
            next_command = self.read_string()
            if next_command == self.END_KERN_DATA:
                break
            if next_command == self.START_TRACK_KERN:
                count = self.read_int()
                for _ in range(count):
                    # Upstream reads each track-kern entry as five bare numeric
                    # tokens (degree + four floats) directly after the count —
                    # there is NO leading ``TrackKern`` keyword per entry. A
                    # prior port added a spurious ``read_command("TrackKern")``
                    # which both rejected valid (keyword-less) track-kern data
                    # and accepted a malformed leading keyword; removed to match
                    # ``AFMParser.parseKernData`` (CHANGES.md wave1548).
                    font_metrics.add_track_kern(
                        TrackKern(
                            self.read_int(),
                            self.read_float(),
                            self.read_float(),
                            self.read_float(),
                            self.read_float(),
                        )
                    )
                self.read_command(self.END_TRACK_KERN)
            elif next_command == self.START_KERN_PAIRS:
                self.parse_kern_pairs(font_metrics)
            elif next_command == self.START_KERN_PAIRS0:
                self.parse_kern_pairs0(font_metrics)
            elif next_command == self.START_KERN_PAIRS1:
                self.parse_kern_pairs1(font_metrics)
            else:
                raise OSError(f"Unknown kerning data type '{next_command}'")

    def parse_kern_pairs(self, font_metrics: FontMetrics) -> None:
        count = self.read_int()
        for _ in range(count):
            font_metrics.add_kern_pair(self.parse_kern_pair())
        self.read_command(self.END_KERN_PAIRS)

    def parse_kern_pairs0(self, font_metrics: FontMetrics) -> None:
        count = self.read_int()
        for _ in range(count):
            font_metrics.add_kern_pair0(self.parse_kern_pair())
        self.read_command(self.END_KERN_PAIRS)

    def parse_kern_pairs1(self, font_metrics: FontMetrics) -> None:
        count = self.read_int()
        for _ in range(count):
            font_metrics.add_kern_pair1(self.parse_kern_pair())
        self.read_command(self.END_KERN_PAIRS)

    def parse_kern_pair(self) -> KernPair:
        cmd = self.read_string()
        if cmd == self.KERN_PAIR_KP:
            return KernPair(
                self.read_string(),
                self.read_string(),
                self.read_float(),
                self.read_float(),
            )
        if cmd == self.KERN_PAIR_KPH:
            return KernPair(
                self.hex_to_string(self.read_string()),
                self.hex_to_string(self.read_string()),
                self.read_float(),
                self.read_float(),
            )
        if cmd == self.KERN_PAIR_KPX:
            return KernPair(
                self.read_string(), self.read_string(), self.read_float(), 0.0
            )
        if cmd == self.KERN_PAIR_KPY:
            return KernPair(
                self.read_string(), self.read_string(), 0.0, self.read_float()
            )
        raise OSError(f"Error expected kern pair command actual='{cmd}'")

    @staticmethod
    def hex_to_string(hex_token: str) -> str:
        if len(hex_token) < 2:
            raise OSError(
                f"Error: Expected hex string of length >= 2 not='{hex_token}"
            )
        if hex_token[0] != "<" or hex_token[-1] != ">":
            raise OSError(
                f"String should be enclosed by angle brackets '{hex_token}'"
            )
        body = hex_token[1:-1]
        try:
            data = bytes.fromhex(body)
        except ValueError as e:
            raise OSError(f"Error parsing AFM document:{e}") from e
        return data.decode("latin-1")

    # ------------------------------------------------------------------
    # Composites
    # ------------------------------------------------------------------

    def parse_composites(self, font_metrics: FontMetrics) -> None:
        count = self.read_int()
        for _ in range(count):
            font_metrics.add_composite(self.parse_composite())
        self.read_command(self.END_COMPOSITES)

    def parse_composite(self) -> Composite:
        # Same divergence as ``parse_char_metric``: bare ``int()`` raises
        # ``ValueError`` on malformed numeric tokens which we wrap as a
        # "Malformed Composite line" error rather than upstream's "Error
        # parsing AFM document" surface (see CHANGES.md, wave294).
        line = self.read_line()
        tokens = [t for t in line.replace(";", " ; ").split() if t]
        try:
            # Expect: CC <name> <count> ; PCC <name> <x> <y> ; ...
            if not tokens or tokens[0] != self.CC:
                raise OSError(
                    f"Expected '{self.CC}' actual='{tokens[0] if tokens else ''}'"
                )
            name = tokens[1]
            composite = Composite(name)
            part_count = int(tokens[2])
            # Skip the trailing ';' after the part count.
            i = 3
            if i < len(tokens) and tokens[i] == ";":
                i += 1
            for _ in range(part_count):
                if tokens[i] != self.PCC:
                    raise OSError(
                        f"Expected '{self.PCC}' actual='{tokens[i]}'"
                    )
                i += 1
                part_name = tokens[i]
                i += 1
                x = int(tokens[i])
                i += 1
                y = int(tokens[i])
                i += 1
                if i < len(tokens) and tokens[i] == ";":
                    i += 1
                composite.add_part(CompositePart(part_name, x, y))
        except (IndexError, ValueError) as e:
            raise OSError(f"Malformed Composite line '{line}'") from e
        return composite

    # ------------------------------------------------------------------
    # Low-level lexer (byte-oriented, mirrors upstream's logic)
    # ------------------------------------------------------------------

    @staticmethod
    def is_eol(b: int) -> bool:
        return b == 0x0D or b == 0x0A

    @staticmethod
    def is_whitespace(b: int) -> bool:
        return b in (0x20, 0x09, 0x0D, 0x0A)

    def _read_byte(self) -> int:
        if self._pos >= len(self._buf):
            return -1
        b = self._buf[self._pos]
        self._pos += 1
        return b

    def read_string(self) -> str:
        # Skip leading whitespace.
        b = self._read_byte()
        while b != -1 and self.is_whitespace(b):
            b = self._read_byte()
        if b == -1:
            return ""
        out = bytearray([b])
        b = self._read_byte()
        while b != -1 and not self.is_whitespace(b):
            out.append(b)
            b = self._read_byte()
        return out.decode("latin-1")

    def read_line(self) -> str:
        b = self._read_byte()
        while b != -1 and self.is_whitespace(b):
            b = self._read_byte()
        if b == -1:
            return ""
        out = bytearray([b])
        b = self._read_byte()
        while b != -1 and not self.is_eol(b):
            out.append(b)
            b = self._read_byte()
        return out.decode("latin-1")

    def read_command(self, expected: str) -> None:
        cmd = self.read_string()
        if cmd != expected:
            raise OSError(f"Error: Expected '{expected}' actual '{cmd}'")

    def read_int(self) -> int:
        return self.parse_int(self.read_string(), 10)

    def parse_int(self, value: str, radix: int = 10) -> int:
        # Mirrors upstream's two ``parseInt`` overloads: the no-radix form
        # delegates to the radix-10 form. ``ValueError`` from Python's
        # ``int(...)`` is wrapped in ``OSError`` so callers see the same
        # ``IOException``-shaped failure mode as upstream.
        try:
            return int(value, radix)
        except ValueError as e:
            raise OSError(f"Error parsing AFM document:{e}") from e

    def read_float(self) -> float:
        return self.parse_float(self.read_string())

    def parse_float(self, value: str) -> float:
        try:
            return float(value)
        except ValueError as e:
            raise OSError(f"Error parsing AFM document:{e}") from e

    def read_boolean(self) -> bool:
        return self.read_string().lower() == "true"
