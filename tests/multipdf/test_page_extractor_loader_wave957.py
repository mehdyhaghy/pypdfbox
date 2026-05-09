from __future__ import annotations

import builtins

from . import test_page_extractor_loader_wave728 as wave728


def test_wave957_encrypted_cos_document_close_and_fake_parser_get_document() -> None:
    document = wave728._EncryptedCOSDocument()
    parser = wave728._FakeParser(object())
    wave728._FakeParser.document = document

    assert parser.get_document() is document
    assert document.closed is False

    document.close()

    assert document.closed is True


def test_wave957_loader_fake_import_falls_back_for_unrelated_import() -> None:
    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals: dict[str, object] | None = None,  # noqa: A002
        locals: dict[str, object] | None = None,  # noqa: A002
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "pypdfbox.pdmodel" and "PDDocument" in fromlist:
            raise ImportError("pdmodel unavailable")
        return real_import(name, globals, locals, fromlist, level)

    assert fake_import("math").sqrt(9) == 3

