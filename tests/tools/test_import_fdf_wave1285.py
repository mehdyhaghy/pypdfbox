"""Tests for ``ImportFDF`` workaround documentation (Wave 1285).

The bare-``TODO`` was replaced with a comment that documents why the
``/NeedAppearances`` toggle still has to be set. These tests pin the
behaviour (the toggle still flips) and make sure the source file no
longer carries a literal ``# TODO`` marker."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.tools.import_fdf import ImportFDF


class _FakeAcroForm:
    def __init__(self) -> None:
        self.cached = False
        self.imported: object | None = None
        self.need_appearances: bool | None = None

    def set_cache_fields(self, value: bool) -> None:
        self.cached = value

    def import_fdf(self, fdf) -> None:
        self.imported = fdf

    def set_need_appearances(self, value: bool) -> None:
        self.need_appearances = value


class _FakeCatalog:
    def __init__(self, form: _FakeAcroForm | None) -> None:
        self._form = form

    def get_acro_form(self) -> _FakeAcroForm | None:
        return self._form


class _FakeDoc:
    def __init__(self, form: _FakeAcroForm | None) -> None:
        self._cat = _FakeCatalog(form)

    def get_document_catalog(self) -> _FakeCatalog:
        return self._cat


def test_import_fdf_sets_need_appearances() -> None:
    form = _FakeAcroForm()
    doc = _FakeDoc(form)
    fdf = object()
    ImportFDF().import_fdf(doc, fdf)
    assert form.cached is True
    assert form.imported is fdf
    assert form.need_appearances is True


def test_import_fdf_no_acroform_short_circuits() -> None:
    doc = _FakeDoc(None)
    ImportFDF().import_fdf(doc, object())  # should not raise


def test_import_fdf_source_has_no_bare_todo() -> None:
    src = Path(__file__).resolve().parents[2] / "pypdfbox" / "tools" / "import_fdf.py"
    text = src.read_text(encoding="utf-8")
    # The legacy bare ``# TODO`` marker should be gone — replaced by a
    # multi-line explanatory comment.
    assert "# TODO this can be removed when we create appearance streams" not in text
    assert "Mirrors upstream" in text
