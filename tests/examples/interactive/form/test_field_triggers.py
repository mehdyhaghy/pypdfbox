"""Tests for :class:`FieldTriggers`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pypdfbox.cos import COSName
from pypdfbox.examples.interactive.form.create_simple_form import CreateSimpleForm
from pypdfbox.examples.interactive.form.field_triggers import FieldTriggers
from pypdfbox.pdmodel.pd_document import PDDocument

_AA = COSName.get_pdf_name("AA")
_TRIGGER_KEYS = ("E", "X", "D", "U", "Fo", "Bl")


def _make_simple_form(tmp_path: Path) -> Path:
    src = tmp_path / "form.pdf"
    CreateSimpleForm.create(str(src))
    return src


def test_attach_triggers_runs(tmp_path: Path) -> None:
    src = _make_simple_form(tmp_path)
    dst = tmp_path / "triggers.pdf"
    FieldTriggers.attach_triggers(str(src), str(dst), "SampleField")
    assert dst.exists()
    assert dst.stat().st_size > 0


def test_attach_triggers_writes_all_six_handlers(tmp_path: Path) -> None:
    src = _make_simple_form(tmp_path)
    dst = tmp_path / "triggers.pdf"
    FieldTriggers.attach_triggers(str(src), str(dst), "SampleField")
    with PDDocument.load(str(dst)) as doc:
        widget = (
            doc.get_document_catalog()
            .get_acro_form()
            .get_field("SampleField")
            .get_widgets()[0]
        )
        cos = widget.get_cos_object()
        aa = cos.get_dictionary_object(_AA)
        assert aa is not None
        for key in _TRIGGER_KEYS:
            assert aa.get_dictionary_object(COSName.get_pdf_name(key)) is not None


def test_attach_triggers_rejects_missing_field(tmp_path: Path) -> None:
    src = _make_simple_form(tmp_path)
    dst = tmp_path / "triggers.pdf"
    with pytest.raises(OSError, match="not found"):
        FieldTriggers.attach_triggers(str(src), str(dst), "MissingField")


def test_attach_triggers_rejects_doc_without_acroform(tmp_path: Path) -> None:
    from pypdfbox.pdmodel.pd_page import PDPage

    src = tmp_path / "blank.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(str(src))
    finally:
        doc.close()
    dst = tmp_path / "triggers.pdf"
    with pytest.raises(OSError, match="AcroForm"):
        FieldTriggers.attach_triggers(str(src), str(dst), "Whatever")


def test_main_with_two_args_dispatches(tmp_path: Path) -> None:
    src = _make_simple_form(tmp_path)
    dst = tmp_path / "triggers.pdf"
    FieldTriggers.main([str(src), str(dst)])
    assert dst.exists()


def test_main_with_one_arg_uses_default_output(tmp_path: Path) -> None:
    src = _make_simple_form(tmp_path)
    # Default output is "target/FieldTriggers.pdf"; redirect cwd so we
    # don't pollute the repo root.
    cwd = tmp_path / "work"
    (cwd / "target").mkdir(parents=True)
    old = Path.cwd()
    import os

    os.chdir(cwd)
    try:
        FieldTriggers.main([str(src)])
        assert (cwd / "target" / "FieldTriggers.pdf").exists()
    finally:
        os.chdir(old)


def test_main_with_no_args_uses_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """argv None -> argv=[] -> defaults src=target/SimpleForm.pdf
    and dst=target/FieldTriggers.pdf. Verify it dispatches by writing
    a known source to the default location."""
    cwd = tmp_path
    (cwd / "target").mkdir()
    monkeypatch.chdir(cwd)
    CreateSimpleForm.create("target/SimpleForm.pdf")
    FieldTriggers.main(None)
    assert (cwd / "target" / "FieldTriggers.pdf").exists()


def test_field_triggers_constructor() -> None:
    # No-op constructor for API parity.
    assert FieldTriggers() is not None


def test_default_paths_exposed() -> None:
    assert FieldTriggers.DEFAULT_INPUT.endswith("SimpleForm.pdf")
    assert FieldTriggers.DEFAULT_OUTPUT.endswith("FieldTriggers.pdf")


def test_module_entry_point_guard() -> None:
    """Just ensure ``__main__`` reference resolves; no pragma needed."""
    mod = sys.modules["pypdfbox.examples.interactive.form.field_triggers"]
    assert hasattr(mod, "FieldTriggers")


def test_attach_triggers_handles_missing_action_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Force both action-module imports to fail and verify the example
    still completes (skips trigger attachment, saves the doc unchanged).
    Covers the ImportError fallback branches."""
    import builtins

    real_import = builtins.__import__
    blocked = (
        "pypdfbox.pdmodel.interactive.action.pd_action_java_script",
        "pypdfbox.pdmodel.interactive.action.pd_annotation_additional_actions",
    )

    def _maybe_block(name: str, *args: object, **kwargs: object) -> object:
        if name in blocked:
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _maybe_block)

    src = _make_simple_form(tmp_path)
    dst = tmp_path / "triggers.pdf"
    FieldTriggers.attach_triggers(str(src), str(dst), "SampleField")
    assert dst.exists()
    # No /AA dictionary should be written when both action modules are
    # unavailable.
    with PDDocument.load(str(dst)) as doc:
        widget = (
            doc.get_document_catalog()
            .get_acro_form()
            .get_field("SampleField")
            .get_widgets()[0]
        )
        assert widget.get_cos_object().get_dictionary_object(_AA) is None
