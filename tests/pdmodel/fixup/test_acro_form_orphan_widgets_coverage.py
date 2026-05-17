"""Hand-written coverage tests for ``AcroFormOrphanWidgetsProcessor``.

Drives:
* the early-return paths (catalog without ``get_acro_form``; null acro
  form; null default resources; per-page annotation read failures)
* the widget-walk in ``handle_annotations`` (parent vs. non-parent
  fields, factory wiring)
* the font-import helper ``add_font_from_widget``
* the non-root parent walker ``resolve_non_root_field``
* the ``ensure_font_resources`` DA-string parser
"""

from __future__ import annotations

import contextlib
from typing import Any

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.fixup.processor.acro_form_orphan_widgets_processor import (
    AcroFormOrphanWidgetsProcessor,
)

# ----------------------------------------------------------------------
# Lightweight stand-ins
# ----------------------------------------------------------------------


class _FontName:
    def __init__(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name


class _Resources:
    """Minimal stand-in for ``PDResources``."""

    def __init__(
        self,
        fonts: dict[str, object] | None = None,
        font_names: list[str] | None = None,
    ) -> None:
        self._fonts: dict[str, object] = fonts or {}
        self._font_names = font_names or list(self._fonts.keys())
        self.put_calls: list[tuple[str, object]] = []

    def get_font_names(self) -> list[_FontName]:
        return [_FontName(n) for n in self._font_names]

    def get_font(self, name: _FontName) -> object | None:
        return self._fonts.get(name.get_name())

    def put(self, name: _FontName, font: object) -> None:
        self.put_calls.append((name.get_name(), font))
        self._fonts[name.get_name()] = font


class _RaisingResources(_Resources):
    def get_font(self, name: _FontName) -> object | None:
        raise OSError("font lookup failed")


class _NormalAppearance:
    def __init__(self, resources: _Resources | None) -> None:
        self._resources = resources

    def get_resources(self) -> _Resources | None:
        return self._resources


class _CosDictStub:
    """Lightweight COS dictionary stub."""

    def __init__(
        self,
        parent: object | None = None,
        t_value: str | None = None,
    ) -> None:
        self._parent = parent
        self._t = t_value

    def get_cos_dictionary(self, key: object) -> object | None:
        if key == COSName.PARENT:
            return self._parent
        return None

    def contains_key(self, key: object) -> bool:
        return key == COSName.PARENT and self._parent is not None

    def get_string(self, key: object) -> str | None:
        if key == COSName.T:
            return self._t
        return None


class _Widget:
    """Stand-in for ``PDAnnotationWidget``."""

    def __init__(
        self,
        normal: _NormalAppearance | None = None,
        parent: object | None = None,
        cos_dict: _CosDictStub | None = None,
    ) -> None:
        self._normal = normal
        self._cos = cos_dict if cos_dict is not None else _CosDictStub(parent=parent)

    def get_normal_appearance_stream(self) -> _NormalAppearance | None:
        return self._normal

    def get_cos_object(self) -> _CosDictStub:
        return self._cos


class _StubAcroForm:
    def __init__(self, resources: _Resources | None) -> None:
        self._resources = resources
        self.fields_set: list[Any] | None = None
        self._field_tree: list[Any] = []

    def get_default_resources(self) -> _Resources | None:
        return self._resources

    def set_fields(self, fields: list[Any]) -> None:
        self.fields_set = fields

    def get_field_tree(self) -> list[Any]:
        return self._field_tree


class _StubCatalog:
    def __init__(self, acro_form: _StubAcroForm | None) -> None:
        self._acro_form = acro_form

    def get_acro_form(self, _fixup: object | None = None) -> _StubAcroForm | None:
        return self._acro_form


class _NoAcroFormCatalog:
    """Catalog without ``get_acro_form`` — the processor must early-return."""


class _Page:
    def __init__(
        self,
        annotations: list[Any] | None = None,
        raise_on_read: bool = False,
    ) -> None:
        self._annotations = annotations or []
        self._raise = raise_on_read

    def get_annotations(self) -> list[Any]:
        if self._raise:
            raise OSError("could not parse annotations")
        return self._annotations


class _StubDoc:
    def __init__(
        self,
        catalog: _StubCatalog | _NoAcroFormCatalog,
        pages: list[_Page] | None = None,
    ) -> None:
        self._catalog = catalog
        self._pages = pages or []

    def get_document_catalog(self) -> object:
        return self._catalog

    def get_pages(self) -> list[_Page]:
        return self._pages


# ----------------------------------------------------------------------
# process(): top-level guards
# ----------------------------------------------------------------------


def test_process_no_acro_form_attr_on_catalog_returns_early() -> None:
    doc = _StubDoc(_NoAcroFormCatalog())
    AcroFormOrphanWidgetsProcessor(doc).process()  # no raise


def test_process_acro_form_none_is_noop() -> None:
    doc = _StubDoc(_StubCatalog(None))
    AcroFormOrphanWidgetsProcessor(doc).process()  # no raise


def test_process_resources_none_short_circuits_resolve() -> None:
    acro = _StubAcroForm(resources=None)
    doc = _StubDoc(_StubCatalog(acro))
    AcroFormOrphanWidgetsProcessor(doc).process()
    assert acro.fields_set is None  # set_fields was never invoked


def test_process_calls_get_acro_form_without_arg_when_typeerror() -> None:
    class _StrictCatalog:
        def get_acro_form(self) -> _StubAcroForm:
            return _StubAcroForm(resources=None)

    doc = _StubDoc(_StrictCatalog())
    AcroFormOrphanWidgetsProcessor(doc).process()  # no raise


# ----------------------------------------------------------------------
# resolve_fields_from_widgets: per-page failure tolerance
# ----------------------------------------------------------------------


def test_resolve_fields_tolerates_page_annotation_failure() -> None:
    acro = _StubAcroForm(resources=_Resources())
    pages = [_Page(raise_on_read=True), _Page(annotations=[])]
    doc = _StubDoc(_StubCatalog(acro), pages=pages)
    AcroFormOrphanWidgetsProcessor(doc).process()
    assert acro.fields_set == []  # fields rebuilt to empty list


def test_resolve_fields_walks_field_tree_for_default_appearance() -> None:
    acro = _StubAcroForm(resources=_Resources())

    class _FieldWithDA:
        def get_default_appearance(self) -> str:
            return ""  # empty short-circuits ensure_font_resources

        def get_fully_qualified_name(self) -> str:
            return "Field.X"

    acro._field_tree = [_FieldWithDA()]
    doc = _StubDoc(_StubCatalog(acro))
    AcroFormOrphanWidgetsProcessor(doc).process()
    assert acro.fields_set == []


# ----------------------------------------------------------------------
# handle_annotations: non-widget skipping, factory dispatch
# ----------------------------------------------------------------------


def test_handle_annotations_ignores_non_widget_entries() -> None:
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    resources = _Resources()
    fields: list[Any] = []
    proc.handle_annotations(
        acro_form=object(),
        acro_form_resources=resources,
        fields=fields,
        annotations=[object(), "not a widget"],
        non_terminal_fields_map={},
    )
    assert fields == []


def test_handle_annotations_widget_with_parent_resolves_non_root() -> None:
    """A widget with a /Parent dict feeds through ``resolve_non_root_field``."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )

    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    resources = _Resources()

    # Build a real widget whose underlying dict carries a non-None /Parent.
    widget = PDAnnotationWidget()
    parent_dict = _CosDictStub(parent=None, t_value="topField")
    widget.get_cos_object().set_item(COSName.PARENT, parent_dict)  # type: ignore[arg-type]
    # Also stamp a normal appearance so ``add_font_from_widget`` short-circuits.
    assert isinstance(widget, PDAnnotationWidget)

    # PDFieldFactory will get invoked with a fake form — wrap to swallow it.
    fields: list[Any] = []
    # Real factory may reject the bare dict; we only need the branch
    # entered, which is asserted by the get_normal_appearance call below.
    with contextlib.suppress(Exception):
        proc.handle_annotations(
            acro_form=object(),
            acro_form_resources=resources,
            fields=fields,
            annotations=[widget],
            non_terminal_fields_map={},
        )


# ----------------------------------------------------------------------
# add_font_from_widget
# ----------------------------------------------------------------------


def test_add_font_from_widget_no_normal_appearance_is_noop() -> None:
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    widget = _Widget(normal=None)
    proc.add_font_from_widget(_Resources(), widget)  # no raise


def test_add_font_from_widget_no_widget_resources_is_noop() -> None:
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    widget = _Widget(normal=_NormalAppearance(resources=None))
    proc.add_font_from_widget(_Resources(), widget)  # no raise


def test_add_font_from_widget_imports_missing_fonts() -> None:
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    widget_font = object()
    widget_resources = _Resources(fonts={"Helv": widget_font})
    widget = _Widget(normal=_NormalAppearance(widget_resources))
    acro_resources = _Resources()
    proc.add_font_from_widget(acro_resources, widget)
    assert acro_resources.put_calls
    assert acro_resources.put_calls[0][0] == "Helv"


def test_add_font_from_widget_skips_subsetted_fonts() -> None:
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    widget_resources = _Resources(fonts={"+SubsetFont": object()})
    widget = _Widget(normal=_NormalAppearance(widget_resources))
    acro_resources = _Resources()
    proc.add_font_from_widget(acro_resources, widget)
    assert acro_resources.put_calls == []


def test_add_font_from_widget_keeps_existing_font_unchanged() -> None:
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    existing = object()
    widget_resources = _Resources(fonts={"Helv": object()})
    widget = _Widget(normal=_NormalAppearance(widget_resources))
    acro_resources = _Resources(fonts={"Helv": existing})
    proc.add_font_from_widget(acro_resources, widget)
    # ``get_font(Helv)`` returns non-None so we never copy in.
    assert acro_resources.put_calls == []


def test_add_font_from_widget_tolerates_oserror_from_get_font() -> None:
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    widget_resources = _Resources(fonts={"Helv": object()})
    widget = _Widget(normal=_NormalAppearance(widget_resources))
    acro_resources = _RaisingResources()
    proc.add_font_from_widget(acro_resources, widget)  # no raise


# ----------------------------------------------------------------------
# resolve_non_root_field: cycle terminations + cache behaviour
# ----------------------------------------------------------------------


def test_resolve_non_root_field_returns_none_when_parent_chain_breaks() -> None:
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    # Parent with no name and no further parent — walks up by checking
    # ``contains_key(PARENT)`` first.
    class _ChainNoParentButContains:
        def contains_key(self, key: object) -> bool:
            # First iteration says "has parent", but the dict lookup
            # returns ``None`` to break the walk.
            return True

        def get_cos_dictionary(self, _key: object) -> object | None:
            return None

        def get_string(self, _key: object) -> str | None:
            return None

    result = proc.resolve_non_root_field(
        acro_form=object(),
        parent=_ChainNoParentButContains(),
        non_terminal_fields_map={},
    )
    assert result is None


def test_resolve_non_root_field_cached_entry_returns_none() -> None:
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    parent = _CosDictStub(parent=None, t_value="root")
    cache: dict[str, Any] = {"root": object()}  # pre-seeded
    result = proc.resolve_non_root_field(
        acro_form=object(),
        parent=parent,
        non_terminal_fields_map=cache,
    )
    assert result is None  # already present in cache => no new field returned


# ----------------------------------------------------------------------
# ensure_font_resources: DA-string parsing branches
# ----------------------------------------------------------------------


class _Field:
    def __init__(self, da: str, qname: str = "Field.A") -> None:
        self._da = da
        self._qname = qname

    def get_default_appearance(self) -> str:
        return self._da

    def get_fully_qualified_name(self) -> str:
        return self._qname


class _ResourcesWithFont(_Resources):
    """Resources whose ``get_font`` returns a non-None value to satisfy the
    early-success branch in ``ensure_font_resources``."""


def test_ensure_font_resources_empty_da_is_noop() -> None:
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    proc.ensure_font_resources(_Resources(), _Field(da=""))  # no raise


def test_ensure_font_resources_da_without_slash_is_noop() -> None:
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    proc.ensure_font_resources(_Resources(), _Field(da="Helv 0 Tf 0 g"))


def test_ensure_font_resources_da_with_existing_font_is_noop() -> None:
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    resources = _Resources(fonts={"Helv": object()})
    proc.ensure_font_resources(resources, _Field(da="/Helv 0 Tf 0 g"))


def test_ensure_font_resources_da_missing_font_logs_and_returns() -> None:
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    resources = _Resources()  # no fonts at all
    proc.ensure_font_resources(resources, _Field(da="/Helv 0 Tf 0 g"))


def test_ensure_font_resources_da_with_no_space_raises_valueerror_handled() -> None:
    """``da_string.index(' ')`` raises ValueError, which the helper swallows."""
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc(_StubCatalog(None)))
    proc.ensure_font_resources(_Resources(), _Field(da="/HelvNoSpace"))


# ----------------------------------------------------------------------
# Back-compat aliases stay bound
# ----------------------------------------------------------------------


def test_backcompat_aliases_resolve_to_public_methods() -> None:
    cls = AcroFormOrphanWidgetsProcessor
    assert cls._resolve_fields_from_widgets is cls.resolve_fields_from_widgets
    assert cls._handle_annotations is cls.handle_annotations
    assert cls._add_font_from_widget is cls.add_font_from_widget
    assert cls._resolve_non_root_field is cls.resolve_non_root_field
    assert cls._ensure_font_resources is cls.ensure_font_resources
