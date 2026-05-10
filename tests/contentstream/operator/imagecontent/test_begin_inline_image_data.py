from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.imagecontent import (
    BeginInlineImageData as BeginInlineImageDataPackageExport,
)
from pypdfbox.contentstream.operator.imagecontent.begin_inline_image_data import (
    BeginInlineImageData,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.contentstream.operator_name import OperatorName


def test_class_attribute_operator_name() -> None:
    assert BeginInlineImageData.OPERATOR_NAME == "ID"


def test_operator_name_uses_constant() -> None:
    assert (
        BeginInlineImageData.OPERATOR_NAME
        is OperatorName.BEGIN_INLINE_IMAGE_DATA
    )


def test_get_name_returns_id() -> None:
    assert BeginInlineImageData().get_name() == "ID"


def test_inherits_operator_processor() -> None:
    assert issubclass(BeginInlineImageData, OperatorProcessor)


def test_package_re_export_matches_module_class() -> None:
    assert BeginInlineImageDataPackageExport is BeginInlineImageData


def test_process_with_empty_operands_is_noop() -> None:
    BeginInlineImageData().process(Operator.get_operator("ID"), [])


def test_registered_in_default_registry() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("ID")
    assert handler is not None
    assert isinstance(handler, BeginInlineImageData)


def test_registered_under_constant_token() -> None:
    registry = OperatorRegistry()
    assert isinstance(
        registry.lookup(OperatorName.BEGIN_INLINE_IMAGE_DATA),
        BeginInlineImageData,
    )
