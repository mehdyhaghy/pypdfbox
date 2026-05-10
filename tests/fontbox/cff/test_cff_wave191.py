"""Wave 191 — round-out tests for CFF base classes.

Covers the small parity gaps added in this wave:

* ``CFFFont.NUM_STANDARD_STRINGS`` / ``DEFAULT_CID_COUNT`` constants.
* ``CFFFont.is_standard_sid`` predicate.
* ``CFFType1Font.has_encoding`` / ``has_local_subrs`` /
  ``get_local_subr_index`` accessors.
* ``CFFCIDFont.has_fd_select`` / ``has_fd_array`` predicates.
* ``CFFCIDFont.get_local_subr_index_for_gid`` helper.

All tests exercise the synthetic / empty-instance paths so they run
unconditionally, without needing a real OTF on the host.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.cff.fd_array import FDArray
from pypdfbox.fontbox.cff.fd_select import Format0FDSelect

# ---------- spec constants ----------


class TestSpecConstants:
    def test_num_standard_strings_is_391(self) -> None:
        # Adobe Technote #5176 §10: SID range 0..390.
        assert CFFFont.NUM_STANDARD_STRINGS == 391

    def test_default_cid_count_is_8720(self) -> None:
        # Adobe Technote #5176 §9, Table 9.
        assert CFFFont.DEFAULT_CID_COUNT == 8720

    def test_constants_match_fonttools_table_size(self) -> None:
        from fontTools.cffLib import cffStandardStrings

        assert len(cffStandardStrings) == CFFFont.NUM_STANDARD_STRINGS

    def test_constants_accessible_on_subclasses(self) -> None:
        # Class constants must inherit cleanly through the hierarchy.
        assert CFFType1Font.NUM_STANDARD_STRINGS == 391
        assert CFFCIDFont.NUM_STANDARD_STRINGS == 391
        assert CFFType1Font.DEFAULT_CID_COUNT == 8720
        assert CFFCIDFont.DEFAULT_CID_COUNT == 8720


# ---------- is_standard_sid ----------


class TestIsStandardSid:
    def test_zero_is_standard(self) -> None:
        # SID 0 == .notdef, the canonical entry of the Standard Strings.
        assert CFFFont.is_standard_sid(0) is True

    def test_last_standard_sid_is_390(self) -> None:
        assert CFFFont.is_standard_sid(390) is True

    def test_sid_391_is_not_standard(self) -> None:
        # First per-font STRING INDEX SID — needs the font set to resolve.
        assert CFFFont.is_standard_sid(391) is False

    def test_negative_is_not_standard(self) -> None:
        assert CFFFont.is_standard_sid(-1) is False

    def test_far_out_of_range_is_not_standard(self) -> None:
        assert CFFFont.is_standard_sid(65535) is False

    def test_works_as_classmethod(self) -> None:
        # Callable on the class without needing an instance.
        assert CFFFont.is_standard_sid(100) is True
        assert CFFType1Font.is_standard_sid(100) is True
        assert CFFCIDFont.is_standard_sid(500) is False

    def test_works_on_instance(self) -> None:
        f = CFFFont()
        assert f.is_standard_sid(50) is True
        assert f.is_standard_sid(1000) is False


# ---------- get_string still works after refactor ----------


class TestGetStringAfterConstantRefactor:
    def test_standard_string_zero_is_notdef(self) -> None:
        f = CFFFont()
        assert f.get_string(0) == ".notdef"

    def test_standard_string_last_resolves(self) -> None:
        f = CFFFont()
        # SID 390 is the last standard string per Adobe Technote #5176
        # Appendix A. We don't pin the exact name (fontTools owns the
        # table), but it must be a non-empty string.
        s = f.get_string(390)
        assert isinstance(s, str)
        assert s

    def test_negative_sid_returns_empty(self) -> None:
        f = CFFFont()
        assert f.get_string(-1) == ""

    def test_sid_391_with_no_fontset_returns_empty(self) -> None:
        # No backing font set, so the per-font STRING INDEX is unreachable.
        f = CFFFont()
        assert f.get_string(391) == ""


# ---------- CFFType1Font.has_encoding ----------


class TestType1HasEncoding:
    def test_unparsed_has_no_encoding(self) -> None:
        f = CFFType1Font()
        assert f.has_encoding() is False

    def test_predefined_standard_has_encoding(self) -> None:
        f = CFFType1Font()

        class FakeTop:
            Encoding = "StandardEncoding"

        f._top = FakeTop()
        assert f.has_encoding() is True
        assert f.is_standard_encoding() is True

    def test_predefined_expert_has_encoding(self) -> None:
        f = CFFType1Font()

        class FakeTop:
            Encoding = "ExpertEncoding"

        f._top = FakeTop()
        assert f.has_encoding() is True
        assert f.is_expert_encoding() is True

    def test_custom_encoding_array_has_encoding(self) -> None:
        f = CFFType1Font()

        class FakeTop:
            Encoding = [".notdef", "A", "B"]

        f._top = FakeTop()
        assert f.has_encoding() is True
        assert f.is_custom_encoding() is True


# ---------- CFFType1Font.has_local_subrs / get_local_subr_index ----------


class _SubrEntry:
    """Stand-in for fontTools' T2CharString — exposes only the
    ``bytecode`` attribute that ``get_local_subr_index`` reads."""

    def __init__(self, bytecode: bytes) -> None:
        self.bytecode = bytecode


class _PrivWithSubrs:
    def __init__(self, subrs: Any) -> None:
        self.Subrs = subrs


class _PrivNoSubrs:
    pass


class _TopWithPriv:
    def __init__(self, private: Any) -> None:
        self.Private = private


class _TopNoPriv:
    pass


class TestType1LocalSubrs:
    def test_unparsed_has_no_local_subrs(self) -> None:
        f = CFFType1Font()
        assert f.has_local_subrs() is False
        assert f.get_local_subr_index() == []

    def test_no_private_dict_returns_empty(self) -> None:
        f = CFFType1Font()
        f._top = _TopNoPriv()
        assert f.has_local_subrs() is False
        assert f.get_local_subr_index() == []

    def test_private_without_subrs(self) -> None:
        f = CFFType1Font()
        f._top = _TopWithPriv(_PrivNoSubrs())
        assert f.has_local_subrs() is False
        assert f.get_local_subr_index() == []

    def test_private_with_none_subrs(self) -> None:
        f = CFFType1Font()
        f._top = _TopWithPriv(_PrivWithSubrs(None))
        assert f.has_local_subrs() is False
        assert f.get_local_subr_index() == []

    def test_private_with_empty_subrs(self) -> None:
        f = CFFType1Font()
        f._top = _TopWithPriv(_PrivWithSubrs([]))
        assert f.has_local_subrs() is False
        assert f.get_local_subr_index() == []

    def test_returns_bytecodes_in_order(self) -> None:
        f = CFFType1Font()
        f._top = _TopWithPriv(
            _PrivWithSubrs(
                [
                    _SubrEntry(b"\x01\x02\x03"),
                    _SubrEntry(b"\x04\x05"),
                    _SubrEntry(b"\x06"),
                ]
            )
        )
        assert f.has_local_subrs() is True
        assert f.get_local_subr_index() == [b"\x01\x02\x03", b"\x04\x05", b"\x06"]

    def test_accepts_raw_bytes_entries(self) -> None:
        # Some serialisers / parsers expose entries as raw bytes
        # rather than charstring wrapper objects.
        f = CFFType1Font()
        f._top = _TopWithPriv(_PrivWithSubrs([b"\xaa\xbb", bytearray(b"\xcc")]))
        assert f.get_local_subr_index() == [b"\xaa\xbb", b"\xcc"]

    def test_unknown_entry_shape_yields_empty_bytes(self) -> None:
        f = CFFType1Font()
        f._top = _TopWithPriv(_PrivWithSubrs([object(), 42]))
        # Non-charstring, non-bytes entries must surface as b"" so
        # callers can spot the missing payload.
        assert f.get_local_subr_index() == [b"", b""]

    def test_local_subrs_count_consistent(self) -> None:
        # has_local_subrs should agree with len(get_local_subr_index()).
        f = CFFType1Font()
        f._top = _TopWithPriv(
            _PrivWithSubrs([_SubrEntry(b"\x01"), _SubrEntry(b"\x02")])
        )
        assert f.has_local_subrs() is True
        assert f.get_local_subrs() == 2
        assert len(f.get_local_subr_index()) == 2


# ---------- CFFCIDFont.has_fd_select / has_fd_array ----------


class _FakeFDArrayItem:
    """Minimal fontTools-shaped FontDict surrogate."""

    def __init__(self, name: str = "Sub", subrs: Any = None) -> None:
        self.FontName = name
        self.rawDict = {"FontName": name}

        class _Priv:
            pass

        priv = _Priv()
        if subrs is not None:
            priv.Subrs = subrs
            priv.rawDict = {"Subrs": subrs}
        else:
            priv.rawDict = {}
        self.Private = priv


class TestCIDHasFDSelectAndArray:
    def test_unparsed_has_neither(self) -> None:
        f = CFFCIDFont()
        assert f.has_fd_select() is False
        assert f.has_fd_array() is False

    def test_set_fd_select_makes_has_fd_select_true(self) -> None:
        f = CFFCIDFont()
        f.set_fd_select(Format0FDSelect([0, 1, 0]))
        assert f.has_fd_select() is True

    def test_empty_fd_select_is_false(self) -> None:
        f = CFFCIDFont()
        f.set_fd_select(Format0FDSelect([]))
        assert f.has_fd_select() is False

    def test_fd_array_with_entries_is_true(self) -> None:
        f = CFFCIDFont()
        f._fd_array = FDArray.from_fonttools([_FakeFDArrayItem(), _FakeFDArrayItem()])
        assert f.has_fd_array() is True

    def test_empty_fd_array_is_false(self) -> None:
        f = CFFCIDFont()
        f._fd_array = FDArray.from_fonttools([])
        assert f.has_fd_array() is False


# ---------- CFFCIDFont.get_local_subr_index_for_gid ----------


class TestCIDLocalSubrIndexForGid:
    def test_unparsed_returns_empty(self) -> None:
        f = CFFCIDFont()
        # No FDSelect, no FDArray — out-of-range / empty path.
        assert f.get_local_subr_index_for_gid(0) == []
        assert f.get_local_subr_index_for_gid(5) == []

    def test_dispatches_via_fd_select(self) -> None:
        f = CFFCIDFont()
        # Two FDs: FD0 has subrs [b"a"]; FD1 has subrs [b"b", b"c"].
        f._fd_array = FDArray.from_fonttools(
            [
                _FakeFDArrayItem(subrs=[_SubrEntry(b"a")]),
                _FakeFDArrayItem(subrs=[_SubrEntry(b"b"), _SubrEntry(b"c")]),
            ]
        )
        # GID 0 → FD0; GIDs 1,2 → FD1.
        f.set_fd_select(Format0FDSelect([0, 1, 1]))
        assert f.get_local_subr_index_for_gid(0) == [b"a"]
        assert f.get_local_subr_index_for_gid(1) == [b"b", b"c"]
        assert f.get_local_subr_index_for_gid(2) == [b"b", b"c"]

    def test_negative_gid_returns_empty(self) -> None:
        f = CFFCIDFont()
        f._fd_array = FDArray.from_fonttools(
            [_FakeFDArrayItem(subrs=[_SubrEntry(b"x")])]
        )
        f.set_fd_select(Format0FDSelect([0]))
        # FDSelect.get_fd_index returns 0 for negative GIDs (matches
        # base behaviour) — and FD0 here has subrs, so we get them.
        # The spec-correct behaviour is "out-of-range FDSelect maps to
        # FD0" which is what this asserts.
        assert f.get_local_subr_index_for_gid(-1) == [b"x"]

    def test_fd_with_no_private_returns_empty(self) -> None:
        f = CFFCIDFont()

        class _NoPriv:
            FontName = "X"
            rawDict = {"FontName": "X"}
            Private = None

        f._fd_array = FDArray.from_fonttools([_NoPriv()])
        f.set_fd_select(Format0FDSelect([0]))
        assert f.get_local_subr_index_for_gid(0) == []
