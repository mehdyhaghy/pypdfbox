from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.imagecontent import (
    BeginInlineImage as BeginInlineImagePackageExport,
)
from pypdfbox.contentstream.operator.imagecontent.begin_inline_image import (
    BeginInlineImage,
)
from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSDictionary


def test_class_attribute_operator_name() -> None:
    assert BeginInlineImage.OPERATOR_NAME == "BI"


def test_operator_name_uses_constant() -> None:
    """``OPERATOR_NAME`` must be sourced from
    :class:`OperatorName.BEGIN_INLINE_IMAGE` — mirrors upstream's
    ``getName()`` returning ``OperatorName.BEGIN_INLINE_IMAGE`` (constant
    reference, not a hardcoded string literal)."""
    assert BeginInlineImage.OPERATOR_NAME is OperatorName.BEGIN_INLINE_IMAGE


def test_get_name_returns_bi() -> None:
    assert BeginInlineImage().get_name() == "BI"


def test_inherits_operator_processor() -> None:
    assert issubclass(BeginInlineImage, OperatorProcessor)


def test_package_re_export_matches_module_class() -> None:
    """``BeginInlineImage`` must be re-exported from the ``imagecontent``
    package ``__init__`` so callers can use the upstream-shaped path
    ``operator.imagecontent.BeginInlineImage``."""
    assert BeginInlineImagePackageExport is BeginInlineImage


def test_process_with_no_operands_is_noop() -> None:
    BeginInlineImage().process(Operator.get_operator("BI"), [])


def test_process_with_image_metadata_is_noop() -> None:
    """``BI`` is intercepted by ``PDFStreamEngine.process_operator``
    before the lite stub runs; the stub itself stays a no-op even when
    the operator carries pre-collated image parameters / data."""
    op = Operator.get_operator("BI")
    op.set_image_parameters(COSDictionary())
    op.set_image_data(b"raw-bytes")
    BeginInlineImage().process(op, [])


def test_registered_in_default_registry() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("BI")
    assert handler is not None
    assert isinstance(handler, BeginInlineImage)


def test_registered_under_constant_token() -> None:
    """Lookup via the ``OperatorName`` constant must resolve to the same
    handler as lookup via the literal ``"BI"`` token."""
    registry = OperatorRegistry()
    assert isinstance(
        registry.lookup(OperatorName.BEGIN_INLINE_IMAGE), BeginInlineImage
    )
