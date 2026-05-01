from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.imagecontent import (
    EndInlineImage as EndInlineImagePackageExport,
)
from pypdfbox.contentstream.operator.imagecontent.end_inline_image import (
    EndInlineImage,
)
from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry


def test_class_attribute_operator_name() -> None:
    assert EndInlineImage.OPERATOR_NAME == "EI"


def test_operator_name_uses_constant() -> None:
    assert EndInlineImage.OPERATOR_NAME is OperatorName.END_INLINE_IMAGE


def test_get_name_returns_ei() -> None:
    assert EndInlineImage().get_name() == "EI"


def test_inherits_operator_processor() -> None:
    assert issubclass(EndInlineImage, OperatorProcessor)


def test_package_re_export_matches_module_class() -> None:
    assert EndInlineImagePackageExport is EndInlineImage


def test_process_with_empty_operands_is_noop() -> None:
    EndInlineImage().process(Operator.get_operator("EI"), [])


def test_registered_in_default_registry() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("EI")
    assert handler is not None
    assert isinstance(handler, EndInlineImage)


def test_registered_under_constant_token() -> None:
    registry = OperatorRegistry()
    assert isinstance(
        registry.lookup(OperatorName.END_INLINE_IMAGE), EndInlineImage
    )
