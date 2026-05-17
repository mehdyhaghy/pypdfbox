"""Tests for ``CreateEmptySignatureForm``.

Wave 1342 fixed three latent bugs that previously blocked end-to-end
coverage of ``create()`` — the ``pd_rectangle`` import path, the
``PDType1Font`` enum-as-dict misuse, and the missing ``COSName.HELV``
predefine.

Wave 1344 fixed the snapshot-list-append bug: the example now calls
``acro_form.set_fields([signature_field])`` and
``page.add_annotation(widget)`` (a new helper) instead of mutating
fresh snapshot lists returned by the getters. The round-trip
assertions below verify that fix.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.signature.create_empty_signature_form import (
    CreateEmptySignatureForm,
)

# ---------- static-helper surface --------------------------------------


def test_static_helper_cannot_be_instantiated():
    # ``__init__`` is annotated ``pragma: no cover``; if the wrapper is
    # ever inadvertently made instantiable, this test still catches it.
    with pytest.raises(RuntimeError):
        CreateEmptySignatureForm()


def test_create_method_is_callable():
    assert callable(CreateEmptySignatureForm.create)


def test_main_method_is_callable():
    assert callable(CreateEmptySignatureForm.main)


# ---------- main() dispatcher ------------------------------------------


def test_main_without_args_raises_usage() -> None:
    """Empty argv triggers the ``raise SystemExit("usage: ...")`` guard
    (line 18 of the source). Covers the ``not args`` branch."""
    with pytest.raises(SystemExit) as exc_info:
        CreateEmptySignatureForm.main([])
    # ``SystemExit("usage ...")`` -> .code holds the message string.
    assert "usage" in str(exc_info.value)


def test_main_dispatches_to_create(tmp_path: Path, monkeypatch) -> None:
    """``main([path])`` should forward ``path`` straight to ``create``.

    Stubs ``create`` to capture the argument so this test exercises
    the dispatch line in isolation, independent of the real PDF write.
    """
    received: list[str] = []

    def _stub(output_path):
        received.append(str(output_path))

    monkeypatch.setattr(CreateEmptySignatureForm, "create", staticmethod(_stub))
    out = tmp_path / "sig.pdf"
    CreateEmptySignatureForm.main([str(out)])
    assert received == [str(out)]


def test_main_passes_first_positional_arg(monkeypatch) -> None:
    """``main`` ignores any args beyond the first positional output path."""
    received: list[str] = []

    def _stub(output_path):
        received.append(str(output_path))

    monkeypatch.setattr(CreateEmptySignatureForm, "create", staticmethod(_stub))
    CreateEmptySignatureForm.main(["primary.pdf", "ignored", "also-ignored"])
    assert received == ["primary.pdf"]


def test_main_with_path_drives_create_end_to_end(tmp_path: Path) -> None:
    """``main([path])`` round-trip: file ends up on disk, no stub."""
    out = tmp_path / "via_main.pdf"
    CreateEmptySignatureForm.main([str(out)])
    assert out.exists()
    assert out.stat().st_size > 0
    assert out.read_bytes().startswith(b"%PDF-")


# ---------- create() end-to-end ---------------------------------------


def test_create_writes_pdf_file(tmp_path: Path) -> None:
    """Smoke test: ``create()`` produces a non-empty PDF on disk."""
    out = tmp_path / "empty_sig.pdf"
    CreateEmptySignatureForm.create(out)
    assert out.exists()
    size = out.stat().st_size
    assert size > 0
    blob = out.read_bytes()
    assert blob.startswith(b"%PDF-")
    # Every PDF must terminate with %%EOF (possibly + trailing newline).
    assert b"%%EOF" in blob[-32:]


def test_create_accepts_str_path(tmp_path: Path) -> None:
    """``create()`` annotation is ``Path | str``; both must work."""
    out = tmp_path / "as_str.pdf"
    CreateEmptySignatureForm.create(str(out))
    assert out.exists() and out.stat().st_size > 0


def test_created_pdf_has_acroform_with_signature_field(tmp_path: Path) -> None:
    """Re-load the saved PDF and verify the AcroForm carries exactly one
    signature field, and the first page carries exactly one widget
    annotation.

    Wave 1344 fixed the snapshot-list-append bug; this assertion would
    fail (empty ``/Fields``/``/Annots`` arrays) prior to that fix.
    """
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument

    out = tmp_path / "round_trip.pdf"
    CreateEmptySignatureForm.create(out)

    with PDDocument.load(str(out)) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        assert acro_form is not None
        fields = acro_form.get_fields()
        assert len(fields) == 1
        assert isinstance(fields[0], PDSignatureField)
        page = doc.get_pages()[0]
        annots = page.get_annotations()
        assert len(annots) == 1


def test_created_pdf_has_helv_default_resource(tmp_path: Path) -> None:
    """The AcroForm's default resources must expose the /Helv font."""
    from pypdfbox.cos.cos_name import COSName
    from pypdfbox.pdmodel.pd_document import PDDocument

    out = tmp_path / "with_helv.pdf"
    CreateEmptySignatureForm.create(out)

    with PDDocument.load(str(out)) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        resources = acro_form.get_default_resources()
        assert resources is not None
        # Resource lookup is via COSName; /Helv must resolve to a font.
        font = resources.get_font(COSName.HELV)
        assert font is not None


def test_created_pdf_has_default_appearance_string(tmp_path: Path) -> None:
    """AcroForm /DA must round-trip the exact appearance string."""
    from pypdfbox.pdmodel.pd_document import PDDocument

    out = tmp_path / "with_da.pdf"
    CreateEmptySignatureForm.create(out)

    with PDDocument.load(str(out)) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        assert acro_form.get_default_appearance() == "/Helv 0 Tf 0 g"


def test_created_pdf_page_size_is_a4(tmp_path: Path) -> None:
    """The single page must be A4 (~595 x 842 PDF points)."""
    from pypdfbox.pdmodel.pd_document import PDDocument

    out = tmp_path / "a4.pdf"
    CreateEmptySignatureForm.create(out)

    with PDDocument.load(str(out)) as doc:
        assert doc.get_number_of_pages() == 1
        page = doc.get_page(0)
        media_box = page.get_media_box()
        # A4 = 595.276 x 841.890 PDF points; allow a 1-pt rounding slack.
        assert media_box.get_width() == pytest.approx(595.276, abs=1)
        assert media_box.get_height() == pytest.approx(841.890, abs=1)
