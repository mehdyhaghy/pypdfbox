from __future__ import annotations

import pytest

import tests.pdmodel.encryption.upstream.test_public_key_security_handler as upstream


def test_wave909_public_key_roundtrip_skip_branch_when_cert_generation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_cert_generation() -> tuple[object, object]:
        raise RuntimeError("no crypto backend")

    monkeypatch.setattr(upstream, "_build_self_signed_rsa", fail_cert_generation)

    with pytest.raises(pytest.skip.Exception, match="cert generation too heavy"):
        upstream.test_recipients_round_trip_preserves_key_and_permissions(128)


def test_wave909_wrong_key_skip_branch_when_second_cert_generation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_cert_generation() -> tuple[object, object]:
        raise RuntimeError("no crypto backend")

    monkeypatch.setattr(upstream, "_build_self_signed_rsa", fail_cert_generation)

    with pytest.raises(pytest.skip.Exception, match="cert generation too heavy"):
        upstream.test_wrong_private_key_raises_value_error()
