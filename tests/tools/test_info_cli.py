"""Round-out CLI tests for ``pypdfbox info``.

Hand-written; exercises ``-password``, ``-metadata`` (XMP), ``-output txt|json``,
and the documented metadata fields (Title / Author / Subject / Keywords /
Creator / Producer / CreationDate / ModificationDate / Trapped) plus
page count, encryption status, and version.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.tools import cli


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_pdf(
    path: Path,
    *,
    page_count: int = 1,
    title: str | None = None,
    author: str | None = None,
    subject: str | None = None,
    keywords: str | None = None,
    creator: str | None = None,
    producer: str | None = None,
    creation_date: _dt.datetime | None = None,
    modification_date: _dt.datetime | None = None,
    trapped: str | None = None,
    custom: dict[str, str] | None = None,
    xmp: bytes | None = None,
) -> Path:
    doc = PDDocument()
    try:
        for _ in range(page_count):
            doc.add_page(PDPage())
        info = doc.get_document_information()
        if title is not None:
            info.set_title(title)
        if author is not None:
            info.set_author(author)
        if subject is not None:
            info.set_subject(subject)
        if keywords is not None:
            info.set_keywords(keywords)
        if creator is not None:
            info.set_creator(creator)
        if producer is not None:
            info.set_producer(producer)
        if creation_date is not None:
            info.set_creation_date(creation_date)
        if modification_date is not None:
            info.set_modification_date(modification_date)
        if trapped is not None:
            info.set_trapped(trapped)
        if custom:
            for k, v in custom.items():
                info.set_custom_metadata_value(k, v)
        if xmp is not None:
            stream = COSStream()
            stream.set_data(xmp)
            doc.get_document_catalog().set_metadata(PDMetadata(stream))
        doc.save(path)
    finally:
        doc.close()
    return path


# ---------------------------------------------------------------------------
# basic tests (txt output, no flags)
# ---------------------------------------------------------------------------


def test_info_txt_basic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _make_pdf(tmp_path / "basic.pdf", page_count=2)
    rc = cli.run_cli(["info", str(pdf)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Pages: 2" in out
    assert "Encrypted: no" in out
    assert "PDF version" in out


def test_info_txt_prints_full_metadata(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _make_pdf(
        tmp_path / "meta.pdf",
        title="My Title",
        author="Anne Author",
        subject="A Subject",
        keywords="alpha beta",
        creator="Creator App",
        producer="Producer App",
        creation_date=_dt.datetime(2024, 1, 2, 3, 4, 5, tzinfo=_dt.timezone.utc),
        modification_date=_dt.datetime(2025, 1, 2, 3, 4, 5, tzinfo=_dt.timezone.utc),
        trapped="True",
    )
    rc = cli.run_cli(["info", str(pdf)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Title: My Title" in out
    assert "Author: Anne Author" in out
    assert "Subject: A Subject" in out
    assert "Keywords: alpha beta" in out
    assert "Creator: Creator App" in out
    assert "Producer: Producer App" in out
    assert "CreationDate" in out
    assert "ModDate" in out
    assert "Trapped: True" in out


def test_info_txt_custom_keys(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _make_pdf(
        tmp_path / "custom.pdf",
        custom={"CustomKey": "CustomValue"},
    )
    rc = cli.run_cli(["info", str(pdf)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "CustomKey: CustomValue" in out


# ---------------------------------------------------------------------------
# -output json
# ---------------------------------------------------------------------------


def test_info_json_emits_valid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _make_pdf(
        tmp_path / "j.pdf",
        page_count=3,
        title="JSON Title",
        author="JSON Author",
    )
    rc = cli.run_cli(["info", str(pdf), "-output", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["pages"] == 3
    assert payload["encrypted"] is False
    assert payload["info"]["Title"] == "JSON Title"
    assert payload["info"]["Author"] == "JSON Author"
    assert "header_version" in payload
    assert "effective_version" in payload


def test_info_json_includes_custom_keys(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _make_pdf(
        tmp_path / "j2.pdf",
        custom={"Reviewer": "Bob"},
    )
    cli.run_cli(["info", str(pdf), "-output", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["custom"]["Reviewer"] == "Bob"


def test_info_output_choice_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _make_pdf(tmp_path / "v.pdf")
    with pytest.raises(SystemExit):
        cli.run_cli(["info", str(pdf), "-output", "xml"])


# ---------------------------------------------------------------------------
# -metadata (XMP)
# ---------------------------------------------------------------------------


_XMP_BODY = (
    b"<?xpacket begin=\"\"?>"
    b"<x:xmpmeta xmlns:x=\"adobe:ns:meta/\">"
    b"<rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\">"
    b"<rdf:Description rdf:about=\"\""
    b" xmlns:dc=\"http://purl.org/dc/elements/1.1/\">"
    b"<dc:title>XMP TITLE</dc:title>"
    b"</rdf:Description>"
    b"</rdf:RDF></x:xmpmeta>"
    b"<?xpacket end=\"w\"?>"
)


def test_info_metadata_flag_dumps_xmp_txt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _make_pdf(tmp_path / "xmp.pdf", xmp=_XMP_BODY)
    rc = cli.run_cli(["info", str(pdf), "-metadata"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Metadata (XMP):" in out
    assert "XMP TITLE" in out


def test_info_metadata_flag_dumps_xmp_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _make_pdf(tmp_path / "xmp2.pdf", xmp=_XMP_BODY)
    rc = cli.run_cli(["info", str(pdf), "-metadata", "-output", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "xmp" in payload
    assert "XMP TITLE" in payload["xmp"]


def test_info_without_metadata_flag_omits_xmp(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _make_pdf(tmp_path / "nox.pdf", xmp=_XMP_BODY)
    cli.run_cli(["info", str(pdf), "-output", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert "xmp" not in payload


# ---------------------------------------------------------------------------
# -password
# ---------------------------------------------------------------------------


def test_info_password_flag_accepted_for_open_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = _make_pdf(tmp_path / "open.pdf")
    rc = cli.run_cli(["info", str(pdf), "-password", ""])
    assert rc == 0
    assert "Pages: 1" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# error path
# ---------------------------------------------------------------------------


def test_info_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "nope.pdf"
    rc = cli.run_cli(["info", str(target)])
    assert rc == 4
    assert "not a file" in capsys.readouterr().out
