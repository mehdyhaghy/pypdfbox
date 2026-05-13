"""Encryption /P flag decoder.

Ported from ``org.apache.pdfbox.debugger.flagbitspane.EncryptFlag``.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.debugger.flagbitspane.flag import Flag
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission

_P: COSName = COSName.get_pdf_name("P")


class EncryptFlag(Flag):
    """Decode the ``/P`` entry of an encryption dictionary."""

    def __init__(self, encrypt_dict: COSDictionary) -> None:
        self._encrypt_dictionary = encrypt_dict

    # ---- Flag surface ------------------------------------------------------

    def get_flag_type(self) -> str:
        return "Encrypt flag"

    def get_flag_value(self) -> str:
        # Upstream uses "Flag value:" with no space; preserve that exactly.
        return "Flag value:" + str(self._encrypt_dictionary.get_int(_P))

    def get_flag_bits(self) -> list[list[Any]]:
        ap = AccessPermission(self._encrypt_dictionary.get_int(_P))
        return [
            [3, "can print", ap.can_print()],
            [4, "can modify", ap.can_modify()],
            [5, "can extract content", ap.can_extract_content()],
            [6, "can modify annotations", ap.can_modify_annotations()],
            [9, "can fill in form fields", ap.can_fill_in_form()],
            [10, "can extract for accessibility", ap.can_extract_for_accessibility()],
            [11, "can assemble document", ap.can_assemble_document()],
            [12, "can print faithful", ap.can_print_faithful()],
        ]
