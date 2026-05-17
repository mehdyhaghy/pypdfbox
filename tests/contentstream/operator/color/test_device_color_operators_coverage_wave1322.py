"""Coverage boost for the six DeviceGray / DeviceRGB / DeviceCMYK operator
handlers (``G`` / ``g`` / ``RG`` / ``rg`` / ``K`` / ``k``).

Each handler shares the same skeleton — resolve the device color-space from
resources, push it onto the graphics state's stroking or non-stroking slot,
then defer to the base ``SetStrokingColor`` / ``SetNonStrokingColor`` to set
the PDColor. These tests parametrise across all six so every branch in the
``process``, ``get_name`` and ``get_color_space`` methods is exercised.

Wave 1322.
"""

from __future__ import annotations

import builtins
import sys
from typing import Any

import pytest

from pypdfbox.contentstream.operator import Operator, OperatorName
from pypdfbox.contentstream.operator.color.set_non_stroking_color import (
    SetNonStrokingColor,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_device_cmyk_color import (  # noqa: E501
    SetNonStrokingDeviceCMYKColor,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_device_gray_color import (  # noqa: E501
    SetNonStrokingDeviceGrayColor,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_device_rgb_color import (  # noqa: E501
    SetNonStrokingDeviceRGBColor,
)
from pypdfbox.contentstream.operator.color.set_stroking_color import (
    SetStrokingColor,
)
from pypdfbox.contentstream.operator.color.set_stroking_device_cmyk_color import (  # noqa: E501
    SetStrokingDeviceCMYKColor,
)
from pypdfbox.contentstream.operator.color.set_stroking_device_gray_color import (  # noqa: E501
    SetStrokingDeviceGrayColor,
)
from pypdfbox.contentstream.operator.color.set_stroking_device_rgb_color import (  # noqa: E501
    SetStrokingDeviceRGBColor,
)
from pypdfbox.cos import COSFloat, COSName, COSString
from pypdfbox.pdmodel.graphics.color import (
    PDColor,
    PDDeviceCMYK,
    PDDeviceGray,
    PDDeviceRGB,
)


# ---------------------------------------------------------------------------
# Stub graphics state / resources / context.
# ---------------------------------------------------------------------------


class _GraphicsState:
    """Minimal state with both stroking and non-stroking slots."""

    def __init__(self) -> None:
        self.stroking_color_space: Any = None
        self.non_stroking_color_space: Any = None
        self.stroking_color: PDColor | None = None
        self.non_stroking_color: PDColor | None = None

    def set_stroking_color_space(self, cs: Any) -> None:
        self.stroking_color_space = cs

    def set_non_stroking_color_space(self, cs: Any) -> None:
        self.non_stroking_color_space = cs

    def get_stroking_color_space(self) -> Any:
        return self.stroking_color_space

    def get_non_stroking_color_space(self) -> Any:
        return self.non_stroking_color_space

    def set_stroking_color(self, color: PDColor) -> None:
        self.stroking_color = color

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.non_stroking_color = color


class _Resources:
    """Resources stub whose ``get_color_space`` returns a fixed table."""

    def __init__(self, table: dict[str, Any] | None) -> None:
        self._table = table

    def get_color_space(self, name: COSName) -> Any:
        if self._table is None:
            return None
        return self._table.get(name.get_name())


class _ResourcesNoGetter:
    """Resources stub that intentionally omits ``get_color_space``."""


class _Context:
    """Stream-engine surrogate."""

    def __init__(
        self,
        resources: Any = None,
        gate: bool = True,
        graphics_state: _GraphicsState | None = None,
    ) -> None:
        self._resources = resources
        self._gate = gate
        self._graphics_state = graphics_state or _GraphicsState()
        self.stroking_color_calls: list[PDColor] = []
        self.non_stroking_color_calls: list[PDColor] = []

    def is_should_process_color_operators(self) -> bool:
        return self._gate

    def get_resources(self) -> Any:
        return self._resources

    def get_graphics_state(self) -> _GraphicsState:
        return self._graphics_state

    def set_stroking_color(self, color: PDColor) -> None:
        self.stroking_color_calls.append(color)

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.non_stroking_color_calls.append(color)


# ---------------------------------------------------------------------------
# Parametrisation table.
# ---------------------------------------------------------------------------


_STROKING_CASES = [
    (
        SetStrokingDeviceGrayColor,
        "G",
        "DeviceGray",
        PDDeviceGray.INSTANCE,
        [COSFloat(0.5)],
        OperatorName.STROKING_COLOR_GRAY,
    ),
    (
        SetStrokingDeviceRGBColor,
        "RG",
        "DeviceRGB",
        PDDeviceRGB.INSTANCE,
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
        OperatorName.STROKING_COLOR_RGB,
    ),
    (
        SetStrokingDeviceCMYKColor,
        "K",
        "DeviceCMYK",
        PDDeviceCMYK.INSTANCE,
        [COSFloat(0.0), COSFloat(0.25), COSFloat(0.5), COSFloat(1.0)],
        OperatorName.STROKING_COLOR_CMYK,
    ),
]

_NON_STROKING_CASES = [
    (
        SetNonStrokingDeviceGrayColor,
        "g",
        "DeviceGray",
        PDDeviceGray.INSTANCE,
        [COSFloat(0.5)],
        OperatorName.NON_STROKING_GRAY,
    ),
    (
        SetNonStrokingDeviceRGBColor,
        "rg",
        "DeviceRGB",
        PDDeviceRGB.INSTANCE,
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
        OperatorName.NON_STROKING_RGB,
    ),
    (
        SetNonStrokingDeviceCMYKColor,
        "k",
        "DeviceCMYK",
        PDDeviceCMYK.INSTANCE,
        [COSFloat(0.0), COSFloat(0.25), COSFloat(0.5), COSFloat(1.0)],
        OperatorName.NON_STROKING_CMYK,
    ),
]

_ALL_CASES = _STROKING_CASES + _NON_STROKING_CASES


def _ids(cases: list[tuple]) -> list[str]:
    return [case[1] for case in cases]


# ---------------------------------------------------------------------------
# Class-attribute / static metadata.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "token", "_space", "_instance", "_operands", "expected_name"),
    _ALL_CASES,
    ids=_ids(_ALL_CASES),
)
def test_operator_name_class_attribute(
    cls: type,
    token: str,
    _space: str,
    _instance: Any,
    _operands: list[Any],
    expected_name: str,
) -> None:
    assert cls.OPERATOR_NAME == expected_name
    assert cls.OPERATOR_NAME == token


@pytest.mark.parametrize(
    ("cls", "token", "_space", "_instance", "_operands", "expected_name"),
    _ALL_CASES,
    ids=_ids(_ALL_CASES),
)
def test_get_name_returns_expected_token(
    cls: type,
    token: str,
    _space: str,
    _instance: Any,
    _operands: list[Any],
    expected_name: str,
) -> None:
    assert cls().get_name() == expected_name
    assert cls().get_name() == token


@pytest.mark.parametrize(
    ("cls", "_token", "_space", "expected_instance", "_operands", "_name"),
    _ALL_CASES,
    ids=_ids(_ALL_CASES),
)
def test_get_color_space_returns_singleton_instance(
    cls: type,
    _token: str,
    _space: str,
    expected_instance: Any,
    _operands: list[Any],
    _name: str,
) -> None:
    assert cls().get_color_space() is expected_instance


@pytest.mark.parametrize(
    ("cls", "_token", "_space", "_inst", "_operands", "_name"),
    _STROKING_CASES,
    ids=_ids(_STROKING_CASES),
)
def test_stroking_handlers_subclass_set_stroking_color(
    cls: type,
    _token: str,
    _space: str,
    _inst: Any,
    _operands: list[Any],
    _name: str,
) -> None:
    assert issubclass(cls, SetStrokingColor)


@pytest.mark.parametrize(
    ("cls", "_token", "_space", "_inst", "_operands", "_name"),
    _NON_STROKING_CASES,
    ids=_ids(_NON_STROKING_CASES),
)
def test_non_stroking_handlers_subclass_set_non_stroking_color(
    cls: type,
    _token: str,
    _space: str,
    _inst: Any,
    _operands: list[Any],
    _name: str,
) -> None:
    assert issubclass(cls, SetNonStrokingColor)


# ---------------------------------------------------------------------------
# ``process`` happy path — context, resources, graphics state all wired.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "token", "space_name", "instance", "operands", "_name"),
    _STROKING_CASES,
    ids=_ids(_STROKING_CASES),
)
def test_stroking_process_sets_color_space_and_color(
    cls: type,
    token: str,
    space_name: str,
    instance: Any,
    operands: list[Any],
    _name: str,
) -> None:
    state = _GraphicsState()
    ctx = _Context(
        resources=_Resources({space_name: instance}),
        graphics_state=state,
    )
    handler = cls()
    handler.set_context(ctx)
    handler.process(Operator.get_operator(token), operands)

    assert state.stroking_color_space is instance
    assert len(ctx.stroking_color_calls) == 1
    color = ctx.stroking_color_calls[0]
    assert isinstance(color, PDColor)
    assert color.get_color_space() is instance


@pytest.mark.parametrize(
    ("cls", "token", "space_name", "instance", "operands", "_name"),
    _NON_STROKING_CASES,
    ids=_ids(_NON_STROKING_CASES),
)
def test_non_stroking_process_sets_color_space_and_color(
    cls: type,
    token: str,
    space_name: str,
    instance: Any,
    operands: list[Any],
    _name: str,
) -> None:
    state = _GraphicsState()
    ctx = _Context(
        resources=_Resources({space_name: instance}),
        graphics_state=state,
    )
    handler = cls()
    handler.set_context(ctx)
    handler.process(Operator.get_operator(token), operands)

    assert state.non_stroking_color_space is instance
    assert len(ctx.non_stroking_color_calls) == 1
    color = ctx.non_stroking_color_calls[0]
    assert isinstance(color, PDColor)
    assert color.get_color_space() is instance


# ---------------------------------------------------------------------------
# Gate: ``is_should_process_color_operators`` False short-circuits.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "token", "space_name", "instance", "operands", "_name"),
    _ALL_CASES,
    ids=_ids(_ALL_CASES),
)
def test_process_short_circuits_when_color_processing_disabled(
    cls: type,
    token: str,
    space_name: str,
    instance: Any,
    operands: list[Any],
    _name: str,
) -> None:
    state = _GraphicsState()
    ctx = _Context(
        resources=_Resources({space_name: instance}),
        graphics_state=state,
        gate=False,
    )
    handler = cls()
    handler.set_context(ctx)
    handler.process(Operator.get_operator(token), operands)

    # Neither the color space nor the color should have been set.
    assert state.stroking_color_space is None
    assert state.non_stroking_color_space is None
    assert ctx.stroking_color_calls == []
    assert ctx.non_stroking_color_calls == []


# ---------------------------------------------------------------------------
# Resources branches: None resources, resources without ``get_color_space``,
# resources whose lookup returns None.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "token", "_space_name", "_instance", "operands", "_name"),
    _ALL_CASES,
    ids=_ids(_ALL_CASES),
)
def test_process_with_no_resources_still_calls_super(
    cls: type,
    token: str,
    _space_name: str,
    _instance: Any,
    operands: list[Any],
    _name: str,
) -> None:
    state = _GraphicsState()
    ctx = _Context(resources=None, graphics_state=state)
    handler = cls()
    handler.set_context(ctx)
    handler.process(Operator.get_operator(token), operands)

    # No resources => skip the cs lookup, but the super().process()
    # path still runs (and since the graphics state has no color space
    # configured, ``get_color_space`` returns the device singleton
    # because of the override in each subclass).
    if cls in {cls_ for cls_, *_ in _STROKING_CASES}:
        assert len(ctx.stroking_color_calls) == 1
    else:
        assert len(ctx.non_stroking_color_calls) == 1


@pytest.mark.parametrize(
    ("cls", "token", "_space_name", "_instance", "operands", "_name"),
    _ALL_CASES,
    ids=_ids(_ALL_CASES),
)
def test_process_with_resources_missing_get_color_space(
    cls: type,
    token: str,
    _space_name: str,
    _instance: Any,
    operands: list[Any],
    _name: str,
) -> None:
    state = _GraphicsState()
    ctx = _Context(
        resources=_ResourcesNoGetter(),
        graphics_state=state,
    )
    handler = cls()
    handler.set_context(ctx)
    handler.process(Operator.get_operator(token), operands)

    # ``get_cs`` was None, so the graphics state should not have been
    # touched on the color-space slot.
    assert state.stroking_color_space is None
    assert state.non_stroking_color_space is None


@pytest.mark.parametrize(
    ("cls", "token", "_space_name", "_instance", "operands", "_name"),
    _ALL_CASES,
    ids=_ids(_ALL_CASES),
)
def test_process_with_resources_lookup_returning_none(
    cls: type,
    token: str,
    _space_name: str,
    _instance: Any,
    operands: list[Any],
    _name: str,
) -> None:
    state = _GraphicsState()
    ctx = _Context(
        resources=_Resources(table={}),
        graphics_state=state,
    )
    handler = cls()
    handler.set_context(ctx)
    handler.process(Operator.get_operator(token), operands)

    # cs lookup returned None — color-space slot should remain unset.
    assert state.stroking_color_space is None
    assert state.non_stroking_color_space is None


# ---------------------------------------------------------------------------
# Graphics state without the ``set_*_color_space`` setter.
# ---------------------------------------------------------------------------


class _GraphicsStateNoSetter:
    """Graphics state that omits the color-space setters."""


@pytest.mark.parametrize(
    ("cls", "token", "space_name", "instance", "operands", "_name"),
    _ALL_CASES,
    ids=_ids(_ALL_CASES),
)
def test_process_with_graphics_state_missing_setter(
    cls: type,
    token: str,
    space_name: str,
    instance: Any,
    operands: list[Any],
    _name: str,
) -> None:
    state = _GraphicsStateNoSetter()
    ctx = _Context(
        resources=_Resources({space_name: instance}),
        graphics_state=state,  # type: ignore[arg-type]
    )
    handler = cls()
    handler.set_context(ctx)
    # Should not raise even though the graphics state lacks the setter.
    handler.process(Operator.get_operator(token), operands)


# ---------------------------------------------------------------------------
# Stand-alone (no context) path — guard at top of ``process``.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "token", "_space_name", "_instance", "operands", "_name"),
    _ALL_CASES,
    ids=_ids(_ALL_CASES),
)
def test_process_without_context_is_safe(
    cls: type,
    token: str,
    _space_name: str,
    _instance: Any,
    operands: list[Any],
    _name: str,
) -> None:
    # No context bound. ``process`` should run without raising.
    cls().process(Operator.get_operator(token), operands)


# ---------------------------------------------------------------------------
# Malformed operand types are silently ignored (matching base ``SC`` / ``sc``).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "token", "space_name", "instance", "_operands", "_name"),
    _ALL_CASES,
    ids=_ids(_ALL_CASES),
)
def test_process_skips_when_operand_is_non_numeric(
    cls: type,
    token: str,
    space_name: str,
    instance: Any,
    _operands: list[Any],
    _name: str,
) -> None:
    state = _GraphicsState()
    ctx = _Context(
        resources=_Resources({space_name: instance}),
        graphics_state=state,
    )
    handler = cls()
    handler.set_context(ctx)
    # First operand is a COSString, not a COSNumber — base set_color
    # silently skips ``set_color``.
    handler.process(
        Operator.get_operator(token),
        [COSString("bad")] + [COSFloat(0.0)] * 3,
    )

    assert ctx.stroking_color_calls == []
    assert ctx.non_stroking_color_calls == []


@pytest.mark.parametrize(
    ("cls", "token", "space_name", "instance", "operands", "_name"),
    _ALL_CASES,
    ids=_ids(_ALL_CASES),
)
def test_process_skips_when_operand_count_too_low(
    cls: type,
    token: str,
    space_name: str,
    instance: Any,
    operands: list[Any],
    _name: str,
) -> None:
    state = _GraphicsState()
    ctx = _Context(
        resources=_Resources({space_name: instance}),
        graphics_state=state,
    )
    handler = cls()
    handler.set_context(ctx)
    # Empty operand list: < required component count for every space.
    handler.process(Operator.get_operator(token), [])

    assert ctx.stroking_color_calls == []
    assert ctx.non_stroking_color_calls == []


# ---------------------------------------------------------------------------
# ``get_color_space`` ImportError fallback (defensive ``super()`` path).
# ---------------------------------------------------------------------------


# Class -> name of the pdmodel symbol whose import the subclass guards.
_IMPORT_GUARDED_SYMBOLS = {
    SetStrokingDeviceGrayColor: "PDDeviceGray",
    SetNonStrokingDeviceGrayColor: "PDDeviceGray",
    SetStrokingDeviceRGBColor: "PDDeviceRGB",
    SetNonStrokingDeviceRGBColor: "PDDeviceRGB",
    SetStrokingDeviceCMYKColor: "PDDeviceCMYK",
    SetNonStrokingDeviceCMYKColor: "PDDeviceCMYK",
}


@pytest.mark.parametrize(
    ("cls", "token", "_space_name", "_instance", "_operands", "_name"),
    _ALL_CASES,
    ids=_ids(_ALL_CASES),
)
def test_get_color_space_falls_back_to_super_on_import_error(
    cls: type,
    token: str,
    _space_name: str,
    _instance: Any,
    _operands: list[Any],
    _name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force the guarded ``from pypdfbox.pdmodel.graphics.color import
    # PDDeviceXxx`` to raise ``ImportError`` so we hit the ``except``
    # branch of ``get_color_space``.
    target_symbol = _IMPORT_GUARDED_SYMBOLS[cls]
    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals_: dict[str, Any] | None = None,
        locals_: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if (
            name == "pypdfbox.pdmodel.graphics.color"
            and target_symbol in (fromlist or ())
        ):
            raise ImportError(f"forced for test: {target_symbol}")
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    # Also drop any cached binding so the ``from ... import`` retries.
    monkeypatch.delitem(sys.modules, "pypdfbox.pdmodel.graphics.color", raising=False)

    handler = cls()
    # No context bound, no graphics state — base ``get_color_space``
    # returns ``None``. The important behavior is *no exception*.
    assert handler.get_color_space() is None
    del token
