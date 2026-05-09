from __future__ import annotations

import pytest

from tests.pdmodel.encryption import test_public_key_security_handler as target


def test_wave990_round_trip_skip_branch_when_cert_generation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_cert_generation() -> tuple[object, object]:
        raise RuntimeError("no crypto backend")

    monkeypatch.setattr(target, "_build_self_signed_rsa", fail_cert_generation)

    with pytest.raises(pytest.skip.Exception, match="cert generation too heavy"):
        target.test_prepare_document_round_trip_matches_decrypt_path(128)
