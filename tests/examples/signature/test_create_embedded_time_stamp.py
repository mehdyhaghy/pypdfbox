"""Tests for ``CreateEmbeddedTimeStamp``."""

from __future__ import annotations

import binascii
import io

import pytest

import pypdfbox.examples.signature.create_embedded_time_stamp as ets_mod
from pypdfbox.examples.signature.create_embedded_time_stamp import (
    CreateEmbeddedTimeStamp,
)

# ---------------------------------------------------------------------------
# Construction / usage()
# ---------------------------------------------------------------------------


def test_construction():
    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")
    assert inst._tsa_url == "http://tsa.test.invalid"
    assert inst._document is None
    assert inst._signature is None
    assert inst._changed_encoded_signature is None


def test_usage_writes_to_stderr(capsys):
    CreateEmbeddedTimeStamp.usage()
    err = capsys.readouterr().err
    assert "CreateEmbeddedTimeStamp" in err
    assert "-tsa" in err


# ---------------------------------------------------------------------------
# main() — CLI dispatch
# ---------------------------------------------------------------------------


def test_main_wrong_arg_count_exits():
    with pytest.raises(SystemExit):
        CreateEmbeddedTimeStamp.main(["only.pdf"])


def test_main_missing_tsa_flag_exits():
    with pytest.raises(SystemExit):
        CreateEmbeddedTimeStamp.main(["a.pdf", "b.pdf", "c.pdf"])


def test_main_dispatches_to_embed(monkeypatch, tmp_path):
    pdf = tmp_path / "signed.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    captured = {}

    def fake_embed(self, in_file, out_file):
        captured["url"] = self._tsa_url
        captured["in"] = in_file
        captured["out"] = out_file

    monkeypatch.setattr(
        CreateEmbeddedTimeStamp, "embed_time_stamp", fake_embed, raising=True
    )
    CreateEmbeddedTimeStamp.main([str(pdf), "-tsa", "http://t"])
    assert captured["url"] == "http://t"
    assert captured["in"].name == "signed.pdf"
    assert captured["out"].name == "signed_eTs.pdf"


def test_main_tsa_first_position(monkeypatch, tmp_path):
    """The implementation locates ``-tsa`` via ``args.index``; positional
    order should not matter beyond the 3-arg total."""
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    captured = {}

    def fake_embed(self, in_file, out_file):
        captured["url"] = self._tsa_url

    monkeypatch.setattr(
        CreateEmbeddedTimeStamp, "embed_time_stamp", fake_embed, raising=True
    )
    CreateEmbeddedTimeStamp.main([str(pdf), "-tsa", "http://elsewhere"])
    assert captured["url"] == "http://elsewhere"


# ---------------------------------------------------------------------------
# _process_time_stamping_internal
# ---------------------------------------------------------------------------


def test_process_time_stamping_internal_no_op_when_unset():
    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")
    # Both document and signature are None → silently returns.
    assert inst._process_time_stamping_internal() is None


def test_process_time_stamping_internal_returns_when_set():
    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")
    inst._document = object()
    inst._signature = object()
    # Still a no-op — the hook is exposed for subclasses.
    assert inst._process_time_stamping_internal() is None


# ---------------------------------------------------------------------------
# embed_time_stamp — file dispatch
# ---------------------------------------------------------------------------


def test_missing_file_raises(tmp_path):
    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")
    with pytest.raises(FileNotFoundError):
        inst.embed_time_stamp(tmp_path / "does-not-exist.pdf")


def test_embed_time_stamp_with_no_out_file_uses_in_place(monkeypatch, tmp_path):
    src = tmp_path / "in.pdf"
    src.write_bytes(b"%PDF-1.4\n%%EOF\n")

    class FakeDoc:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    from pypdfbox.pdmodel import pd_document as _pd_doc_module

    monkeypatch.setattr(
        _pd_doc_module.PDDocument,
        "load",
        classmethod(lambda cls, _fh, password=None: FakeDoc()),
    )

    captured = {}

    def fake_process(self, in_path, out_path):
        captured["in"] = in_path
        captured["out"] = out_path

    monkeypatch.setattr(
        CreateEmbeddedTimeStamp, "process_time_stamping", fake_process, raising=True
    )

    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")
    inst.embed_time_stamp(src)
    # out_file None → in_place
    assert captured["in"] == captured["out"] == src


def test_embed_time_stamp_with_explicit_out_file(monkeypatch, tmp_path):
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    src.write_bytes(b"%PDF-1.4\n%%EOF\n")

    class FakeDoc:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    from pypdfbox.pdmodel import pd_document as _pd_doc_module

    monkeypatch.setattr(
        _pd_doc_module.PDDocument,
        "load",
        classmethod(lambda cls, _fh, password=None: FakeDoc()),
    )

    captured = {}

    def fake_process(self, in_path, out_path):
        captured["in"] = in_path
        captured["out"] = out_path

    monkeypatch.setattr(
        CreateEmbeddedTimeStamp, "process_time_stamping", fake_process, raising=True
    )

    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")
    inst.embed_time_stamp(src, dst)
    assert captured["in"] == src and captured["out"] == dst


# ---------------------------------------------------------------------------
# process_time_stamping — orchestrates the relevant-signatures pass
# ---------------------------------------------------------------------------


def test_process_time_stamping_raises_when_no_signature_found(monkeypatch, tmp_path):
    src = tmp_path / "in.pdf"
    src.write_bytes(b"%PDF-1.4\nbody\n%%EOF\n")
    dst = tmp_path / "out.pdf"

    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")

    # process_relevant_signatures sets _changed_encoded_signature; if it
    # leaves it None the function raises.
    def fake_relevant(self, doc_bytes):
        return None

    monkeypatch.setattr(
        CreateEmbeddedTimeStamp,
        "process_relevant_signatures",
        fake_relevant,
        raising=True,
    )
    with pytest.raises(RuntimeError, match="No signature"):
        inst.process_time_stamping(src, dst)


def test_process_time_stamping_writes_when_signature_present(monkeypatch, tmp_path):
    src = tmp_path / "in.pdf"
    src.write_bytes(b"DATABLOB")
    dst = tmp_path / "out.pdf"

    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")

    def fake_relevant(self, doc_bytes):
        self._changed_encoded_signature = b"DEADBEEF"

    def fake_embed(self, doc_bytes, output):
        output.write(b"EMBEDDED")

    monkeypatch.setattr(
        CreateEmbeddedTimeStamp,
        "process_relevant_signatures",
        fake_relevant,
        raising=True,
    )
    monkeypatch.setattr(
        CreateEmbeddedTimeStamp,
        "embed_new_signature_into_document",
        fake_embed,
        raising=True,
    )

    inst.process_time_stamping(src, dst)
    assert dst.read_bytes() == b"EMBEDDED"


# ---------------------------------------------------------------------------
# process_relevant_signatures
# ---------------------------------------------------------------------------


class _FakeSig:
    def __init__(self, contents=b"\x00" * 16, byte_range=None):
        self._contents = contents
        self._byte_range = byte_range or [0, 10, 28, 4]

    def get_contents_from_bytes(self, doc_bytes):  # noqa: D401
        return self._contents

    def get_byte_range(self):
        return list(self._byte_range)


def test_process_relevant_signatures_no_signature(monkeypatch):
    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")
    inst._document = object()
    monkeypatch.setattr(
        ets_mod.SigUtils,
        "get_last_relevant_signature",
        staticmethod(lambda d: None),
    )
    inst.process_relevant_signatures(b"BLOB")
    assert inst._signature is None
    assert inst._changed_encoded_signature is None


def test_process_relevant_signatures_without_tsa_passthrough(monkeypatch):
    inst = CreateEmbeddedTimeStamp("")  # falsy → no ValidationTimeStamp
    inst._document = object()

    fake = _FakeSig(contents=b"\xde\xad\xbe\xef", byte_range=[0, 5, 21, 10])
    monkeypatch.setattr(
        ets_mod.SigUtils,
        "get_last_relevant_signature",
        staticmethod(lambda d: fake),
    )

    inst.process_relevant_signatures(b"X" * 200)
    expected = binascii.hexlify(b"\xde\xad\xbe\xef").upper()
    assert inst._changed_encoded_signature == expected


def test_process_relevant_signatures_with_tsa_extends(monkeypatch):
    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")
    inst._document = object()
    fake = _FakeSig(contents=b"\xaa\xbb", byte_range=[0, 5, 21, 10])
    monkeypatch.setattr(
        ets_mod.SigUtils,
        "get_last_relevant_signature",
        staticmethod(lambda d: fake),
    )

    class FakeValidation:
        def __init__(self, url):
            self.url = url

        def add_signed_time_stamp(self, blob):
            return blob + b"-TST"

    monkeypatch.setattr(ets_mod, "ValidationTimeStamp", FakeValidation)

    inst.process_relevant_signatures(b"X" * 200)
    expected = binascii.hexlify(b"\xaa\xbb-TST").upper()
    assert inst._changed_encoded_signature == expected


def test_process_relevant_signatures_too_big_raises(monkeypatch):
    inst = CreateEmbeddedTimeStamp("")  # no TSA, just passthrough
    inst._document = object()
    # 32 raw bytes → 64 hex chars; max-place = byte_range[2] - byte_range[1].
    big_contents = b"\x01" * 32
    fake = _FakeSig(contents=big_contents, byte_range=[0, 5, 10, 50])  # max=5
    monkeypatch.setattr(
        ets_mod.SigUtils,
        "get_last_relevant_signature",
        staticmethod(lambda d: fake),
    )
    with pytest.raises(OSError, match="too big"):
        inst.process_relevant_signatures(b"X" * 200)


# ---------------------------------------------------------------------------
# embed_new_signature_into_document
# ---------------------------------------------------------------------------


def test_embed_new_signature_into_document_layout():
    """The output should be: prefix + new encoded sig + zero padding + suffix.

    Layout matches upstream ``embedNewSignatureIntoDocument`` (line 185):
    bytes 0..byte_range[1]+1 from input, then the new hex blob, then hex
    zeros padding the placeholder, then bytes byte_range[2]-1 onwards.
    """
    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")
    # byte_range = [start1, len1, start2, len2]
    # Place: contents placeholder spans bytes [len1 .. start2-1]
    byte_range = [0, 5, 15, 5]
    inst._signature = _FakeSig(byte_range=byte_range)
    inst._changed_encoded_signature = b"ABCD"  # 4 hex chars
    doc_bytes = b"HEAD<" + b"\x00" * 9 + b">TAIL"  # 20 bytes total

    out = io.BytesIO()
    inst.embed_new_signature_into_document(doc_bytes, out)
    written = out.getvalue()

    # Should at least start with the first 6 bytes (slice [0:6]).
    assert written[:6] == doc_bytes[0:6]
    # The 4-char hex blob is embedded after the prefix.
    assert b"ABCD" in written
    # And the tail (5 bytes from position 14 onwards) is appended.
    assert written.endswith(doc_bytes[14:14 + 5 + 1])


def test_embed_new_signature_into_document_pads_with_hex_zeros():
    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")
    byte_range = [0, 5, 25, 5]  # max placeholder = 25 - 5 = 20
    inst._signature = _FakeSig(byte_range=byte_range)
    inst._changed_encoded_signature = b"AA"  # 2 chars → adding_length = 16

    out = io.BytesIO()
    inst.embed_new_signature_into_document(b"P" * 50, out)
    written = out.getvalue()
    # 16 zero-bytes hex-encoded → 32 chars of "00".
    # Adding-length = 25-5-2-2 = 16 → ((16+1)//2)=8 raw bytes → "00" * 8.
    assert b"00" * 8 in written
