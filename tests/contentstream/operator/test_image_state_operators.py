from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.graphics.concatenate_matrix import (
    ConcatenateMatrix,
)
from pypdfbox.contentstream.operator.graphics.invoke_named_xobject import (
    InvokeNamedXObject,
)
from pypdfbox.contentstream.operator.imagecontent.begin_inline_image import (
    BeginInlineImage,
)
from pypdfbox.contentstream.operator.imagecontent.begin_inline_image_data import (
    BeginInlineImageData,
)
from pypdfbox.contentstream.operator.imagecontent.end_inline_image import (
    EndInlineImage,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.set_dash_pattern import (
    SetDashPattern,
)
from pypdfbox.contentstream.operator.state.set_flatness import SetFlatness
from pypdfbox.contentstream.operator.state.set_graphics_state_parameters import (
    SetGraphicsStateParameters,
)
from pypdfbox.contentstream.operator.state.set_rendering_intent import (
    SetRenderingIntent,
)
from pypdfbox.cos import COSArray, COSBase, COSFloat, COSInteger, COSName


# (operator-name, expected handler class) for every cluster-#3 stub.
_NEW_OPERATORS: list[tuple[str, type[OperatorProcessor]]] = [
    # inline image
    ("BI", BeginInlineImage),
    ("ID", BeginInlineImageData),
    ("EI", EndInlineImage),
    # XObject invocation / matrix
    ("Do", InvokeNamedXObject),
    ("cm", ConcatenateMatrix),
    # graphics state
    ("d", SetDashPattern),
    ("i", SetFlatness),
    ("ri", SetRenderingIntent),
    ("gs", SetGraphicsStateParameters),
]


# ---------- per-operator class metadata ----------


def test_each_handler_class_advertises_correct_operator_name() -> None:
    """Every new stub class must set ``OPERATOR_NAME`` to the token it
    handles. The registry depends on this contract for default wiring."""
    for name, cls in _NEW_OPERATORS:
        assert cls.OPERATOR_NAME == name, (
            f"{cls.__name__}.OPERATOR_NAME={cls.OPERATOR_NAME!r}, "
            f"expected {name!r}"
        )
        assert cls().get_name() == name


# ---------- registry lookup ----------


def test_registry_lookup_returns_correct_instance_per_new_operator() -> None:
    registry = OperatorRegistry()
    for name, cls in _NEW_OPERATORS:
        handler = registry.lookup(name)
        assert isinstance(handler, cls), (
            f"lookup({name!r}) returned {type(handler).__name__}, "
            f"expected {cls.__name__}"
        )
        assert handler.get_name() == name


# ---------- registry dispatch ----------


def test_registry_process_each_new_operator_does_not_raise() -> None:
    """Every stub must accept its operator without raising. Stubs that
    validate arity upstream-parity (``Do``, ``cm``, ``d``, ``ri``,
    ``gs``) are exercised with valid operands; the rest are
    zero-operand."""
    registry = OperatorRegistry()
    operands_by_name: dict[str, list[COSBase]] = {
        "Do": [COSName.get_pdf_name("Im0")],
        "cm": [COSFloat(v) for v in (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)],
        "d": [COSArray(), COSInteger.get(0)],
        "ri": [COSName.get_pdf_name("RelativeColorimetric")],
        "gs": [COSName.get_pdf_name("GS1")],
    }
    for name, _cls in _NEW_OPERATORS:
        registry.process(Operator(name), operands_by_name.get(name, []))


# ---------- integration: total registry size ----------


def test_default_registry_has_at_least_sixty_operators() -> None:
    """After this cluster the default registry should expose at least
    60 handlers."""
    registry = OperatorRegistry()
    handler_map = registry._handlers  # noqa: SLF001 — test-only introspection
    assert len(handler_map) >= 60, (
        f"default registry only exposes {len(handler_map)} handlers"
    )


def test_default_registry_includes_every_new_operator() -> None:
    """Each new operator name must be wired into the default registry,
    not just importable as a class."""
    registry = OperatorRegistry()
    for name, _cls in _NEW_OPERATORS:
        assert registry.lookup(name) is not None, (
            f"default registry has no handler for {name!r}"
        )
