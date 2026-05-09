from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import COSArray
from pypdfbox.filter._predictor import _unpng
from pypdfbox.pdmodel.encryption import PDInvalidPasswordException
from pypdfbox.text.filtered_text_stripper import FilteredTextStripper
from pypdfbox.text.pdf_text_stripper import _TextState
from pypdfbox.text.text_position import TextPosition
from pypdfbox.tools import decrypt, encrypt


class _EmptySliceBytes:
    def __len__(self) -> int:
        return 1

    def __getitem__(self, key: object) -> bytes:
        return b""


def _decrypt_args(src: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "input": str(src),
        "output": None,
        "password": "owner",
        "key_store": None,
        "alias": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _encrypt_args(src: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "input": str(src),
        "output": None,
        "owner_password": "owner",
        "user_password": "user",
        "cert_files": [],
        "key_length": encrypt.DEFAULT_KEY_LENGTH,
        "can_assemble_document": True,
        "can_extract_content": True,
        "can_extract_for_accessibility": True,
        "can_fill_in_form": True,
        "can_modify": True,
        "can_modify_annotations": True,
        "can_print": True,
        "can_print_faithful": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_wave800_predictor_unpng_breaks_on_empty_sliced_row() -> None:
    assert _unpng(_EmptySliceBytes(), row_bytes=1, bytes_per_pixel=1) == b""


def test_wave800_text_position_generic_direction_adjustment() -> None:
    text = TextPosition(
        "x",
        x=3.0,
        y=4.0,
        font_size=12.0,
        dir=45.0,
        page_width=100.0,
        page_height=200.0,
    )

    expected_x = 3.0 * math.cos(math.pi / 4) + 4.0 * math.sin(math.pi / 4)
    expected_y = -3.0 * math.sin(math.pi / 4) + 4.0 * math.cos(math.pi / 4)

    assert text.get_x_dir_adj() == pytest.approx(expected_x)
    assert text.get_y_dir_adj() == pytest.approx(expected_y)


def test_wave800_filtered_text_stripper_skips_tj_array_for_other_angle() -> None:
    stripper = FilteredTextStripper(target_angle=0)
    state = _TextState()
    state.tm_b = 1.0
    state.tm_d = 0.0
    positions: list[TextPosition] = []

    stripper._emit_tj_array(COSArray(), state, positions)  # noqa: SLF001

    assert positions == []


def test_wave800_decrypt_keystore_oserror_returns_four(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "encrypted.pdf"
    src.write_bytes(b"%PDF-1.4\n")

    def _raise_oserror(*args: object, **kwargs: object) -> object:
        raise OSError("bad keystore")

    monkeypatch.setattr(decrypt, "_load_pkcs12_keystore", _raise_oserror)

    rc = decrypt.run(_decrypt_args(src, key_store=str(tmp_path / "keys.p12")))

    assert rc == 4
    assert "bad keystore" in capsys.readouterr().out


def test_wave800_decrypt_in_place_invalid_password_from_save_path_returns_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "encrypted.pdf"
    src.write_bytes(b"%PDF-1.4\n")

    class _Permission:
        def is_owner_permission(self) -> bool:
            return True

    class _Probe:
        def __enter__(self) -> _Probe:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def is_encrypted(self) -> bool:
            return True

        def get_current_access_permission(self) -> _Permission:
            return _Permission()

    def _raise_invalid_password(*args: object, **kwargs: object) -> None:
        raise PDInvalidPasswordException("still locked")

    monkeypatch.setattr(decrypt.PDDocument, "load", lambda *a, **k: _Probe())
    monkeypatch.setattr(decrypt, "decrypt_pdf", _raise_invalid_password)

    rc = decrypt.run(_decrypt_args(src))

    assert rc == 1
    assert "still locked" in capsys.readouterr().out
    assert list(tmp_path.glob(".encrypted.pdf.*.tmp")) == []


def test_wave800_encrypt_resolve_oserror_falls_back_to_path_equality(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "plain.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    calls: list[tuple[Path, Path, dict[str, Any]]] = []

    class _Probe:
        def __enter__(self) -> _Probe:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def is_encrypted(self) -> bool:
            return False

        def get_signature_dictionaries(self) -> list[object]:
            return []

    def _resolve_raises(self: Path) -> Path:
        raise OSError("cannot resolve")

    def _encrypt_pdf(input_path: Path, output_path: Path, **kwargs: Any) -> None:
        calls.append((input_path, output_path, kwargs))

    monkeypatch.setattr(encrypt.PDDocument, "load", lambda *a, **k: _Probe())
    monkeypatch.setattr(encrypt.Path, "resolve", _resolve_raises)
    monkeypatch.setattr(encrypt, "encrypt_pdf", _encrypt_pdf)

    rc = encrypt.run(_encrypt_args(src))

    assert rc == 0
    assert calls
    assert calls[0][0] == src
    assert calls[0][1].name.startswith(".plain.pdf.")
