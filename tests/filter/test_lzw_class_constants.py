"""Hand-written tests for the class-level constants on
:class:`pypdfbox.filter.LZWDecode` / :class:`pypdfbox.filter.LZWFilter`.

Upstream PDFBox keeps these as ``public static final long CLEAR_TABLE``
and ``public static final long EOD`` on ``LZWFilter``. Direct ports
translating ``LZWFilter.CLEAR_TABLE`` / ``LZWFilter.EOD`` need them on
the class itself, not just on the enclosing module.
"""

from __future__ import annotations

from pypdfbox.filter import LZWDecode, LZWFilter
from pypdfbox.filter.lzw_decode import (
    CLEAR_TABLE as MODULE_CLEAR_TABLE,
)
from pypdfbox.filter.lzw_decode import (
    EOD as MODULE_EOD,
)
from pypdfbox.filter.lzw_decode import (
    MAX_TABLE_SIZE as MODULE_MAX_TABLE_SIZE,
)


class TestLZWDecodeClassConstants:
    def test_clear_table_value(self):
        # CLEAR_TABLE is the dictionary-reset code (256) per ISO 32000-1
        # §7.4.4.
        assert LZWDecode.CLEAR_TABLE == 256

    def test_eod_value(self):
        # EOD is 257, immediately after the 256 byte literals + CLEAR.
        assert LZWDecode.EOD == 257

    def test_max_table_size_value(self):
        # 12-bit codes → 4096 entries before a CLEAR is required.
        assert LZWDecode.MAX_TABLE_SIZE == 4096

    def test_class_attributes_match_module_constants(self):
        assert LZWDecode.CLEAR_TABLE == MODULE_CLEAR_TABLE
        assert LZWDecode.EOD == MODULE_EOD
        assert LZWDecode.MAX_TABLE_SIZE == MODULE_MAX_TABLE_SIZE


class TestLZWFilterClassConstantsInherited:
    def test_lzw_filter_inherits_clear_table(self):
        # LZWFilter is the upstream-named subclass of LZWDecode; the
        # constants must be visible through both class names so direct
        # ports translating either ``LZWFilter.CLEAR_TABLE`` or
        # ``LZWDecode.CLEAR_TABLE`` resolve identically.
        assert LZWFilter.CLEAR_TABLE == LZWDecode.CLEAR_TABLE

    def test_lzw_filter_inherits_eod(self):
        assert LZWFilter.EOD == LZWDecode.EOD

    def test_lzw_filter_inherits_max_table_size(self):
        assert LZWFilter.MAX_TABLE_SIZE == LZWDecode.MAX_TABLE_SIZE


class TestLZWConstantsRelationships:
    def test_eod_is_one_after_clear_table(self):
        # Reserved codes are 256 (CLEAR_TABLE) and 257 (EOD), back-to-back.
        assert LZWDecode.EOD == LZWDecode.CLEAR_TABLE + 1

    def test_clear_table_is_first_reserved_code(self):
        # Codes 0..255 are byte literals; CLEAR_TABLE is the next one.
        assert LZWDecode.CLEAR_TABLE == 256

    def test_max_table_size_is_power_of_two(self):
        # 12-bit max code width → 2^12 = 4096 entries.
        assert LZWDecode.MAX_TABLE_SIZE == 1 << 12
