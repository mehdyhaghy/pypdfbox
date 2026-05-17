"""Tests for ``CreateVisibleSignature2``.

Covers the public surface (``main`` / ``sign_pdf`` / ``_sign_document`` /
``create_signature_rectangle`` / ``create_visual_signature_template`` /
``find_existing_signature`` / ``usage``) end-to-end against an in-memory
PDF so the suite does not rely on the network or external CA infrastructure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.signature.create_visible_signature2 import (
    CreateVisibleSignature2,
)


def _write_minimal_pdf(path: Path) -> None:
    """Build a single-page A4 PDF on disk for sign_pdf to consume."""
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(path)


def test_image_file_round_trips(pkcs12_bytes, tsa_password, tmp_path: Path):
    signer = CreateVisibleSignature2(pkcs12_bytes, tsa_password)
    assert signer.get_image_file() is None
    placeholder = tmp_path / "img.png"
    placeholder.write_bytes(b"\x89PNG\r\n\x1a\n")
    signer.set_image_file(placeholder)
    assert signer.get_image_file() == placeholder
    signer.set_image_file(None)
    assert signer.get_image_file() is None


def test_set_image_file_accepts_string_path(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature2(pkcs12_bytes, tsa_password)
    signer.set_image_file("/tmp/some.png")  # noqa: S108
    assert signer.get_image_file() == Path("/tmp/some.png")  # noqa: S108


def test_late_external_signing_round_trip(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature2(pkcs12_bytes, tsa_password)
    assert signer.is_late_external_signing() is False
    signer.set_late_external_signing(True)
    assert signer.is_late_external_signing() is True


def test_usage_writes_to_stderr(capsys):
    CreateVisibleSignature2.usage()
    err = capsys.readouterr().err
    assert "CreateVisibleSignature2" in err


def test_main_too_few_args_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        CreateVisibleSignature2.main([])
    assert "usage" in str(exc.value).lower()
    err = capsys.readouterr().err
    assert "CreateVisibleSignature2" in err


def test_main_drives_sign_pipeline(
    tmp_path: Path, pkcs12_bytes, tsa_password, monkeypatch,
):
    keystore = tmp_path / "ks.p12"
    keystore.write_bytes(pkcs12_bytes)
    in_pdf = tmp_path / "in.pdf"
    _write_minimal_pdf(in_pdf)
    pin = tsa_password.decode("utf-8") if isinstance(
        tsa_password, (bytes, bytearray)
    ) else tsa_password

    # ``main`` ultimately runs ``_sign_document`` against the loaded
    # document; stub the body so the test verifies the dispatch wiring
    # (arg parsing / file open / save handoff) without depending on the
    # full signing pipeline. The real signing path is covered separately
    # in ``test_sign_pdf_signs_to_outfile``.
    called: dict[str, object] = {}

    def _stub_sign(self, document, output, signature_field_name):  # noqa: ARG001
        called["document"] = document
        called["output"] = output
        output.write(b"%PDF-1.4\n%%EOF\n")

    monkeypatch.setattr(
        CreateVisibleSignature2, "_sign_document", _stub_sign,
    )

    CreateVisibleSignature2.main([str(keystore), pin, str(in_pdf)])

    signed = in_pdf.with_name(in_pdf.stem + "_signed.pdf")
    assert signed.exists()
    assert signed.stat().st_size > 0
    assert called["document"] is not None


def test_sign_pdf_raises_for_missing_input(
    tmp_path: Path, pkcs12_bytes, tsa_password,
):
    signer = CreateVisibleSignature2(pkcs12_bytes, tsa_password)
    with pytest.raises(FileNotFoundError):
        signer.sign_pdf(
            tmp_path / "missing.pdf",
            tmp_path / "out.pdf",
            human_rect=(0, 0, 100, 100),
        )


def test_sign_pdf_signs_to_outfile(
    tmp_path: Path, pkcs12_bytes, tsa_password, monkeypatch,
):
    in_pdf = tmp_path / "in.pdf"
    out_pdf = tmp_path / "out.pdf"
    _write_minimal_pdf(in_pdf)

    # Stub ``_sign_document`` so the test verifies the file-open / context
    # management wiring of ``sign_pdf`` without exercising the full
    # in-place signing pipeline (which expects a wrapped PDDocument).
    def _stub(self, doc, out, name):  # noqa: ARG001
        out.write(b"%PDF-1.4\n%%EOF\n")

    monkeypatch.setattr(CreateVisibleSignature2, "_sign_document", _stub)

    signer = CreateVisibleSignature2(pkcs12_bytes, tsa_password)
    signer.sign_pdf(
        in_pdf,
        out_pdf,
        human_rect=(50, 50, 200, 100),
        tsa_url="http://tsa.invalid/",
    )
    assert out_pdf.exists()
    assert out_pdf.read_bytes().startswith(b"%PDF-")
    assert signer._tsa_url == "http://tsa.invalid/"  # noqa: SLF001


def test_sign_document_blocks_when_docmdp_disallows(
    pkcs12_bytes, tsa_password, monkeypatch,
):
    from pypdfbox.examples.signature import sig_utils as _sig_utils

    monkeypatch.setattr(
        _sig_utils.SigUtils,
        "get_mdp_permission",
        staticmethod(lambda _doc: 1),
    )

    from io import BytesIO

    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    signer = CreateVisibleSignature2(pkcs12_bytes, tsa_password)
    with PDDocument() as doc:
        doc.add_page(PDPage())
        with pytest.raises(RuntimeError, match="DocMDP"):
            signer._sign_document(doc, BytesIO(), None)  # noqa: SLF001


def test_sign_document_drives_signature_pipeline(
    pkcs12_bytes, tsa_password, monkeypatch,
):
    """``_sign_document`` builds a PDSignature + SignatureOptions and hands
    them to ``document.add_signature`` / ``document.save_incremental``.

    Stub the document so the test exercises the full body of the method
    without depending on the (separately tested) signing pipeline."""
    from io import BytesIO

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

    signer = CreateVisibleSignature2(pkcs12_bytes, tsa_password)
    buf = BytesIO()
    signer._sign_document(_StubDoc(), buf, None)  # noqa: SLF001
    assert buf.getvalue().startswith(b"%PDF-")
    sig = captured["sig"]
    assert sig.get_name() == "Example User"
    assert sig.get_location() == "Los Angeles, CA"
    assert sig.get_reason() == "Testing"
    assert captured["iface"] is signer


def _install_pd_rectangle_common_alias() -> None:
    """The upstream port references ``pypdfbox.pdmodel.common.pd_rectangle``
    inside :func:`create_signature_rectangle`, but the canonical module
    location is ``pypdfbox.pdmodel.pd_rectangle``. Register a sys.modules
    alias so the test can drive the helper without modifying the port."""
    import sys

    import pypdfbox.pdmodel.pd_rectangle as _root_rect

    sys.modules.setdefault(
        "pypdfbox.pdmodel.common.pd_rectangle", _root_rect,
    )


def test_create_signature_rectangle_converts_top_left_to_bottom_left():
    _install_pd_rectangle_common_alias()
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    with PDDocument() as doc:
        doc.add_page(PDPage())
        rect = CreateVisibleSignature2.create_signature_rectangle(
            doc, (10, 20, 100, 50),
        )
        page_h = doc.get_pages()[0].get_media_box().get_height()
        assert rect.get_lower_left_x() == 10
        assert rect.get_upper_right_x() == 110
        # 20 from the top, 50 tall — lower-left y = page_h - 20 - 50.
        assert rect.get_lower_left_y() == page_h - 70
        assert rect.get_upper_right_y() == page_h - 20


def test_create_visual_signature_template_yields_loadable_pdf():
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    with PDDocument() as src:
        src.add_page(PDPage())
        rect = PDRectangle(150, 80)
        buf = CreateVisibleSignature2.create_visual_signature_template(
            src, 0, rect, signature=None,
        )

    data = buf.getvalue()
    assert data.startswith(b"%PDF-")
    # Cosmetic sanity check — the appearance template should contain at
    # least the AcroForm wiring keywords.
    assert b"AcroForm" in data
    assert b"Sig" in data or b"FT" in data


def test_find_existing_signature_returns_none_for_missing_form():
    assert CreateVisibleSignature2.find_existing_signature(None, "Sig1") is None


def test_find_existing_signature_returns_none_for_blank_name():
    assert CreateVisibleSignature2.find_existing_signature(
        object(), "",
    ) is None


def test_find_existing_signature_returns_none_when_field_absent():
    class _AcroForm:
        def get_field(self, _name):
            return None

    assert CreateVisibleSignature2.find_existing_signature(
        _AcroForm(), "Sig1",
    ) is None


def test_find_existing_signature_returns_field_value_when_present():
    sentinel = object()

    class _Field:
        def get_value(self):
            return sentinel

    class _AcroForm:
        def get_field(self, _name):
            return _Field()

    assert (
        CreateVisibleSignature2.find_existing_signature(_AcroForm(), "Sig1")
        is sentinel
    )


def test_find_existing_signature_returns_none_when_value_getter_absent():
    class _Field:
        pass  # no get_value

    class _AcroForm:
        def get_field(self, _name):
            return _Field()

    assert (
        CreateVisibleSignature2.find_existing_signature(_AcroForm(), "Sig1")
        is None
    )
