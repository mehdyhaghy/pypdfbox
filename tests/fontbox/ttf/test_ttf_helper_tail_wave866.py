from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf import DigitalSignatureTable
from tests.fontbox.ttf import test_true_type_font as true_type_mod


class _MissingFixture:
    def exists(self) -> bool:
        return False

    def __str__(self) -> str:
        return "missing-test-font.ttf"


def test_wave866_liberation_sans_fixture_skip_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(true_type_mod, "FIXTURE", _MissingFixture())

    with pytest.raises(pytest.skip.Exception):
        true_type_mod.liberation_sans.__wrapped__()


@pytest.mark.parametrize(
    ("test_func", "args"),
    [
        (true_type_mod.test_close_is_idempotent, ()),
        (true_type_mod.test_context_manager_closes, ()),
        (true_type_mod.test_enable_gsub_default, (object(),)),
        (true_type_mod.test_enable_disable_gsub_feature, ()),
        (true_type_mod.test_enable_vertical_substitutions_registers_vrt2_and_vert, ()),
        (true_type_mod.test_enabled_features_isolated_per_font, ()),
    ],
)
def test_wave866_fixture_dependent_tests_skip_without_fixture(
    monkeypatch: pytest.MonkeyPatch,
    test_func: object,
    args: tuple[object, ...],
) -> None:
    monkeypatch.setattr(true_type_mod, "FIXTURE", _MissingFixture())

    with pytest.raises(pytest.skip.Exception):
        test_func(*args)


class _FontWithDigitalSignature:
    def __init__(self) -> None:
        self._dsig = DigitalSignatureTable()

    def get_digital_signature(self) -> DigitalSignatureTable:
        return self._dsig

    def get_dsig(self) -> DigitalSignatureTable:
        return self._dsig


def test_wave866_digital_signature_alias_branch_with_present_table() -> None:
    true_type_mod.test_get_digital_signature_alias(_FontWithDigitalSignature())
