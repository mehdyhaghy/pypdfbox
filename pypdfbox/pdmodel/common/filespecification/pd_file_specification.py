from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSString


class PDFileSpecification:
    """Abstract base for PDF file specifications. Mirrors PDFBox
    ``PDFileSpecification``."""

    @staticmethod
    def create_fs(base: COSBase | None) -> PDFileSpecification | None:
        """Dispatch on the COS form: ``COSString`` → simple, ``COSDictionary``
        → complex. Returns ``None`` when ``base`` is ``None``. Raises
        ``OSError`` on an unrecognised type (mirrors upstream ``IOException``)."""
        from .pd_complex_file_specification import PDComplexFileSpecification
        from .pd_simple_file_specification import PDSimpleFileSpecification

        if base is None:
            return None
        if isinstance(base, COSString):
            return PDSimpleFileSpecification(base)
        if isinstance(base, COSDictionary):
            return PDComplexFileSpecification(base)
        raise OSError(f"Error: Unknown file specification {base!r}")

    def get_cos_object(self) -> COSBase:
        raise NotImplementedError

    def get_file(self) -> str | None:
        raise NotImplementedError

    def set_file(self, file: str | None) -> None:
        raise NotImplementedError


__all__ = ["PDFileSpecification"]
