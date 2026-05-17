"""Wave 1331 coverage boost: ``AcroFormOrphanWidgetsProcessor``.

Covers the widget-walk happy paths in ``handle_annotations`` (lines
112-122) and the ``resolve_non_root_field`` factory-success path (lines
182-185) by monkey-patching ``PDFieldFactory.create_field``.

The ImportError branches at 103-104 and 174-175 are not exercised —
they exist as belt-and-braces fallbacks and the modules are always
importable in the test environment.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.fixup.processor.acro_form_orphan_widgets_processor import (
    AcroFormOrphanWidgetsProcessor,
)

# --------------------------------------------------------------------------
# Lightweight stand-ins (mirror the styling in the wave-1315 file)
# --------------------------------------------------------------------------


class _CosDictStub:
    """Tiny COS-dict stand-in with the methods the processor uses."""

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


class _NormalAppearance:
    def get_resources(self) -> None:
        return None


class _FakeField:
    """Stand-in for ``PDField`` returned by a patched factory."""

    def __init__(self, qname: str) -> None:
        self._qname = qname

    def get_fully_qualified_name(self) -> str:
        return self._qname


class _StubDoc:
    """Minimal document carrying just a catalog reference."""

    def __init__(self) -> None:
        self._pages: list[Any] = []

    def get_document_catalog(self) -> object:  # pragma: no cover - unused
        raise AssertionError("not used in these tests")

    def get_pages(self) -> list[Any]:
        return self._pages


# --------------------------------------------------------------------------
# handle_annotations — widget with /Parent → resolve_non_root_field path
# --------------------------------------------------------------------------


def test_handle_annotations_widget_with_parent_appends_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 112-116: widget carrying /Parent → ``resolve_non_root_field``
    returns a non-None field → appended to ``fields``."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )
    from pypdfbox.pdmodel.interactive.form import pd_field_factory as pff

    parent_dict = _CosDictStub(parent=None, t_value="topField")
    cos_dict = _CosDictStub(parent=parent_dict, t_value="widgetT")

    widget = PDAnnotationWidget.__new__(PDAnnotationWidget)
    widget.get_cos_object = lambda: cos_dict  # type: ignore[attr-defined,method-assign]
    widget.get_normal_appearance_stream = lambda: None  # type: ignore[attr-defined,method-assign]

    captured: list[tuple[Any, ...]] = []

    def _fake_create_field(form: object, field: object, parent: object) -> _FakeField:
        captured.append((form, field, parent))
        return _FakeField("Parent.X")

    monkeypatch.setattr(pff.PDFieldFactory, "create_field", _fake_create_field)

    proc = AcroFormOrphanWidgetsProcessor(_StubDoc())
    fields: list[Any] = []
    proc.handle_annotations(
        acro_form=object(),
        acro_form_resources=object(),
        fields=fields,
        annotations=[widget],
        non_terminal_fields_map={},
    )
    assert len(fields) == 1
    assert isinstance(fields[0], _FakeField)
    assert captured  # factory got called via resolve_non_root_field


def test_handle_annotations_widget_with_parent_resolved_none_does_not_append(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reciprocal branch — ``resolve_non_root_field`` returns None
    (because the cache already has the qualified name) — must skip the
    append."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )
    from pypdfbox.pdmodel.interactive.form import pd_field_factory as pff

    parent_dict = _CosDictStub(parent=None, t_value="cached")
    cos_dict = _CosDictStub(parent=parent_dict)

    widget = PDAnnotationWidget.__new__(PDAnnotationWidget)
    widget.get_cos_object = lambda: cos_dict  # type: ignore[attr-defined,method-assign]
    widget.get_normal_appearance_stream = lambda: None  # type: ignore[attr-defined,method-assign]

    monkeypatch.setattr(
        pff.PDFieldFactory,
        "create_field",
        lambda *_args, **_kw: _FakeField("nope"),
    )

    proc = AcroFormOrphanWidgetsProcessor(_StubDoc())
    fields: list[Any] = []
    proc.handle_annotations(
        acro_form=object(),
        acro_form_resources=object(),
        fields=fields,
        annotations=[widget],
        non_terminal_fields_map={"cached": object()},
    )
    assert fields == []


# --------------------------------------------------------------------------
# handle_annotations — widget without /Parent → terminal factory path
# --------------------------------------------------------------------------


def test_handle_annotations_widget_without_parent_appends_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 121-122: widget without /Parent dispatches straight to
    ``PDFieldFactory.create_field`` and appends a non-None result."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )
    from pypdfbox.pdmodel.interactive.form import pd_field_factory as pff

    cos_dict = _CosDictStub(parent=None)
    widget = PDAnnotationWidget.__new__(PDAnnotationWidget)
    widget.get_cos_object = lambda: cos_dict  # type: ignore[attr-defined,method-assign]
    widget.get_normal_appearance_stream = lambda: None  # type: ignore[attr-defined,method-assign]

    created = _FakeField("Terminal.Y")
    monkeypatch.setattr(
        pff.PDFieldFactory, "create_field", lambda *_args, **_kw: created
    )

    proc = AcroFormOrphanWidgetsProcessor(_StubDoc())
    fields: list[Any] = []
    proc.handle_annotations(
        acro_form=object(),
        acro_form_resources=object(),
        fields=fields,
        annotations=[widget],
        non_terminal_fields_map={},
    )
    assert fields == [created]


def test_handle_annotations_widget_without_parent_skips_when_factory_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reciprocal branch — factory returns ``None`` ⇒ no append."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )
    from pypdfbox.pdmodel.interactive.form import pd_field_factory as pff

    cos_dict = _CosDictStub(parent=None)
    widget = PDAnnotationWidget.__new__(PDAnnotationWidget)
    widget.get_cos_object = lambda: cos_dict  # type: ignore[attr-defined,method-assign]
    widget.get_normal_appearance_stream = lambda: None  # type: ignore[attr-defined,method-assign]

    monkeypatch.setattr(
        pff.PDFieldFactory, "create_field", lambda *_args, **_kw: None
    )

    proc = AcroFormOrphanWidgetsProcessor(_StubDoc())
    fields: list[Any] = []
    proc.handle_annotations(
        acro_form=object(),
        acro_form_resources=object(),
        fields=fields,
        annotations=[widget],
        non_terminal_fields_map={},
    )
    assert fields == []


# --------------------------------------------------------------------------
# resolve_non_root_field: full happy path (lines 182-185)
# --------------------------------------------------------------------------


def test_resolve_non_root_field_creates_and_caches_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 182-185: cache miss → factory call → cache write → return."""
    from pypdfbox.pdmodel.interactive.form import pd_field_factory as pff

    parent = _CosDictStub(parent=None, t_value="missing")
    created = _FakeField("Form.Group.Missing")
    monkeypatch.setattr(
        pff.PDFieldFactory, "create_field", lambda *_args, **_kw: created
    )

    cache: dict[str, Any] = {}
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc())
    result = proc.resolve_non_root_field(
        acro_form=object(),
        parent=parent,
        non_terminal_fields_map=cache,
    )
    assert result is created
    assert cache == {"Form.Group.Missing": created}


def test_resolve_non_root_field_cache_miss_factory_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cache miss but factory returns None ⇒ nothing cached, None returned."""
    from pypdfbox.pdmodel.interactive.form import pd_field_factory as pff

    parent = _CosDictStub(parent=None, t_value="missing")
    monkeypatch.setattr(
        pff.PDFieldFactory, "create_field", lambda *_args, **_kw: None
    )

    cache: dict[str, Any] = {}
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc())
    result = proc.resolve_non_root_field(
        acro_form=object(),
        parent=parent,
        non_terminal_fields_map=cache,
    )
    assert result is None
    assert cache == {}


def test_resolve_non_root_field_walks_parent_chain_to_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Walk through several /Parent levels before instantiating."""
    from pypdfbox.pdmodel.interactive.form import pd_field_factory as pff

    root = _CosDictStub(parent=None, t_value="root")
    middle = _CosDictStub(parent=root, t_value="middle")
    leaf = _CosDictStub(parent=middle, t_value="leaf")

    created = _FakeField("root")
    monkeypatch.setattr(
        pff.PDFieldFactory, "create_field", lambda *_args, **_kw: created
    )

    cache: dict[str, Any] = {}
    proc = AcroFormOrphanWidgetsProcessor(_StubDoc())
    result = proc.resolve_non_root_field(
        acro_form=object(),
        parent=leaf,
        non_terminal_fields_map=cache,
    )
    # Walked up through middle → root; factory used the root dict.
    assert result is created
    assert "root" in cache
