from __future__ import annotations

import argparse
import math
from pathlib import Path
from unittest.mock import patch

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSString
from pypdfbox.pdmodel.encryption import InvalidPasswordException
from pypdfbox.text import FilteredTextStripper, TextPosition
from pypdfbox.text.pdf_text_stripper import PDFTextStripper, _TextState
from pypdfbox.tools import decrypt, encrypt


def _position(**overrides: object) -> TextPosition:
    values: dict[str, object] = {
        "text": "x",
        "x": 10.0,
        "y": 20.0,
        "font_size": 12.0,
        "width": 6.0,
        "page_width": 200.0,
        "page_height": 300.0,
    }
    values.update(overrides)
    return TextPosition(**values)


def test_wave790_text_position_generic_direction_adjustment() -> None:
    pos = _position(dir=45.0)

    assert pos.get_x_dir_adj() == pytest.approx(
        10.0 * math.cos(math.radians(45.0)) + 20.0 * math.sin(math.radians(45.0))
    )
    assert pos.get_y_dir_adj() == pytest.approx(
        -10.0 * math.sin(math.radians(45.0)) + 20.0 * math.cos(math.radians(45.0))
    )


def test_wave790_filtered_tj_array_returns_before_base_emit_when_angle_differs() -> None:
    state = _TextState()
    state.tm_b = 1.0
    state.tm_d = 0.0
    arr = COSArray([COSString("ignored"), COSInteger.get(-500)])
    positions: list[TextPosition] = []
    stripper = FilteredTextStripper(target_angle=0)

    with patch.object(PDFTextStripper, "_emit_tj_array") as base_emit:
        stripper._emit_tj_array(arr, state, positions)  # noqa: SLF001

    base_emit.assert_not_called()
    assert positions == []
    assert state.text_x == 0.0


def test_wave790_filtered_tj_array_delegates_when_angle_matches() -> None:
    state = _TextState()
    arr = COSArray([COSString("shown")])
    positions: list[TextPosition] = []
    stripper = FilteredTextStripper(target_angle=0)

    with patch.object(PDFTextStripper, "_emit_tj_array") as base_emit:
        stripper._emit_tj_array(arr, state, positions)  # noqa: SLF001

    base_emit.assert_called_once_with(arr, state, positions)


def test_wave790_decrypt_keystore_oserror_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "input.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    key_store = tmp_path / "key.p12"
    key_store.write_bytes(b"placeholder")

    def _raise_oserror(
        keystore_path: str | Path,
        alias: str | None,
        password: str,
    ) -> object:
        raise OSError("bad keystore")

    monkeypatch.setattr(decrypt, "_load_pkcs12_keystore", _raise_oserror)

    rc = decrypt.run(
        argparse.Namespace(
            input=str(src),
            output=str(tmp_path / "out.pdf"),
            password="secret",
            key_store=str(key_store),
            alias="a",
        )
    )

    assert rc == 4
    assert "bad keystore" in capsys.readouterr().out


def test_wave790_decrypt_in_place_invalid_password_during_save_branch(
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

        def __exit__(self, *exc: object) -> None:
            return None

        def is_encrypted(self) -> bool:
            return True

        def get_current_access_permission(self) -> _Permission:
            return _Permission()

    def _load(*args: object, **kwargs: object) -> _Probe:
        return _Probe()

    def _decrypt_pdf(*args: object, **kwargs: object) -> None:
        raise InvalidPasswordException("password failed after probe")

    monkeypatch.setattr(decrypt.PDDocument, "load", _load)
    monkeypatch.setattr(decrypt, "decrypt_pdf", _decrypt_pdf)

    rc = decrypt.run(
        argparse.Namespace(
            input=str(src),
            output=None,
            password="owner",
            key_store=None,
            alias=None,
        )
    )

    assert rc == 1
    assert "password failed after probe" in capsys.readouterr().out
    assert list(src.parent.glob(f".{src.name}.*.tmp")) == []


def test_wave790_encrypt_same_output_falls_back_when_resolve_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "plain.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    calls: list[tuple[Path, Path]] = []

    class _Probe:
        def __enter__(self) -> _Probe:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def is_encrypted(self) -> bool:
            return False

        def get_signature_dictionaries(self) -> list[object]:
            return []

    def _load(*args: object, **kwargs: object) -> _Probe:
        return _Probe()

    def _resolve(self: Path) -> Path:
        raise OSError("resolve unavailable")

    def _encrypt_pdf(
        input_path: str | Path,
        output_path: str | Path,
        **kwargs: object,
    ) -> None:
        calls.append((Path(input_path), Path(output_path)))
        Path(output_path).write_bytes(b"%PDF-1.4 encrypted\n")

    monkeypatch.setattr(encrypt.PDDocument, "load", _load)
    monkeypatch.setattr(encrypt.Path, "resolve", _resolve)
    monkeypatch.setattr(encrypt, "encrypt_pdf", _encrypt_pdf)

    rc = encrypt.run(
        argparse.Namespace(
            input=str(src),
            output=str(src),
            owner_password=None,
            user_password="user",
            cert_files=[],
            key_length=128,
            can_assemble_document=True,
            can_extract_content=True,
            can_extract_for_accessibility=True,
            can_fill_in_form=True,
            can_modify=True,
            can_modify_annotations=True,
            can_print=True,
            can_print_faithful=True,
        )
    )

    assert rc == 0
    assert calls and calls[0][0] == src
    assert src.read_bytes() == b"%PDF-1.4 encrypted\n"
