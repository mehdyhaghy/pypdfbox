from types import ModuleType

import pytest

from tests.fontbox.cff import test_cff_cid_font as cid_mod
from tests.fontbox.cff import test_cff_font_parity as parity_mod
from tests.fontbox.cff import test_cff_type1_font as type1_mod
from tests.fontbox.cff import test_type2_char_string as type2_mod


class _BrokenTTFont:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("cannot open fixture")


@pytest.mark.parametrize(
    ("module", "fixture_name", "bytes_name"),
    [
        (parity_mod, "cff_font", "_CFF_BYTES"),
        (type1_mod, "type1_font", "_TYPE1_BYTES"),
        (type2_mod, "cff_font", "_CFF_BYTES"),
    ],
)
def test_wave856_cff_font_fixtures_skip_when_host_fixture_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    fixture_name: str,
    bytes_name: str,
) -> None:
    monkeypatch.setattr(module, bytes_name, None)

    with pytest.raises(pytest.skip.Exception):
        getattr(module, fixture_name).__wrapped__()


def test_wave856_type1_predefined_encoding_test_exercises_expert_branch() -> None:
    class _ExpertFont:
        def is_standard_encoding(self) -> bool:
            return False

        def is_expert_encoding(self) -> bool:
            return True

        def code_to_name(self, code: int) -> str:
            assert code == 65
            return "Asmall"

    type1_mod.test_parsed_type1_code_to_name_predefined(_ExpertFont())


def test_wave856_type1_from_bytes_rejects_cid_needs_no_system_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The CID rejection test reads a bundled CID-keyed CFF fixture; it must
    # not fall back to recompiling a system font through fontTools.
    from fontTools import ttLib

    monkeypatch.setattr(ttLib, "TTFont", _BrokenTTFont)

    type1_mod.TestCFFType1FontFromCIDFontRaises().test_from_bytes_rejects_cid_keyed()


def test_wave856_type1_from_bytes_rejects_cid_fails_without_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If CFFType1Font.from_bytes stopped rejecting CID-keyed input, the
    # rejection test must fail rather than pass vacuously.
    monkeypatch.setattr(
        type1_mod.CFFType1Font,
        "from_bytes",
        classmethod(lambda cls, data: cls()),
    )

    with pytest.raises(pytest.fail.Exception):
        type1_mod.TestCFFType1FontFromCIDFontRaises().test_from_bytes_rejects_cid_keyed()


def test_wave856_cid_from_bytes_rejects_name_keyed_needs_no_system_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The name-keyed rejection test reads a bundled name-keyed CFF fixture;
    # it must not fall back to recompiling a system font through fontTools.
    from fontTools import ttLib

    monkeypatch.setattr(ttLib, "TTFont", _BrokenTTFont)

    cid_mod.TestCFFCIDFontFromNonCIDRaises().test_from_bytes_rejects_name_keyed()


def test_wave856_cid_from_bytes_rejects_name_keyed_fails_without_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If CFFCIDFont.from_bytes stopped rejecting name-keyed input, the
    # rejection test must fail rather than pass vacuously.
    monkeypatch.setattr(
        cid_mod.CFFCIDFont,
        "from_bytes",
        classmethod(lambda cls, data: cls()),
    )

    with pytest.raises(pytest.fail.Exception):
        cid_mod.TestCFFCIDFontFromNonCIDRaises().test_from_bytes_rejects_name_keyed()


def test_wave856_cid_font_fixture_needs_no_system_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The parsed-font fixture loads the bundled CID-keyed CFF; it must not
    # recompile a host CJK font through fontTools.
    from fontTools import ttLib

    monkeypatch.setattr(ttLib, "TTFont", _BrokenTTFont)

    font = cid_mod.cid_font.__wrapped__()
    assert font.is_cid_font() is True


def test_wave856_cid_font_fixture_is_multi_fd() -> None:
    # The fixture must keep discriminating between several font-dicts so
    # the per-FD tests exercise real FDSelect dispatch.
    font = cid_mod.cid_font.__wrapped__()
    assert font.get_fd_array().size() == 3
    fds = {font.get_fd_select().get_fd_index(gid) for gid in range(8)}
    assert fds == {0, 1, 2}
