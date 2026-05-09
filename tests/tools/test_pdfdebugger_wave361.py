"""Wave 361 coverage for ``pypdfbox pdfdebugger`` tool modes."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.tools import cli, pdfdebugger

_CONTENT = b"BT /F1 12 Tf 50 700 Td (wave361 tokens) Tj ET"


def _write_pdf_with_stream(path: Path) -> Path:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        stream = COSStream()
        with stream.create_raw_output_stream() as out:
            out.write(_CONTENT)
        page.set_contents(stream)
        doc.save(path)
    finally:
        doc.close()
    return path


def _first_stream_key(path: Path) -> COSObjectKey:
    with PDDocument.load(path) as doc:
        cos_doc = doc.get_document()
        for key in cos_doc.get_object_keys():
            obj = cos_doc.get_object_from_pool(key).get_object()
            if isinstance(obj, COSStream):
                return key
    raise AssertionError("expected at least one indirect stream")


def _write_encrypted(path: Path, *, owner: str = "owner", user: str = "user") -> Path:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        stream = COSStream()
        with stream.create_raw_output_stream() as out:
            out.write(_CONTENT)
        page.set_contents(stream)
        doc.protect(
            StandardProtectionPolicy(
                owner_password=owner,
                user_password=user,
                permissions=AccessPermission(),
            )
        )
        doc.save(path)
    finally:
        doc.close()
    return path


def test_wave361_json_summary_and_page_modes(
    capsys: pytest.CaptureFixture[str], make_pdf: Callable[..., Path]
) -> None:
    pdf = make_pdf(page_count=1)

    assert cli.run_cli(["pdfdebugger", str(pdf), "--format", "json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["file"] == str(pdf)
    assert summary["pages"] == 1
    assert summary["encrypted"] is False
    assert "/Root" in summary["trailer_keys"]

    assert cli.run_cli(["pdfdebugger", str(pdf), "-page", "1", "--format", "json"]) == 0
    page = json.loads(capsys.readouterr().out)
    assert page["page"] == 1
    assert page["dict"]["Type"] == "/Page"


def test_wave361_list_objects_json_reports_xref_states(
    capsys: pytest.CaptureFixture[str], make_pdf: Callable[..., Path]
) -> None:
    pdf = make_pdf(page_count=1)

    assert cli.run_cli(["pdfdebugger", str(pdf), "--list-objects", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["entries"]
    assert {entry["state"] for entry in payload["entries"]} <= {
        "used",
        "synthetic",
        "in_objstm",
        "free",
    }
    expected_keys = {"object_number", "generation_number", "state"}
    assert all(expected_keys <= set(e) for e in payload["entries"])


def test_wave361_xref_state_helper_handles_free_synthetic_and_objstm() -> None:
    cos_doc = COSDocument()
    try:
        used = COSObjectKey(7, 0)
        objstm = COSObjectKey(8, 0)
        synthetic = COSObjectKey(9, 0)
        cos_doc.add_xref_table({used: 123, objstm: -42})
        cos_doc.get_object_from_pool(synthetic)

        assert pdfdebugger._xref_state_for(cos_doc, COSObjectKey(0, 65535)) == (
            "free",
            0,
            None,
        )
        assert pdfdebugger._xref_state_for(cos_doc, used) == ("used", 123, None)
        assert pdfdebugger._xref_state_for(cos_doc, objstm) == ("in_objstm", None, 42)
        assert pdfdebugger._xref_state_for(cos_doc, synthetic) == (
            "synthetic",
            None,
            None,
        )
    finally:
        cos_doc.close()


def test_wave361_dump_stream_json_and_not_stream_error(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    pdf = _write_pdf_with_stream(tmp_path / "stream.pdf")
    stream_key = _first_stream_key(pdf)

    assert (
        cli.run_cli(
            [
                "pdfdebugger",
                str(pdf),
                "--dump-stream",
                f"{stream_key.object_number}.{stream_key.generation_number}",
                "--format",
                "json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["object_number"] == stream_key.object_number
    assert payload["raw_length"] > 0
    assert bytes.fromhex(payload["decoded_hex"]) == _CONTENT

    assert cli.run_cli(["pdfdebugger", str(pdf), "--dump-stream", "1.0"]) == 4
    assert "is not a stream" in capsys.readouterr().out


def test_wave361_page_tokens_text_and_json(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    pdf = _write_pdf_with_stream(tmp_path / "tokens.pdf")

    assert cli.run_cli(["pdfdebugger", str(pdf), "--show-page-tokens", "1"]) == 0
    text = capsys.readouterr().out
    assert "Page 1 content stream" in text
    assert "BT" in text
    assert "Tj" in text

    assert (
        cli.run_cli(
            ["pdfdebugger", str(pdf), "--show-page-tokens", "1", "--format", "json"]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["page"] == 1
    assert {"op": "BT"} in payload["tokens"]
    assert {"op": "ET"} in payload["tokens"]


def test_wave361_show_encryption_text_truncates_hashes(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    pdf = _write_encrypted(tmp_path / "encrypted.pdf")

    assert (
        cli.run_cli(
            [
                "pdfdebugger",
                str(pdf),
                "--password",
                "user",
                "--show-encryption",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "Encryption:" in out
    assert "/Filter" in out
    assert "/U (prefix)" in out
    assert "... (truncated for security)" in out


def test_wave361_json_encryption_handles_missing_dictionary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeCosDoc:
        def is_encrypted(self) -> bool:
            return True

    class FakeDoc:
        def get_document(self) -> FakeCosDoc:
            return FakeCosDoc()

        def get_encryption(self) -> None:
            return None

    assert pdfdebugger._print_encryption(FakeDoc(), output_format="json") == 0  # type: ignore[arg-type]
    assert json.loads(capsys.readouterr().out) == {
        "encrypted": True,
        "encryption": None,
    }


def test_wave361_node_json_handles_cycles_streams_and_depth() -> None:
    stream = COSStream()
    stream.set_data(b"decoded-preview")
    stream.set_item("Marker", COSName.get_pdf_name("Yes"))
    dictionary = COSDictionary()
    dictionary.set_item("Stream", stream)
    dictionary.set_item("Self", dictionary)

    payload = pdfdebugger._node_to_jsonable(
        dictionary,
        visited=set(),
        depth=0,
        follow_refs=False,
        max_depth=4,
    )
    assert payload["Self"] == {"truncated": "cycle"}
    assert payload["Stream"]["type"] == "stream"
    assert payload["Stream"]["preview_hex"] == b"decoded-preview".hex()

    assert pdfdebugger._node_to_jsonable(
        dictionary,
        visited=set(),
        depth=0,
        follow_refs=False,
        max_depth=0,
    ) == {"truncated": "max depth"}
    stream.close()


def test_wave361_walker_helpers_cover_navigation_and_stream_previews() -> None:
    arr = COSArray([COSInteger.get(2)])
    child = COSDictionary()
    child.set_item("Kids", arr)
    root = COSDictionary()
    root.set_item("Child", COSObject(5, 0, resolved=child))

    assert pdfdebugger._walker_lookup_child(root, "Child") is not None
    assert pdfdebugger._walker_lookup_child(arr, "[0]") == COSInteger.get(2)
    assert pdfdebugger._walker_lookup_child(arr, "99") is None
    assert pdfdebugger._walker_find_in_subtree(root, "/Kids") == ["/Child/Kids"]
    assert pdfdebugger._walker_stream_preview(root, mode="raw") == "<not a stream>"


def test_wave361_hex_dump_empty_and_truncated() -> None:
    assert pdfdebugger._hex_dump(b"") == "<empty>"

    dump = pdfdebugger._hex_dump(b"abcdef", width=2, max_lines=2)

    assert "00000000  61 62  |ab|" in dump
    assert "... (2 more bytes)" in dump
