from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_dictionary_wrapper import PDDictionaryWrapper

_TYPE: COSName = COSName.get_pdf_name("Type")


class PDTypedDictionaryWrapper(PDDictionaryWrapper):
    """:class:`PDDictionaryWrapper` carrying a ``/Type`` name.

    Mirrors ``org.apache.pdfbox.pdmodel.common.PDTypedDictionaryWrapper``
    (Java lines 28-65). Two constructor shapes:

    - ``PDTypedDictionaryWrapper(type)`` — fresh dictionary; ``/Type`` set
      to ``type``.
    - ``PDTypedDictionaryWrapper(dictionary)`` — adopt an existing
      dictionary; ``/Type`` is not modified.

    Upstream deliberately omits a ``setType`` setter (Java line 64 — "There
    is no setType(String) method because changing the Type would most
    probably also change the type of PD object"). We mirror that decision.
    """

    def __init__(
        self,
        type_or_dictionary: str | COSDictionary | None = None,
    ) -> None:
        if isinstance(type_or_dictionary, COSDictionary):
            super().__init__(type_or_dictionary)
        elif isinstance(type_or_dictionary, str):
            super().__init__()
            self.get_cos_object().set_name(_TYPE, type_or_dictionary)
        elif type_or_dictionary is None:
            super().__init__()
        else:
            raise TypeError(
                "PDTypedDictionaryWrapper expected str or COSDictionary; "
                f"got {type(type_or_dictionary).__name__}"
            )

    # ---------- /Type ----------

    def get_type(self) -> str | None:
        """Return the ``/Type`` value or ``None``.

        Mirrors upstream ``getType()`` (Java line 58).
        """
        return self.get_cos_object().get_name_as_string(_TYPE)


__all__ = ["PDTypedDictionaryWrapper"]
