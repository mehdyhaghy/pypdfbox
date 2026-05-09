from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.font import PDFontFactory
from pypdfbox.tools import info, texttopdf


class _FakeCOSDocument:
    def get_version(self) -> str:
        return "1.4"


class _CatalogRaisingVersion:
    def get_version(self) -> str:
        raise RuntimeError("malformed catalog")


class _FakeInformation:
    def get_title(self) -> str:
        return "Title"

    def get_author(self) -> str:
        return ""

    def get_subject(self) -> None:
        return None

    def get_keywords(self) -> str:
        return "keywords"

    def get_creator(self) -> str:
        return ""

    def get_producer(self) -> str:
        return "producer"

    def get_property_string_value(self, key: str) -> str:
        return {"CreationDate": "D:20260508000000", "ModDate": ""}[key]

    def get_trapped(self) -> str:
        return ""

    def get_metadata_keys(self) -> list[str]:
        return ["ZCustom", "Title", "ACustom", "Empty"]

    def get_custom_metadata_value(self, key: str) -> str:
        return {
            "ACustom": "first",
            "Empty": "",
            "Title": "ignored standard",
            "ZCustom": "last",
        }[key]


class _FakeInfoDocument:
    def get_document(self) -> _FakeCOSDocument:
        return _FakeCOSDocument()

    def get_document_catalog(self) -> _CatalogRaisingVersion:
        return _CatalogRaisingVersion()

    def get_document_information(self) -> _FakeInformation:
        return _FakeInformation()

    def get_version(self) -> float:
        return 1.6

    def get_number_of_pages(self) -> int:
        return 3

    def is_encrypted(self) -> bool:
        return True


def test_collect_info_skips_blank_values_and_sorts_custom_keys() -> None:
    snapshot = info._collect_info(_FakeInfoDocument(), Path("sample.pdf"))  # type: ignore[arg-type]  # noqa: SLF001

    assert snapshot == {
        "file": "sample.pdf",
        "header_version": "1.4",
        "catalog_version": None,
        "effective_version": 1.6,
        "pages": 3,
        "encrypted": True,
        "info": {
            "Title": "Title",
            "Keywords": "keywords",
            "Producer": "producer",
            "CreationDate": "D:20260508000000",
        },
        "custom": {"ACustom": "first", "ZCustom": "last"},
    }


def test_print_json_includes_xmp_only_when_present(
    capsys: pytest.CaptureFixture[str],
) -> None:
    snapshot: dict[str, object] = {
        "file": "x.pdf",
        "header_version": 1.7,
        "catalog_version": None,
        "effective_version": 1.7,
        "pages": 1,
        "encrypted": False,
        "info": {},
        "custom": {},
    }

    info._print_json(snapshot, "<xmp>é</xmp>")  # noqa: SLF001

    payload = json.loads(capsys.readouterr().out)
    assert payload["xmp"] == "<xmp>é</xmp>"
    assert payload["pages"] == 1


def test_read_xmp_falls_back_to_raw_stream_bytes() -> None:
    class _RawStream:
        def __enter__(self) -> io.BytesIO:
            return io.BytesIO(b"<xmp>\xff</xmp>")

        def __exit__(self, *args: object) -> None:
            pass

    class _Metadata:
        def get_metadata_as_string(self) -> str:
            raise RuntimeError("decode failed")

        def create_input_stream(self) -> _RawStream:
            return _RawStream()

    class _Catalog:
        def get_metadata(self) -> _Metadata:
            return _Metadata()

    class _Doc:
        def get_document_catalog(self) -> _Catalog:
            return _Catalog()

    assert info._read_xmp(_Doc()) == "<xmp>�</xmp>"  # type: ignore[arg-type]  # noqa: SLF001


def test_info_run_closes_document_loaded_by_tool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "in.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    closed: list[bool] = []

    class _Doc(_FakeInfoDocument):
        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(info.PDDocument, "load", lambda *args, **kwargs: _Doc())

    rc = info.run(
        argparse.Namespace(
            input=str(pdf),
            password="pw",
            metadata=False,
            output="json",
        )
    )

    assert rc == 0
    assert closed == [True]


def test_texttopdf_readlines_preserves_form_feed_and_trailing_blank() -> None:
    assert texttopdf._readlines("a\r\nb\rc\nbefore\fafter\n") == [  # noqa: SLF001
        "a",
        "b",
        "c",
        "before\fafter",
    ]
    assert texttopdf._readlines("one\n") == ["one"]  # noqa: SLF001


def test_texttopdf_split_words_preserves_trailing_empty_fields() -> None:
    assert texttopdf._split_words("a  b ") == ["a", "", "b", ""]  # noqa: SLF001


def test_texttopdf_string_width_fallback_for_font_without_width_api() -> None:
    class _FontWithoutWidth:
        pass

    assert texttopdf._string_width_units(_FontWithoutWidth(), "abcd") == 2000.0  # type: ignore[arg-type]  # noqa: SLF001


def test_create_pdf_from_text_accepts_plain_iterable_lines() -> None:
    doc = PDDocument()
    try:
        texttopdf.create_pdf_from_text(
            doc,
            ["alpha", "beta"],
            font=PDFontFactory.create_default_font(),
        )
        assert doc.get_number_of_pages() == 1
    finally:
        doc.close()


def test_texttopdf_run_media_box_overrides_page_size(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    src = tmp_path / "in.txt"
    src.write_text("x", encoding="utf-8")
    out = tmp_path / "out.pdf"
    calls: list[dict[str, Any]] = []

    def _fake_create_pdf_from_text_file(*args: Any, **kwargs: Any) -> None:
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(
        texttopdf,
        "create_pdf_from_text_file",
        _fake_create_pdf_from_text_file,
    )

    rc = texttopdf.run(
        argparse.Namespace(
            input=str(src),
            output=str(out),
            margins=[1, 2, 3, 4],
            media_box=[0, 0, 123, 456],
            page_size="Tabloid",
            font_size=11,
            standard_font="Helvetica",
            landscape=True,
            line_spacing=1.2,
            charset="latin-1",
        )
    )

    assert rc == 0
    kwargs = calls[0]["kwargs"]
    assert kwargs["page_size"] == "Tabloid"
    assert kwargs["left_margin"] == 1.0
    assert kwargs["right_margin"] == 2.0
    assert kwargs["top_margin"] == 3.0
    assert kwargs["bottom_margin"] == 4.0
    assert kwargs["media_box"].get_width() == pytest.approx(123.0)
    assert kwargs["media_box"].get_height() == pytest.approx(456.0)
