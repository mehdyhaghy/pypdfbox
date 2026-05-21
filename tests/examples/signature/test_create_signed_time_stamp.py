"""Tests for ``CreateSignedTimeStamp``."""

from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.cos.cos_name import COSName
from pypdfbox.examples.signature.create_signed_time_stamp import CreateSignedTimeStamp
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature


def test_sign_uses_validation_time_stamp(monkeypatch):
    signer = CreateSignedTimeStamp("http://tsa.test.invalid")

    captured = {}

    class FakeValidation:
        def __init__(self, url):
            captured["url"] = url

        def get_time_stamp_token(self, content):
            captured["payload"] = content.read()
            return b"FAKE-TOKEN"

    monkeypatch.setattr(
        "pypdfbox.examples.signature.create_signed_time_stamp.ValidationTimeStamp",
        FakeValidation,
    )
    result = signer.sign(BytesIO(b"to-stamp"))
    assert result == b"FAKE-TOKEN"
    assert captured["url"] == "http://tsa.test.invalid"
    assert captured["payload"] == b"to-stamp"


def test_implements_signature_interface_sign():
    signer = CreateSignedTimeStamp("http://tsa.test.invalid")
    assert callable(signer.sign)


# ---------------------------------------------------------------------------
# usage() / main()
# ---------------------------------------------------------------------------


def test_usage_writes_to_stderr(capsys):
    CreateSignedTimeStamp.usage()
    err = capsys.readouterr().err
    assert "CreateSignedTimeStamp" in err
    assert "-tsa" in err


def test_main_with_wrong_arg_count_calls_usage_and_exits(capsys):
    with pytest.raises(SystemExit):
        CreateSignedTimeStamp.main(["only-one-arg"])
    err = capsys.readouterr().err
    assert "CreateSignedTimeStamp" in err


def test_main_with_missing_tsa_flag_raises(capsys):
    with pytest.raises(SystemExit):
        CreateSignedTimeStamp.main(["a.pdf", "not-tsa", "http://x"])
    err = capsys.readouterr().err
    assert "CreateSignedTimeStamp" in err


def test_main_dispatches_to_sign_detached(monkeypatch, tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    captured = {}

    def fake_sign(self, in_file, out_file):
        captured["url"] = self._tsa_url
        captured["in"] = in_file
        captured["out"] = out_file

    monkeypatch.setattr(
        CreateSignedTimeStamp, "sign_detached", fake_sign, raising=True
    )
    CreateSignedTimeStamp.main([str(pdf), "-tsa", "http://tsa.test.invalid"])
    assert captured["url"] == "http://tsa.test.invalid"
    assert captured["in"].name == "doc.pdf"
    # Out file becomes "<stem>_timestamped.pdf" alongside the input.
    assert captured["out"].name == "doc_timestamped.pdf"


# ---------------------------------------------------------------------------
# sign_detached — file-I/O dispatch
# ---------------------------------------------------------------------------


def test_sign_detached_missing_file_raises(tmp_path):
    signer = CreateSignedTimeStamp("http://tsa.test.invalid")
    with pytest.raises(FileNotFoundError):
        signer.sign_detached(tmp_path / "nope.pdf")


def test_sign_detached_with_no_out_file_uses_in_place(monkeypatch, tmp_path):
    """When no ``out_file`` is provided, sign_detached writes back to
    the input path (mirrors upstream)."""
    src = tmp_path / "in.pdf"
    src.write_bytes(b"%PDF-1.4\n%%EOF\n")

    class FakeDoc:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    from pypdfbox.pdmodel import pd_document as pd_doc_mod

    captured: dict[str, object] = {}

    def fake_sign_doc(self, document, output):
        captured["doc"] = document
        captured["output_writable"] = hasattr(output, "write")
        output.write(b"signed-bytes-here")

    monkeypatch.setattr(
        pd_doc_mod.PDDocument, "load", staticmethod(lambda _fh: FakeDoc())
    )
    monkeypatch.setattr(
        CreateSignedTimeStamp, "sign_detached_document", fake_sign_doc, raising=True
    )

    signer = CreateSignedTimeStamp("http://tsa.test.invalid")
    signer.sign_detached(src)
    assert isinstance(captured["doc"], FakeDoc)
    assert captured["output_writable"] is True
    assert src.read_bytes() == b"signed-bytes-here"


def test_sign_detached_with_explicit_out_file_writes_there(monkeypatch, tmp_path):
    src = tmp_path / "in.pdf"
    out = tmp_path / "out.pdf"
    src.write_bytes(b"%PDF-1.4\n%%EOF\n")

    class FakeDoc:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    from pypdfbox.pdmodel import pd_document as pd_doc_mod

    def fake_sign_doc(self, document, output):
        output.write(b"OK")

    monkeypatch.setattr(
        pd_doc_mod.PDDocument, "load", staticmethod(lambda _fh: FakeDoc())
    )
    monkeypatch.setattr(
        CreateSignedTimeStamp, "sign_detached_document", fake_sign_doc, raising=True
    )

    signer = CreateSignedTimeStamp("http://tsa.test.invalid")
    signer.sign_detached(src, out)
    # Out file written, src untouched.
    assert out.read_bytes() == b"OK"
    assert src.read_bytes() == b"%PDF-1.4\n%%EOF\n"


def test_sign_detached_accepts_str_paths(monkeypatch, tmp_path):
    src = tmp_path / "in.pdf"
    src.write_bytes(b"%PDF-1.4\n%%EOF\n")

    class FakeDoc:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    from pypdfbox.pdmodel import pd_document as pd_doc_mod

    def fake_sign_doc(self, document, output):
        output.write(b"DONE")

    monkeypatch.setattr(
        pd_doc_mod.PDDocument, "load", staticmethod(lambda _fh: FakeDoc())
    )
    monkeypatch.setattr(
        CreateSignedTimeStamp, "sign_detached_document", fake_sign_doc, raising=True
    )

    signer = CreateSignedTimeStamp("http://tsa.test.invalid")
    out = tmp_path / "stamped.pdf"
    signer.sign_detached(str(src), str(out))
    assert out.read_bytes() == b"DONE"


# ---------------------------------------------------------------------------
# sign_detached_document — DocMDP gate + signature setup
# ---------------------------------------------------------------------------


def test_sign_detached_document_raises_when_docmdp_is_no_changes(monkeypatch):
    """A DocMDP transform-parameters dictionary of level 1 (== "no
    changes permitted") triggers an early RuntimeError."""
    from pypdfbox.examples.signature import create_signed_time_stamp as mod

    class FakeSigUtils:
        @staticmethod
        def get_mdp_permission(_doc):
            return 1

    monkeypatch.setattr(mod, "SigUtils", FakeSigUtils)

    signer = CreateSignedTimeStamp("http://tsa.test.invalid")
    with pytest.raises(RuntimeError, match="No changes to the document are permitted"):
        signer.sign_detached_document(object(), BytesIO())


def test_sign_detached_document_creates_pd_signature_and_calls_save_incremental(
    monkeypatch,
) -> None:
    """When the DocMDP gate clears, the helper builds a PDSignature
    (type=DocTimeStamp, filter=Adobe.PPKLite, sub_filter=ETSI.RFC3161)
    and threads it through ``add_signature`` / ``save_incremental``.

    LATENT BUG (flagged, not fixed): the source passes ``COSName``
    instances to ``PDSignature.set_type`` / ``set_sub_filter``, both of
    which expect ``str`` and route through ``COSDictionary.set_name``
    (which can't coerce a ``COSName`` value to bytes). The signature
    setup raises ``TypeError`` at runtime. We patch the two affected
    setters with str-tolerant shims so the rest of the function
    (add_signature + save_incremental) stays exercised under coverage.
    """
    from pypdfbox.examples.signature import create_signed_time_stamp as mod

    class FakeSigUtils:
        @staticmethod
        def get_mdp_permission(_doc):
            return 0

    monkeypatch.setattr(mod, "SigUtils", FakeSigUtils)

    # Tolerant shims that accept both str and COSName.
    captured_setters: dict[str, object] = {}

    def _accept_any_type(self, value):  # noqa: ANN001
        captured_setters["type"] = value

    def _accept_any_sub_filter(self, value):  # noqa: ANN001
        captured_setters["sub_filter"] = value

    monkeypatch.setattr(PDSignature, "set_type", _accept_any_type, raising=True)
    monkeypatch.setattr(
        PDSignature, "set_sub_filter", _accept_any_sub_filter, raising=True
    )

    captured: dict[str, object] = {}

    class FakeDocument:
        def add_signature(self, signature, signer):
            captured["signature"] = signature
            captured["signer"] = signer

        def save_incremental(self, output):
            captured["output"] = output
            output.write(b"saved")

    signer = CreateSignedTimeStamp("http://tsa.test.invalid")
    sink = BytesIO()
    signer.sign_detached_document(FakeDocument(), sink)

    sig = captured["signature"]
    assert isinstance(sig, PDSignature)
    # Wave 1338 fixed the source to pass plain strings to set_type /
    # set_sub_filter (was previously passing COSName instances, which
    # triggered TypeError inside COSDictionary.set_name).
    assert captured_setters["type"] == "DocTimeStamp"
    assert captured_setters["sub_filter"] == "ETSI.RFC3161"
    assert sig.get_filter() == PDSignature.FILTER_ADOBE_PPKLITE
    assert captured["signer"] is signer
    assert captured["output"] is sink
    assert sink.getvalue() == b"saved"


def test_pd_signature_set_type_rejects_cos_name():
    """Pinning the PDSignature contract: ``set_type`` accepts ``str`` only.
    Passing a ``COSName`` raises ``TypeError`` inside ``COSDictionary.set_name``.
    The create_signed_time_stamp example used to pass a ``COSName``; wave 1338
    fixed it to pass plain strings.
    """
    sig = PDSignature()
    with pytest.raises(TypeError):
        sig.set_type(COSName.DOC_TIME_STAMP)


# ---------------------------------------------------------------------------
# sign() — exception path
# ---------------------------------------------------------------------------


def test_sign_swallows_exception_and_returns_empty_bytes(monkeypatch, caplog):
    """When the underlying TSA fetch raises, ``sign`` mirrors upstream
    by logging the error and returning ``b""`` (the placeholder
    signature stays in place)."""
    import logging

    signer = CreateSignedTimeStamp("http://tsa.test.invalid")

    class BoomValidation:
        def __init__(self, url):
            self.url = url

        def get_time_stamp_token(self, content):
            raise RuntimeError("TSA unreachable")

    monkeypatch.setattr(
        "pypdfbox.examples.signature.create_signed_time_stamp.ValidationTimeStamp",
        BoomValidation,
    )
    with caplog.at_level(
        logging.ERROR, logger="pypdfbox.examples.signature.create_signed_time_stamp"
    ):
        result = signer.sign(BytesIO(b"payload"))
    assert result == b""
    assert "Hashing-Algorithm not found" in caplog.text
