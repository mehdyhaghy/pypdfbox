"""Coverage-boost tests for ``pypdfbox.pdmodel.fixup.acro_form_default_fixup``.

Targets the catalog-without-get_acro_form short-circuit, the
single-argument ``get_acro_form`` fallback (TypeError path), and the
``/NeedAppearances=True`` branch with and without orphan widgets.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.pdmodel.fixup.acro_form_default_fixup import AcroFormDefaultFixup

# ---------- Stubs ---------------------------------------------------------


class _StubCos:
    def set_need_to_be_updated(self, _: bool) -> None:
        return None

    def get_cos_dictionary(self, _: object) -> object | None:
        return None

    def set_item(self, _k: object, _v: object) -> None:
        return None


class _StubAcroForm:
    def __init__(
        self,
        *,
        need_appearances: bool,
        fields: list[Any] | None,
    ) -> None:
        self._need = need_appearances
        self._fields = fields
        self._refreshed = False
        self._da = "/Helv 0 Tf 0 g "
        self._dr: Any = None

    def get_need_appearances(self) -> bool:
        return self._need

    def get_fields(self) -> list[Any] | None:
        return self._fields

    def refresh_appearances(self) -> None:
        self._refreshed = True

    def get_cos_object(self) -> Any:
        return _StubCos()

    def get_field_tree(self) -> list[Any]:
        return []

    def get_default_appearance(self) -> str:
        return self._da

    def set_default_appearance(self, value: str) -> None:
        self._da = value

    def get_default_resources(self) -> Any:
        return self._dr

    def set_default_resources(self, resources: Any) -> None:
        self._dr = resources


class _CatalogNoAcroForm:
    """Catalog without ``get_acro_form`` — should make the fixup return early."""

    def get_pages(self) -> list[Any]:
        return []


class _CatalogReturnsNone:
    def get_acro_form(self, _fixup: object | None = None) -> Any:
        return None


class _CatalogSingleArg:
    """``get_acro_form()`` accepts no arguments, so calling with one
    raises ``TypeError`` and the fixup falls back to the zero-arg call.
    """

    def __init__(self, acro_form: _StubAcroForm) -> None:
        self._af = acro_form
        self.fallback_count = 0

    def get_acro_form(self) -> _StubAcroForm:
        self.fallback_count += 1
        return self._af


class _CatalogTwoArg:
    def __init__(self, acro_form: _StubAcroForm) -> None:
        self._af = acro_form

    def get_acro_form(self, _fixup: object | None = None) -> _StubAcroForm:
        return self._af


class _StubDocument:
    def __init__(self, catalog: Any) -> None:
        self._catalog = catalog
        self._pages: list[Any] = []

    def get_document_catalog(self) -> Any:
        return self._catalog

    def get_pages(self) -> list[Any]:
        return self._pages


# ---------- Tests --------------------------------------------------------


def test_apply_short_circuits_when_catalog_has_no_get_acro_form() -> None:
    doc = _StubDocument(_CatalogNoAcroForm())
    # Must not raise even though catalog lacks get_acro_form (line 47).
    AcroFormDefaultFixup(doc).apply()


def test_apply_short_circuits_when_acroform_is_none() -> None:
    doc = _StubDocument(_CatalogReturnsNone())
    AcroFormDefaultFixup(doc).apply()


def test_apply_falls_back_to_zero_arg_get_acro_form() -> None:
    """Catalog's get_acro_form does not accept a fixup argument; the
    fixup must retry with no args (line 50-51).
    """
    af = _StubAcroForm(need_appearances=False, fields=[object()])
    catalog = _CatalogSingleArg(af)
    doc = _StubDocument(catalog)
    AcroFormDefaultFixup(doc).apply()
    # The defaults processor + the orphan-widget / refresh chain each
    # call ``get_acro_form`` — what matters is that the TypeError-fallback
    # was exercised at least once for this catalog.
    assert catalog.fallback_count >= 1


def test_apply_returns_when_need_appearances_false() -> None:
    af = _StubAcroForm(need_appearances=False, fields=[object()])
    doc = _StubDocument(_CatalogTwoArg(af))
    AcroFormDefaultFixup(doc).apply()
    assert af._refreshed is False


def test_apply_refresh_when_need_appearances_and_fields_present() -> None:
    """need_appearances=True + non-empty fields list -> skip orphan
    rebuild but still call refresh (line 63).
    """
    af = _StubAcroForm(need_appearances=True, fields=[object()])
    doc = _StubDocument(_CatalogTwoArg(af))
    AcroFormDefaultFixup(doc).apply()
    assert af._refreshed is True


def test_apply_rebuilds_orphans_when_no_fields() -> None:
    """need_appearances=True + empty fields list -> orphan-widgets
    processor must run, then the refresh processor.
    """
    af = _StubAcroForm(need_appearances=True, fields=[])
    doc = _StubDocument(_CatalogTwoArg(af))
    AcroFormDefaultFixup(doc).apply()
    assert af._refreshed is True


def test_apply_rebuilds_orphans_when_fields_is_none() -> None:
    af = _StubAcroForm(need_appearances=True, fields=None)
    doc = _StubDocument(_CatalogTwoArg(af))
    AcroFormDefaultFixup(doc).apply()
    assert af._refreshed is True
