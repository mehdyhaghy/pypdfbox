"""Wave 393 residual coverage for pdfdebugger cold branches."""
from __future__ import annotations

import argparse
import builtins
import json
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.tools import cli, pdfdebugger


class _FakeDoc:
    def __init__(self, cos_doc: COSDocument) -> None:
        self._cos_doc = cos_doc

    def get_document(self) -> COSDocument:
        return self._cos_doc


class _ErrorStream(COSStream):
    def create_raw_input_stream(self) -> Any:
        raise OSError("raw unavailable")

    def to_byte_array(self) -> bytes:
        raise ValueError("decode unavailable")


class _FakeEncryption:
    def get_filter(self) -> str:
        return "Standard"

    def get_sub_filter(self) -> None:
        return None

    def get_v(self) -> int:
        return 4

    def get_revision(self) -> int:
        return 5

    def get_length(self) -> int:
        return 128

    def get_p(self) -> int:
        return -4

    def is_encrypt_meta_data(self) -> bool:
        return True

    def get_u(self) -> bytes:
        return b"uvwxyz"

    def get_o(self) -> bytes:
        return b"opqrst"


class _EncryptedCosDoc:
    def __init__(self, encrypted: bool) -> None:
        self._encrypted = encrypted

    def is_encrypted(self) -> bool:
        return self._encrypted


class _EncryptionDoc:
    def __init__(self, *, encrypted: bool, enc: object | None = None) -> None:
        self._cos_doc = _EncryptedCosDoc(encrypted)
        self._enc = enc

    def get_document(self) -> _EncryptedCosDoc:
        return self._cos_doc

    def get_encryption(self) -> object | None:
        return self._enc


class _PageDoc:
    def get_number_of_pages(self) -> int:
        return 0


class _SummaryDoc:
    def __init__(self, cos_doc: COSDocument) -> None:
        self._cos_doc = cos_doc

    def get_document(self) -> COSDocument:
        return self._cos_doc

    def get_version(self) -> float:
        return 1.7

    def get_number_of_pages(self) -> int:
        return 0

    def is_encrypted(self) -> bool:
        return False


def test_wave393_formatters_cover_cycles_filters_arrays_and_json_scalars() -> None:
    cycle = COSDictionary()
    cycle.set_item("Self", cycle)
    out: list[str] = []
    pdfdebugger._format_node(cycle, 0, out, visited=set())
    assert "    ... (cycle)" in out

    stream = COSStream()
    try:
        stream.set_data(b"filtered")
        stream.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
        out = []
        pdfdebugger._format_node(stream, 0, out, visited=set())
        assert out[0] == "<<  (stream, length=8 filter=/FlateDecode)"
    finally:
        stream.close()

    complex_array = COSArray([COSInteger.get(1), COSDictionary()])
    out = []
    pdfdebugger._format_node(complex_array, 0, out, visited=set())
    assert out[0] == "["
    assert out[-1] == "]"

    assert pdfdebugger._node_to_jsonable(
        None, visited=set(), depth=0, follow_refs=False, max_depth=3
    ) is None
    assert (
        pdfdebugger._node_to_jsonable(
            COSBoolean.TRUE, visited=set(), depth=0, follow_refs=False, max_depth=3
        )
        is True
    )
    assert pdfdebugger._node_to_jsonable(
        COSFloat("2.25"), visited=set(), depth=0, follow_refs=False, max_depth=3
    ) == 2.25
    assert pdfdebugger._node_to_jsonable(
        COSNull.NULL, visited=set(), depth=0, follow_refs=False, max_depth=3
    ) is None


def test_wave393_mode_helpers_cover_json_text_and_error_edges(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cos_doc = COSDocument()
    normal_stream = COSStream()
    stream = _ErrorStream()
    try:
        normal_stream.set_data(b"abc")
        normal_key = COSObjectKey(7, 0)
        stream_key = COSObjectKey(8, 0)
        scalar_key = COSObjectKey(9, 0)
        cos_doc.get_object_from_pool(normal_key).set_object(normal_stream)
        cos_doc.get_object_from_pool(stream_key).set_object(stream)
        cos_doc.get_object_from_pool(scalar_key).set_object(COSInteger.get(7))
        doc = _FakeDoc(cos_doc)

        pdfdebugger._print_trailer(doc)  # type: ignore[arg-type]
        assert "<no trailer>" in capsys.readouterr().out

        trailer = COSDictionary()
        trailer.set_item("Size", COSInteger.get(2))
        catalog = COSDictionary()
        catalog.set_item("Type", COSName.get_pdf_name("Catalog"))
        catalog.set_item("Pages", COSInteger.get(12))
        trailer.set_item("Root", catalog)
        cos_doc.set_trailer(trailer)
        pdfdebugger._print_trailer(doc, output_format="json")  # type: ignore[arg-type]
        trailer_payload = json.loads(capsys.readouterr().out)
        assert trailer_payload["trailer"]["Size"] == 2

        pdfdebugger._print_summary(_SummaryDoc(cos_doc), Path("sample.pdf"))  # type: ignore[arg-type]
        assert "Catalog /Pages: 12" in capsys.readouterr().out

        assert pdfdebugger._print_catalog(doc, output_format="json") == 0  # type: ignore[arg-type]
        assert json.loads(capsys.readouterr().out)["catalog"]["Type"] == "/Catalog"

        assert (
            pdfdebugger._print_object(  # type: ignore[arg-type]
                doc, scalar_key.object_number, scalar_key.generation_number, output_format="json"
            )
            == 0
        )
        assert json.loads(capsys.readouterr().out)["value"] == 7

        assert (
            pdfdebugger._dump_stream(  # type: ignore[arg-type]
                doc, normal_key.object_number, normal_key.generation_number
            )
            == 0
        )
        assert "00000000  61 62 63" in capsys.readouterr().out

        assert pdfdebugger._dump_stream(doc, 123, 0) == 4  # type: ignore[arg-type]
        assert "not in pool" in capsys.readouterr().out

        assert (
            pdfdebugger._dump_stream(  # type: ignore[arg-type]
                doc, stream_key.object_number, stream_key.generation_number
            )
            == 0
        )
        dump_text = capsys.readouterr().out
        assert "<error: raw unavailable>" in dump_text
        assert "<error: decode unavailable>" in dump_text

        assert (
            pdfdebugger._dump_stream(  # type: ignore[arg-type]
                doc,
                stream_key.object_number,
                stream_key.generation_number,
                output_format="json",
            )
            == 0
        )
        payload = json.loads(capsys.readouterr().out)
        assert payload["raw_error"] == "raw unavailable"
        assert payload["decoded_error"] == "decode unavailable"
    finally:
        normal_stream.close()
        stream.close()
        cos_doc.close()


def test_wave393_tokens_encryption_and_walker_edge_helpers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    array = COSArray([COSInteger.get(1), COSString("two")])
    dictionary = COSDictionary()
    dictionary.set_item("A", array)
    assert pdfdebugger._format_token(array) == "[ 1 (two) ]"
    assert pdfdebugger._format_token(dictionary) == "<< /A [ 1 (two) ] >>"
    assert pdfdebugger._format_token(object()).startswith("<object object at ")

    assert pdfdebugger._print_page_tokens(_PageDoc(), 1) == 4  # type: ignore[arg-type]
    assert "page 1 out of range (1..0)" in capsys.readouterr().out

    assert pdfdebugger._print_encryption(_EncryptionDoc(encrypted=False)) == 0  # type: ignore[arg-type]
    assert "Encryption: <not encrypted>" in capsys.readouterr().out

    assert pdfdebugger._print_encryption(_EncryptionDoc(encrypted=True)) == 0  # type: ignore[arg-type]
    assert "<encrypted but /Encrypt dict missing>" in capsys.readouterr().out

    assert (
        pdfdebugger._print_encryption(  # type: ignore[arg-type]
            _EncryptionDoc(encrypted=True, enc=_FakeEncryption()), output_format="json"
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["u_hex_prefix"] == "75767778"
    assert payload["o_hex_prefix"] == "6f707172"

    assert pdfdebugger._walker_lookup_child(None, "Anything") is None
    assert pdfdebugger._walker_lookup_child(COSInteger.get(1), "Anything") is None
    assert pdfdebugger._walker_find_in_subtree(None, "A") == []
    assert pdfdebugger._walker_find_in_subtree(dictionary, "A", max_results=0) == []

    empty_stream = COSStream()
    try:
        assert "stream has no data" in pdfdebugger._walker_stream_preview(
            empty_stream, mode="raw"
        )
    finally:
        empty_stream.close()


def test_wave393_interactive_walker_blank_help_and_cd_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cos_doc = COSDocument()
    trailer = COSDictionary()
    trailer.set_item("Root", COSDictionary())
    cos_doc.set_trailer(trailer)
    commands = iter(["", "help", "cd", "cd Missing", "quit"])
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(commands))
    try:
        assert pdfdebugger._interactive_walker(_FakeDoc(cos_doc)) == 0  # type: ignore[arg-type]
    finally:
        cos_doc.close()

    out = capsys.readouterr().out
    assert "Commands:" in out
    assert "cd: usage: cd <key|index>" in out
    assert "cd: no child 'Missing'" in out


def test_wave393_cli_rejects_bad_object_specs_and_load_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    make_pdf,
) -> None:
    pdf = make_pdf(page_count=1)

    assert cli.run_cli(["pdfdebugger", str(pdf), "-object", "not-int"]) == 2
    assert "-object expects non-negative integer" in capsys.readouterr().out

    assert cli.run_cli(["pdfdebugger", str(pdf), "--show-object", "1.bad"]) == 2
    assert "--show-object expects NUM[.GEN]" in capsys.readouterr().out

    assert cli.run_cli(["pdfdebugger", str(pdf), "--dump-stream", "1.bad"]) == 2
    assert "--dump-stream expects NUM[.GEN]" in capsys.readouterr().out

    broken_pdf = tmp_path / "broken.pdf"
    broken_pdf.write_bytes(b"%PDF-not-really")

    def raise_load(_src: Path, **_kwargs: object) -> object:
        raise OSError("load failed")

    monkeypatch.setattr(pdfdebugger.PDDocument, "load", raise_load)
    args = argparse.Namespace(
        input=str(broken_pdf),
        depth=24,
        password=None,
        output_format="text",
    )
    assert pdfdebugger.run(args) == 4
    assert "cannot open" in capsys.readouterr().out
    assert pdfdebugger._parse_show_object("abc") is None


def test_wave393_cli_valid_show_object_and_interactive_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    make_pdf,
) -> None:
    pdf = make_pdf(page_count=1)

    with pdfdebugger.PDDocument.load(pdf) as doc:
        root = doc.get_document().get_trailer().get_item(COSName.ROOT)
        assert root is not None
        num = root.object_number
        gen = root.generation_number

    assert cli.run_cli(["pdfdebugger", str(pdf), "--show-object", f"{num}.{gen}"]) == 0
    assert f"Object {num} {gen} R:" in capsys.readouterr().out

    monkeypatch.setattr(builtins, "input", lambda _prompt: "q")
    assert cli.run_cli(["pdfdebugger", str(pdf), "--interactive"]) == 0
    assert "pdfdebugger interactive walker" in capsys.readouterr().out
