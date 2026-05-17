"""Tests for ``CreateVisibleSignature``.

Covers the public surface (``main`` / ``usage`` / ``sign_pdf`` /
``_sign_document`` / ``find_existing_signature`` plus the designer
property getters/setters) end-to-end against an in-memory PDF so the
suite does not require network access or a real CA.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from pypdfbox.examples.signature.create_visible_signature import (
    CreateVisibleSignature,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
from pypdfbox.pdmodel.interactive.digitalsignature.signature_options import (
    SignatureOptions,
)


def _write_minimal_pdf(path: Path) -> None:
    """Build a single-page A4 PDF on disk for sign_pdf to consume."""
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(path)


# ---------------------------------------------------------------------------
# Constructor + base-class glue (kept from earlier waves)
# ---------------------------------------------------------------------------


def test_extends_create_signature_base(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    assert signer.get_certificate_chain()


def test_late_external_signing_flag(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    assert signer.is_late_external_signing() is False
    signer.set_late_external_signing(True)
    assert signer.is_late_external_signing() is True


def test_visible_signature_properties_captured(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    signer.set_visible_signature_properties(
        "Jane", "Earth", "Testing", preferred_size=0
    )
    assert signer._visible_signature_properties["name"] == "Jane"


def test_visible_sign_designer_captured(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    signer.set_visible_sign_designer(filename=None, x=10, y=20, zoom_percent=100)
    assert signer._visible_sign_designer["x"] == 10


def test_visible_sign_designer_records_image_stream(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    img = BytesIO(b"\x89PNG\r\n\x1a\nimg-bytes")
    signer.set_visible_sign_designer(
        filename="logo.png",
        x=5,
        y=10,
        zoom_percent=80,
        image_stream=img,
        page=2,
    )
    assert signer._visible_sign_designer == {
        "filename": "logo.png",
        "x": 5,
        "y": 10,
        "zoom": 80,
        "image_stream": img,
        "page": 2,
    }


def test_visible_signature_properties_full_kwargs(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    signer.set_visible_signature_properties(
        "Alice",
        "Mars",
        "Filing",
        preferred_size=8192,
        page=3,
        visual_signature_enabled=False,
    )
    assert signer._visible_signature_properties == {
        "name": "Alice",
        "location": "Mars",
        "reason": "Filing",
        "preferred_size": 8192,
        "page": 3,
        "visual_signature_enabled": False,
    }


def test_stream_cache_create_function_round_trip(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    assert signer.get_stream_cache_create_function() is None
    sentinel = lambda: BytesIO()  # noqa: E731
    signer.set_stream_cache_create_function(sentinel)
    assert signer.get_stream_cache_create_function() is sentinel
    signer.set_stream_cache_create_function(None)
    assert signer.get_stream_cache_create_function() is None


# ---------------------------------------------------------------------------
# usage / main
# ---------------------------------------------------------------------------


def test_usage_writes_to_stderr(capsys):
    CreateVisibleSignature.usage()
    err = capsys.readouterr().err
    assert "CreateVisibleSignature" in err


def test_main_too_few_args_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        CreateVisibleSignature.main([])
    assert "usage" in str(exc.value).lower()
    err = capsys.readouterr().err
    assert "CreateVisibleSignature" in err


def test_main_drives_sign_pipeline(
    tmp_path: Path, pkcs12_bytes, tsa_password, monkeypatch,
):
    keystore = tmp_path / "ks.p12"
    keystore.write_bytes(pkcs12_bytes)
    in_pdf = tmp_path / "in.pdf"
    _write_minimal_pdf(in_pdf)
    image = tmp_path / "logo.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    pin = (
        tsa_password.decode("utf-8")
        if isinstance(tsa_password, (bytes, bytearray))
        else tsa_password
    )

    # Stub ``_sign_document`` so the test verifies the dispatch wiring
    # (arg parsing / file open / image-stream open / property capture)
    # without running the full signing pipeline.
    seen: dict[str, object] = {}

    def _stub_sign(self, document, output, signature_field_name):  # noqa: ARG001
        seen["document"] = document
        seen["output"] = output
        seen["sign_designer"] = self._visible_sign_designer
        seen["sig_props"] = self._visible_signature_properties
        output.write(b"%PDF-1.4\n%%EOF\n")

    monkeypatch.setattr(CreateVisibleSignature, "_sign_document", _stub_sign)

    CreateVisibleSignature.main(
        [str(keystore), pin, str(in_pdf), str(image)],
    )

    signed = in_pdf.with_name(in_pdf.stem + "_signed.pdf")
    assert signed.exists()
    assert signed.read_bytes().startswith(b"%PDF-")
    # main captured both the designer block and the property block.
    assert seen["sign_designer"]["filename"] == str(image)
    assert seen["sign_designer"]["x"] == 0
    assert seen["sign_designer"]["zoom"] == 100
    assert seen["sig_props"]["name"] == "Example User"
    assert seen["sig_props"]["location"] == "Earth"


# ---------------------------------------------------------------------------
# sign_pdf
# ---------------------------------------------------------------------------


def test_sign_pdf_raises_for_missing_input(tmp_path, pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    with pytest.raises(FileNotFoundError, match="does not exist"):
        signer.sign_pdf(tmp_path / "missing.pdf", tmp_path / "out.pdf")


def test_sign_pdf_threads_tsa_url_into_signer(
    tmp_path, pkcs12_bytes, tsa_password, monkeypatch,
):
    in_pdf = tmp_path / "in.pdf"
    out_pdf = tmp_path / "out.pdf"
    _write_minimal_pdf(in_pdf)

    def _stub(self, doc, out, name):  # noqa: ARG001
        out.write(b"%PDF-1.4\n%%EOF\n")

    monkeypatch.setattr(CreateVisibleSignature, "_sign_document", _stub)

    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    signer.sign_pdf(
        in_pdf,
        out_pdf,
        tsa_url="http://tsa.invalid/",
        signature_field_name="Sig1",
    )
    assert out_pdf.exists()
    assert out_pdf.read_bytes().startswith(b"%PDF-")
    assert signer._tsa_url == "http://tsa.invalid/"


def test_sign_pdf_accepts_str_paths(
    tmp_path, pkcs12_bytes, tsa_password, monkeypatch,
):
    in_pdf = tmp_path / "in.pdf"
    out_pdf = tmp_path / "out.pdf"
    _write_minimal_pdf(in_pdf)

    def _stub(self, doc, out, name):  # noqa: ARG001
        out.write(b"%PDF-1.4\n%%EOF\n")

    monkeypatch.setattr(CreateVisibleSignature, "_sign_document", _stub)

    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    signer.sign_pdf(str(in_pdf), str(out_pdf))
    assert out_pdf.exists()


# ---------------------------------------------------------------------------
# _sign_document
# ---------------------------------------------------------------------------


def test_sign_document_blocks_when_docmdp_disallows(
    pkcs12_bytes, tsa_password, monkeypatch,
):
    from pypdfbox.examples.signature import sig_utils as _sig_utils

    monkeypatch.setattr(
        _sig_utils.SigUtils,
        "get_mdp_permission",
        staticmethod(lambda _doc: 1),
    )
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    with pytest.raises(RuntimeError, match="DocMDP"):
        signer._sign_document(object(), BytesIO(), None)


def test_sign_document_drives_signature_pipeline_defaults(
    pkcs12_bytes, tsa_password, monkeypatch,
):
    """Without explicit properties, ``_sign_document`` defaults the
    signature name/location/reason and sizes the placeholder at twice
    the default signature size.
    """
    from pypdfbox.examples.signature import sig_utils as _sig_utils

    monkeypatch.setattr(
        _sig_utils.SigUtils,
        "get_mdp_permission",
        staticmethod(lambda _doc: 0),
    )

    captured: dict[str, object] = {}

    class _StubDoc:
        def add_signature(self, sig, iface, options):
            captured["sig"] = sig
            captured["iface"] = iface
            captured["options"] = options

        def save_incremental(self, out):
            out.write(b"%PDF-1.4\nsaved\n")

    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    buf = BytesIO()
    signer._sign_document(_StubDoc(), buf, None)

    sig = captured["sig"]
    assert isinstance(sig, PDSignature)
    assert sig.get_filter() == PDSignature.FILTER_ADOBE_PPKLITE
    assert sig.get_sub_filter() == PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED
    assert sig.get_name() == "Example User"
    assert sig.get_location() == ""
    assert sig.get_reason() == "Testing"
    assert isinstance(captured["options"], SignatureOptions)
    assert captured["iface"] is signer
    assert buf.getvalue().startswith(b"%PDF-")


def test_sign_document_uses_explicit_properties(
    pkcs12_bytes, tsa_password, monkeypatch,
):
    from pypdfbox.examples.signature import sig_utils as _sig_utils

    monkeypatch.setattr(
        _sig_utils.SigUtils,
        "get_mdp_permission",
        staticmethod(lambda _doc: 0),
    )

    captured: dict[str, object] = {}

    class _StubDoc:
        def add_signature(self, sig, iface, options):  # noqa: ARG002
            captured["sig"] = sig

        def save_incremental(self, out):  # noqa: ARG002
            return None

    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    signer.set_visible_signature_properties(
        "Jane Doe", "Mars", "Filed", preferred_size=4096,
    )
    signer._sign_document(_StubDoc(), BytesIO(), None)

    sig = captured["sig"]
    assert sig.get_name() == "Jane Doe"
    assert sig.get_location() == "Mars"
    assert sig.get_reason() == "Filed"


def test_sign_document_embeds_visual_signature_when_image_stream_present(
    pkcs12_bytes, tsa_password, monkeypatch,
):
    """When a designer with an ``image_stream`` is set, the bytes are
    read once and threaded into ``SignatureOptions.set_visual_signature``.
    """
    from pypdfbox.examples.signature import sig_utils as _sig_utils

    monkeypatch.setattr(
        _sig_utils.SigUtils,
        "get_mdp_permission",
        staticmethod(lambda _doc: 0),
    )

    captured: dict[str, object] = {}

    class _StubDoc:
        def add_signature(self, sig, iface, options):  # noqa: ARG002
            captured["options"] = options

        def save_incremental(self, out):  # noqa: ARG002
            return None

    payload = b"\x89PNG\r\n\x1a\nvisual-bytes"
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    signer.set_visible_sign_designer(
        filename="logo.png",
        x=0,
        y=0,
        zoom_percent=100,
        image_stream=BytesIO(payload),
    )

    spy_visual: dict[str, object] = {}
    real_set_visual = SignatureOptions.set_visual_signature

    def _spy(self, stream):
        spy_visual["bytes"] = stream.read() if hasattr(stream, "read") else stream
        # Don't actually wire the placeholder into the dict — the stub
        # document never validates it.

    monkeypatch.setattr(SignatureOptions, "set_visual_signature", _spy)
    try:
        signer._sign_document(_StubDoc(), BytesIO(), None)
    finally:
        monkeypatch.setattr(SignatureOptions, "set_visual_signature", real_set_visual)

    assert spy_visual["bytes"] == payload


def test_sign_document_skips_visual_signature_when_no_image_stream(
    pkcs12_bytes, tsa_password, monkeypatch,
):
    from pypdfbox.examples.signature import sig_utils as _sig_utils

    monkeypatch.setattr(
        _sig_utils.SigUtils,
        "get_mdp_permission",
        staticmethod(lambda _doc: 0),
    )

    class _StubDoc:
        def add_signature(self, sig, iface, options):  # noqa: ARG002
            return None

        def save_incremental(self, out):  # noqa: ARG002
            return None

    called = {"count": 0}

    def _spy(self, stream):  # noqa: ARG001
        called["count"] += 1

    monkeypatch.setattr(SignatureOptions, "set_visual_signature", _spy)
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    # Designer with NO image_stream — visual signature should be skipped.
    signer.set_visible_sign_designer(filename=None, x=0, y=0, zoom_percent=100)
    signer._sign_document(_StubDoc(), BytesIO(), None)
    assert called["count"] == 0


# ---------------------------------------------------------------------------
# find_existing_signature
# ---------------------------------------------------------------------------


def _build_stub_doc(fields):
    """Return a doc-like object with ``get_document_catalog().get_acro_form()
    .get_fields() == fields``."""

    class _AcroForm:
        def get_fields(self_inner):
            return fields

    class _Catalog:
        def get_acro_form(self_inner):
            return _AcroForm()

    class _Doc:
        def get_document_catalog(self_inner):
            return _Catalog()

    return _Doc()


def test_find_existing_signature_returns_none_when_no_fields(
    pkcs12_bytes, tsa_password,
):
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    doc = _build_stub_doc([])
    assert signer.find_existing_signature(doc, "Sig1") is None


def test_find_existing_signature_returns_matching_field(
    pkcs12_bytes, tsa_password,
):
    class _Field:
        def __init__(self, name):
            self._n = name

        def get_partial_name(self):
            return self._n

    target = _Field("Sig1")
    doc = _build_stub_doc([_Field("Other"), target, _Field("Sig2")])
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    assert signer.find_existing_signature(doc, "Sig1") is target


def test_find_existing_signature_returns_none_when_name_mismatch(
    pkcs12_bytes, tsa_password,
):
    class _Field:
        def get_partial_name(self):
            return "Other"

    doc = _build_stub_doc([_Field()])
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    assert signer.find_existing_signature(doc, "Sig1") is None


def test_find_existing_signature_handles_field_without_partial_name(
    pkcs12_bytes, tsa_password,
):
    """Fields lacking ``get_partial_name`` resolve to ``None`` via the
    inline ``getattr`` fallback and are simply skipped.
    """

    class _Field:
        pass  # no get_partial_name

    doc = _build_stub_doc([_Field()])
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    assert signer.find_existing_signature(doc, "Sig1") is None
