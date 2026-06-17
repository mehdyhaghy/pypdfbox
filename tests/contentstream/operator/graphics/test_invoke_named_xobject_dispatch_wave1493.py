"""Dispatch-arm pins for ``InvokeNamedXObject`` (the ``Do`` operator,
upstream ``org.apache.pdfbox.contentstream.operator.graphics.DrawObject``).

The base ``test_invoke_named_xobject.py`` exercises operand validation and the
no-context / no-resources early-returns. This module drives the operator with a
recording stub context so the *resolved-XObject* dispatch is observable:

* an unresolved name -> ``MissingResourceException``;
* an image XObject -> ``context.draw_image``;
* a transparency group -> ``context.show_transparency_group``;
* any other form XObject -> ``context.show_form``;
* a form recognised only by its ``is_form_xobject`` attribute (not class name)
  -> ``context.show_form``;
* a resolved XObject of an unrecognised kind -> no dispatch (silent skip),
  mirroring upstream's lack of a catch-all branch.

The type dispatch keys on ``type(obj).__name__``, so the stubs below are named
``PDImageXObject`` / ``PDTransparencyGroup`` / ``PDFormXObject`` to match the
real production class names without importing the heavy image/rendering stack.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.graphics import InvokeNamedXObject
from pypdfbox.cos import COSName
from pypdfbox.pdmodel.missing_resource_exception import MissingResourceException


class _RecordingResources:
    def __init__(self, mapping: dict[str, object]) -> None:
        self._mapping = mapping
        self.requested: list[str] = []

    def get_x_object(self, name: COSName) -> object | None:
        self.requested.append(name.get_name())
        return self._mapping.get(name.get_name())


class _RecordingContext:
    def __init__(self, resources: object | None) -> None:
        self._resources = resources
        self.drawn: list[object] = []
        self.forms: list[object] = []
        self.groups: list[object] = []
        self.level = 0

    def get_resources(self) -> object | None:
        return self._resources

    # The graphics ``Do`` handler guards form/group dispatch with the
    # engine recursion-level counter (matches the real PDFStreamEngine).
    def increase_level(self) -> None:
        self.level += 1

    def decrease_level(self) -> None:
        self.level -= 1

    def get_level(self) -> int:
        return self.level

    def draw_image(self, image: object) -> None:
        self.drawn.append(image)

    def show_form(self, form: object) -> None:
        self.forms.append(form)

    def show_transparency_group(self, group: object) -> None:
        self.groups.append(group)


# Class names must match the production discriminator (type(obj).__name__).
class PDImageXObject:  # noqa: N801 - mirrors the real production class name
    pass


class PDTransparencyGroup:  # noqa: N801 - mirrors the real production class name
    pass


class PDFormXObject:  # noqa: N801 - mirrors the real production class name
    pass


class _AttrForm:
    """A form XObject recognised only by the ``is_form_xobject`` attribute,
    not by class name — the second arm of ``_is_form_xobject``."""

    is_form_xobject = True


class _UnknownXObject:
    pass


def _do() -> Operator:
    return Operator.get_operator("Do")


def _run(mapping: dict[str, object], name: str = "X0") -> _RecordingContext:
    resources = _RecordingResources(mapping)
    context = _RecordingContext(resources)
    handler = InvokeNamedXObject()
    handler.set_context(context)
    handler.process(_do(), [COSName.get_pdf_name(name)])
    return context


def test_image_xobject_is_forwarded_to_draw_image() -> None:
    image = PDImageXObject()
    context = _run({"X0": image})
    assert context.drawn == [image]
    assert context.forms == []
    assert context.groups == []


def test_transparency_group_is_forwarded_to_show_transparency_group() -> None:
    group = PDTransparencyGroup()
    context = _run({"X0": group})
    assert context.groups == [group]
    assert context.drawn == []
    assert context.forms == []


def test_form_xobject_is_forwarded_to_show_form() -> None:
    form = PDFormXObject()
    context = _run({"X0": form})
    assert context.forms == [form]
    assert context.drawn == []
    assert context.groups == []


def test_attribute_only_form_is_forwarded_to_show_form() -> None:
    """A form recognised via the ``is_form_xobject`` attribute (rather than
    class name) still routes to ``show_form``."""
    form = _AttrForm()
    context = _run({"X0": form})
    assert context.forms == [form]


def test_unrecognised_xobject_is_silently_skipped() -> None:
    """A resolved XObject that matches none of the three kinds dispatches to
    nothing — upstream has no catch-all branch."""
    context = _run({"X0": _UnknownXObject()})
    assert context.drawn == []
    assert context.forms == []
    assert context.groups == []


def test_missing_xobject_raises_missing_resource_exception() -> None:
    """A name that resolves to ``None`` raises ``MissingResourceException``
    carrying the requested name, mirroring upstream's ``IOException``."""
    handler = InvokeNamedXObject()
    handler.set_context(_RecordingContext(_RecordingResources({})))
    with pytest.raises(MissingResourceException, match="Missing XObject: Im9"):
        handler.process(_do(), [COSName.get_pdf_name("Im9")])


def test_resource_lookup_uses_the_operand_name() -> None:
    resources = _RecordingResources({"Fm3": PDFormXObject()})
    context = _RecordingContext(resources)
    handler = InvokeNamedXObject()
    handler.set_context(context)
    handler.process(_do(), [COSName.get_pdf_name("Fm3")])
    assert resources.requested == ["Fm3"]
    assert len(context.forms) == 1


def test_no_resources_on_context_is_a_noop() -> None:
    """When the context returns no resources the operator returns before any
    lookup or dispatch — no exception is raised."""
    context = _RecordingContext(None)
    handler = InvokeNamedXObject()
    handler.set_context(context)
    handler.process(_do(), [COSName.get_pdf_name("X0")])
    assert context.drawn == []
    assert context.forms == []
    assert context.groups == []
