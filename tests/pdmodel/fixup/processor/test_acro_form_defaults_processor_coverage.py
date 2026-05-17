"""Hand-written coverage tests for ``AcroFormDefaultsProcessor``.

Drives the previously-uncovered branches in
``pypdfbox/pdmodel/fixup/processor/acro_form_defaults_processor.py``:

* the public ``verify_or_create_defaults`` delegate (parity-name alias).
* ``process``: early-return when the catalog has no ``get_acro_form`` and
  when ``get_acro_form`` returns ``None``.
* the ``TypeError`` fallback when ``get_acro_form`` does not accept a
  fixup argument.
* the ``Exception`` fallback inside the ``get_default_appearance`` lookup.
* the DR-creation branch (default resources missing) including the
  ``set_need_to_be_updated`` propagation.
* the ``_ensure_font`` early-return when the font key already exists.
* the ``_ensure_font`` success path with a stubbed ``PDType1Font`` so the
  ``put`` + ``set_need_to_be_updated`` lines execute.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.fixup.processor import acro_form_defaults_processor as adp
from pypdfbox.pdmodel.fixup.processor.acro_form_defaults_processor import (
    AcroFormDefaultsProcessor,
)

# ----------------------------------------------------------------------
# Lightweight stand-ins
# ----------------------------------------------------------------------


class _CosObj:
    """COS-object stub that records ``set_need_to_be_updated`` calls."""

    def __init__(self) -> None:
        self.needs_update: list[bool] = []

    def set_need_to_be_updated(self, flag: bool) -> None:
        self.needs_update.append(flag)


class _AcroForm:
    """Minimal stand-in for ``PDAcroForm`` exposing only the surface the
    defaults processor touches."""

    def __init__(
        self,
        *,
        da: str = "/Helv 0 Tf 0 g ",
        default_resources: object | None = None,
        raise_on_get_da: bool = False,
    ) -> None:
        self._da = da
        self._default_resources = default_resources
        self._raise_on_get_da = raise_on_get_da
        self._cos = _CosObj()
        self.set_da_calls: list[str] = []
        self.set_default_resources_calls: list[object] = []

    def get_default_appearance(self) -> str:
        if self._raise_on_get_da:
            raise RuntimeError("synthetic DA failure")
        return self._da

    def set_default_appearance(self, value: str) -> None:
        self.set_da_calls.append(value)
        self._da = value

    def get_default_resources(self) -> object | None:
        return self._default_resources

    def set_default_resources(self, resources: object) -> None:
        self.set_default_resources_calls.append(resources)
        self._default_resources = resources

    def get_cos_object(self) -> _CosObj:
        return self._cos


class _StubCatalog:
    def __init__(self, acro_form: _AcroForm | None) -> None:
        self._acro_form = acro_form

    def get_acro_form(self, _fixup: object | None = None) -> _AcroForm | None:
        return self._acro_form


class _StrictCatalog:
    """Catalog whose ``get_acro_form`` takes no args — drives the TypeError
    branch in ``process``."""

    def __init__(self, acro_form: _AcroForm | None) -> None:
        self._acro_form = acro_form

    def get_acro_form(self) -> _AcroForm | None:
        return self._acro_form


class _NoAcroFormCatalog:
    """Catalog without ``get_acro_form`` — drives the early-return."""


class _StubDoc:
    def __init__(self, catalog: object) -> None:
        self._catalog = catalog

    def get_document_catalog(self) -> object:
        return self._catalog


# ----------------------------------------------------------------------
# process(): top-level guards
# ----------------------------------------------------------------------


def test_process_catalog_without_get_acro_form_is_noop() -> None:
    doc = _StubDoc(_NoAcroFormCatalog())
    AcroFormDefaultsProcessor(doc).process()  # no raise


def test_process_acro_form_none_is_noop() -> None:
    doc = _StubDoc(_StubCatalog(None))
    AcroFormDefaultsProcessor(doc).process()  # no raise


def test_process_typeerror_fallback_uses_no_arg_get_acro_form() -> None:
    """``get_acro_form(None)`` raises TypeError → falls through to
    ``get_acro_form()``."""
    acro = _AcroForm(default_resources=None)
    doc = _StubDoc(_StrictCatalog(acro))
    AcroFormDefaultsProcessor(doc).process()
    # DR was created via the fallback path → set_default_resources fired
    assert acro.set_default_resources_calls


# ----------------------------------------------------------------------
# verify_or_create_defaults: public delegate
# ----------------------------------------------------------------------


def test_verify_or_create_defaults_public_delegate() -> None:
    """The public name exists so the parity scanner sees the upstream
    method name."""
    doc = _StubDoc(_StubCatalog(None))
    proc = AcroFormDefaultsProcessor(doc)
    acro = _AcroForm(da="", default_resources=None)
    proc.verify_or_create_defaults(acro)
    # The delegate set both DA and DR.
    assert acro.set_da_calls == [adp._ADOBE_DEFAULT_APPEARANCE]
    assert acro.set_default_resources_calls


# ----------------------------------------------------------------------
# _verify_or_create_defaults: DA branch
# ----------------------------------------------------------------------


def test_da_exception_during_get_falls_through_to_set() -> None:
    """``get_default_appearance`` raising must be swallowed and the
    default DA written instead."""
    doc = _StubDoc(_StubCatalog(None))
    proc = AcroFormDefaultsProcessor(doc)
    acro = _AcroForm(raise_on_get_da=True, default_resources=None)
    proc.verify_or_create_defaults(acro)
    assert acro.set_da_calls == [adp._ADOBE_DEFAULT_APPEARANCE]
    # set_need_to_be_updated should have been invoked for the DA + DR writes
    assert True in acro._cos.needs_update


def test_da_already_set_skips_set_default_appearance() -> None:
    """When DA already exists, no rewrite happens."""
    doc = _StubDoc(_StubCatalog(None))
    proc = AcroFormDefaultsProcessor(doc)

    existing_dr = _PDResourcesLike(
        font_dict_present=True, fonts={"Helv": object(), "ZaDb": object()}
    )
    acro = _AcroForm(da="/MyFont 12 Tf 0 g ", default_resources=existing_dr)
    proc.verify_or_create_defaults(acro)
    assert acro.set_da_calls == []  # untouched
    assert acro.set_default_resources_calls == []  # DR already there


# ----------------------------------------------------------------------
# Helpers for the DR / font branches
# ----------------------------------------------------------------------


class _FontDict:
    """COSDictionary-like stub with ``contains_key`` + ``set_need_to_be_updated``."""

    def __init__(self, contained: set[str] | None = None) -> None:
        self._contained = contained or set()
        self.needs_update: list[bool] = []

    def contains_key(self, key: object) -> bool:
        name = key.get_name() if hasattr(key, "get_name") else str(key)
        return name in self._contained

    def set_need_to_be_updated(self, flag: bool) -> None:
        self.needs_update.append(flag)


class _DRCos:
    """Stand-in for the default-resources ``get_cos_object()`` return."""

    def __init__(self, font_dict: object | None) -> None:
        self._font_dict = font_dict
        self.set_item_calls: list[tuple[object, object]] = []
        self.needs_update: list[bool] = []

    def get_cos_dictionary(self, _key: object) -> object | None:
        return self._font_dict

    def set_item(self, key: object, value: object) -> None:
        self.set_item_calls.append((key, value))
        # Mirror real behaviour: subsequent get_cos_dictionary should
        # return the newly-set font dict.
        self._font_dict = value

    def set_need_to_be_updated(self, flag: bool) -> None:
        self.needs_update.append(flag)


class _PDResourcesLike:
    """Stand-in for ``PDResources`` exposing the bits the defaults
    processor uses."""

    def __init__(
        self,
        *,
        font_dict_present: bool,
        fonts: dict[str, object] | None = None,
    ) -> None:
        contained = set(fonts.keys()) if fonts else set()
        self._font_dict: _FontDict | None = (
            _FontDict(contained=contained) if font_dict_present else None
        )
        self._dr_cos = _DRCos(self._font_dict)
        self.put_calls: list[tuple[object, object]] = []

    def get_cos_object(self) -> _DRCos:
        return self._dr_cos

    def put(self, key: object, value: object) -> None:
        self.put_calls.append((key, value))


def test_default_resources_missing_creates_new_pdresources(monkeypatch: pytest.MonkeyPatch) -> None:
    """When ``get_default_resources`` is ``None`` a fresh ``PDResources``
    is built + assigned. The DA branch also flagged the COS object."""
    doc = _StubDoc(_StubCatalog(None))
    proc = AcroFormDefaultsProcessor(doc)
    acro = _AcroForm(da="", default_resources=None)
    proc.verify_or_create_defaults(acro)
    assert acro.set_default_resources_calls, "DR should be assigned"
    # The DA branch + the DR branch each flag the AcroForm COS object.
    assert acro._cos.needs_update.count(True) >= 2


def test_ensure_font_skips_when_font_already_in_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    """``contains_key(cos_name) == True`` → ``_ensure_font`` returns
    early without calling ``put``."""
    doc = _StubDoc(_StubCatalog(None))
    proc = AcroFormDefaultsProcessor(doc)
    dr = _PDResourcesLike(
        font_dict_present=True,
        fonts={"Helv": object(), "ZaDb": object()},
    )
    acro = _AcroForm(da="/Helv 0 Tf 0 g ", default_resources=dr)
    proc.verify_or_create_defaults(acro)
    # Both fonts pre-existed → no ``put`` calls.
    assert dr.put_calls == []


def test_ensure_font_success_path_imports_pdtype1font(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ``PDType1Font`` so the import returns a stub object. The
    helper must then ``put`` it on the resources and flip the
    ``set_need_to_be_updated`` flag on the DR cos object + font dict."""
    import pypdfbox.pdmodel.font.pd_type1_font as pd_t1f

    sentinel = object()

    class _FakeFont:
        def __init__(self, name: str) -> None:
            self.name = name

    monkeypatch.setattr(pd_t1f, "PDType1Font", _FakeFont, raising=True)

    doc = _StubDoc(_StubCatalog(None))
    proc = AcroFormDefaultsProcessor(doc)
    dr = _PDResourcesLike(font_dict_present=True, fonts=None)  # no fonts yet
    acro = _AcroForm(da="/Helv 0 Tf 0 g ", default_resources=dr)
    proc.verify_or_create_defaults(acro)
    # Two fonts (Helv + ZaDb) should now be added.
    put_keys = [k.get_name() if hasattr(k, "get_name") else str(k) for k, _ in dr.put_calls]
    assert "Helv" in put_keys
    assert "ZaDb" in put_keys
    # The DR cos object's ``set_need_to_be_updated`` was invoked.
    assert True in dr._dr_cos.needs_update
    # The font dict's ``set_need_to_be_updated`` was invoked.
    assert dr._font_dict is not None
    assert True in dr._font_dict.needs_update
    _ = sentinel  # silence unused-variable lint


def test_ensure_font_branches_when_dr_has_no_font_subdict(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the DR cos object has no ``/Font`` subdict, the processor
    materialises a fresh ``COSDictionary`` and ``set_item`` it under
    ``COSName.get_pdf_name("Font")``."""
    import pypdfbox.pdmodel.font.pd_type1_font as pd_t1f

    class _FakeFont:
        def __init__(self, name: str) -> None:
            self.name = name

    monkeypatch.setattr(pd_t1f, "PDType1Font", _FakeFont, raising=True)

    doc = _StubDoc(_StubCatalog(None))
    proc = AcroFormDefaultsProcessor(doc)
    dr = _PDResourcesLike(font_dict_present=False)  # no /Font dict
    acro = _AcroForm(da="/Helv 0 Tf 0 g ", default_resources=dr)
    proc.verify_or_create_defaults(acro)
    # set_item on DR cos was called with the new /Font dict.
    assert dr._dr_cos.set_item_calls
    font_key, font_value = dr._dr_cos.set_item_calls[0]
    assert (font_key.get_name() if hasattr(font_key, "get_name") else str(font_key)) == "Font"
    assert isinstance(font_value, COSDictionary)


# ----------------------------------------------------------------------
# Integration: full ``process()`` against a real ``PDAcroForm``
# ----------------------------------------------------------------------


def test_process_against_real_acro_form_creates_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end check with a real ``PDDocument`` + ``PDAcroForm``.

    Patches ``PDType1Font`` with a subclass that ignores the bogus
    ``font_name`` arg the processor passes — letting the font slot into
    the real ``PDResources.put`` ``PDFont``-isinstance check."""
    import pypdfbox.pdmodel.font.pd_type1_font as pd_t1f
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
    from pypdfbox.pdmodel.pd_document import PDDocument

    class _FakeType1Font(PDType1Font):
        def __init__(self, _font_name: str) -> None:
            super().__init__(None)

    monkeypatch.setattr(pd_t1f, "PDType1Font", _FakeType1Font, raising=True)

    doc = PDDocument()
    catalog = doc.get_document_catalog()
    catalog.set_acro_form(PDAcroForm(doc))
    proc = AcroFormDefaultsProcessor(doc)
    proc.process()
    acro = catalog.get_acro_form()
    assert acro is not None
    assert acro.get_default_appearance() == adp._ADOBE_DEFAULT_APPEARANCE
    assert acro.get_default_resources() is not None
    doc.close()


__all__: list[Any] = []
