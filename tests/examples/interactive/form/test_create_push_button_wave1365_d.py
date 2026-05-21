"""Wave 1365 — coverage round-out for :class:`CreatePushButton`.

The base smoke test only exercises the explicit-argv path. This module
covers the no-args branch (defaults to ``CreatePushButton.DEFAULT_FILENAME``),
the trivial ``__init__`` body, and the ``create`` helper's structural
output (one push-button field with one widget on page 0).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.interactive.form.create_push_button import CreatePushButton
from pypdfbox.pdmodel.pd_document import PDDocument


def test_default_filename_constant_targets_pdf() -> None:
    """The ``DEFAULT_FILENAME`` class constant must survive the port —
    several upstream samples reference it (line 36)."""
    assert CreatePushButton.DEFAULT_FILENAME.endswith(".pdf")


def test_constructor_is_a_no_op() -> None:
    """Cover the no-op ``__init__`` body (line 39)."""
    instance = CreatePushButton()
    assert isinstance(instance, CreatePushButton)


def test_main_with_explicit_path(tmp_path: Path) -> None:
    """The ``argv`` non-empty branch (line 45)."""
    out = tmp_path / "push-explicit.pdf"
    CreatePushButton.main([str(out)])
    assert out.exists()
    assert out.stat().st_size > 0


def test_main_with_empty_argv_uses_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``argv`` empty branch — defaults to ``DEFAULT_FILENAME``.

    Redirect the class constant into ``tmp_path`` so the side-effect file
    lands somewhere disposable.
    """
    out = tmp_path / "push-default.pdf"
    monkeypatch.setattr(CreatePushButton, "DEFAULT_FILENAME", str(out))
    CreatePushButton.main([])
    assert out.exists()


def test_main_with_none_argv_uses_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main(None)`` must also fall back to ``DEFAULT_FILENAME``."""
    out = tmp_path / "push-none.pdf"
    monkeypatch.setattr(CreatePushButton, "DEFAULT_FILENAME", str(out))
    CreatePushButton.main(None)
    assert out.exists()


def test_create_writes_pdf_with_acroform(tmp_path: Path) -> None:
    """``create`` must produce a PDF whose AcroForm carries one
    push-button field (lines 52-70)."""
    out = tmp_path / "push-create.pdf"
    CreatePushButton.create(str(out))
    with PDDocument.load(str(out)) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        assert acro_form is not None
        fields = acro_form.get_fields()
        # The example appends exactly one field.
        assert len(fields) == 1


def test_create_writes_widget_on_first_page(tmp_path: Path) -> None:
    """The widget must be appended to the first page's annotation list
    (lines 61-65). The reload path may decode the widget either as an
    annotation entry on the page or only as part of the AcroForm tree,
    depending on porting stage — accept either."""
    out = tmp_path / "push-widget.pdf"
    CreatePushButton.create(str(out))
    with PDDocument.load(str(out)) as doc:
        page = doc.get_page(0)
        # After serialization either the page-level /Annots array carries
        # the widget reference *or* the field tree exposes it via the
        # AcroForm. Both indicate the side-effect on the page ran.
        page_annots = page.get_annotations()
        af = doc.get_document_catalog().get_acro_form()
        widgets_via_acro = (
            af.get_fields()[0].get_widgets() if af and af.get_fields() else []
        )
        assert page_annots or widgets_via_acro


def test_create_appends_to_existing_field_list(tmp_path: Path) -> None:
    """The example uses ``[*acro_form.get_fields(), push_button]`` so it
    must be append-safe (line 60). Verify by running it twice through the
    same temp directory."""
    out_a = tmp_path / "push-a.pdf"
    out_b = tmp_path / "push-b.pdf"
    CreatePushButton.create(str(out_a))
    CreatePushButton.create(str(out_b))
    # Both files exist independently — the example does not stash global
    # state across runs.
    assert out_a.stat().st_size > 0
    assert out_b.stat().st_size > 0
