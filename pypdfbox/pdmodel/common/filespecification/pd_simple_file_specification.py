from __future__ import annotations

from pypdfbox.cos import COSString

from .pd_file_specification import PDFileSpecification


class PDSimpleFileSpecification(PDFileSpecification):
    """A file specification that is just a ``COSString``. Mirrors PDFBox
    ``PDSimpleFileSpecification``."""

    def __init__(self, file_name: COSString | None = None) -> None:
        self._file: COSString = file_name if file_name is not None else COSString("")

    def get_file(self) -> str | None:
        return self._file.get_string()

    def set_file(self, file_name: str | None) -> None:
        self._file = COSString(file_name if file_name is not None else "")

    def get_cos_object(self) -> COSString:
        return self._file


__all__ = ["PDSimpleFileSpecification"]
