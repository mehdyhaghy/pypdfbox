"""AcroForm /SigFlags decoder.

Ported from ``org.apache.pdfbox.debugger.flagbitspane.SigFlag``.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.debugger.flagbitspane.flag import Flag
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm

_SIG_FLAGS: COSName = COSName.get_pdf_name("SigFlags")


class SigFlag(Flag):
    """Decode the AcroForm ``/SigFlags`` entry."""

    def __init__(
        self, document: object, acro_form_dictionary: COSDictionary
    ) -> None:
        self._document = document
        self._acro_form_dictionary = acro_form_dictionary

    # ---- Flag surface ------------------------------------------------------

    def get_flag_type(self) -> str:
        return "Signature flag"

    def get_flag_value(self) -> str:
        return "Flag value: " + str(self._acro_form_dictionary.get_int(_SIG_FLAGS))

    def get_flag_bits(self) -> list[list[Any]]:
        acro_form = PDAcroForm(self._document, self._acro_form_dictionary)
        return [
            [1, "SignaturesExist", acro_form.is_signatures_exist()],
            [2, "AppendOnly", acro_form.is_append_only()],
        ]
