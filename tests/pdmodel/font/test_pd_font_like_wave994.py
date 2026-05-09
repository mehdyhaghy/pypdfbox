from __future__ import annotations

from typing import cast

from tests.pdmodel.font import test_pd_font_like as target


def test_wave994_wrong_signature_get_name_body_is_exercised() -> None:
    target.test_protocol_runtime_checkable_does_not_check_signatures()
    wrong_sig = cast(type, target._WrongSig)

    assert wrong_sig().get_name() == 1


def test_wave994_extended_extra_body_is_exercised() -> None:
    target.test_protocol_inheritance_disabled_for_runtime_check_only()
    extended = cast(type, target._ExtendedFontLike)

    assert extended().extra() is None
