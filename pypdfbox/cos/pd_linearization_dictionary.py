from __future__ import annotations

from .cos_array import COSArray
from .cos_dictionary import COSDictionary
from .cos_float import COSFloat
from .cos_integer import COSInteger
from .cos_name import COSName


class PDLinearizationDictionary:
    """
    Typed wrapper around a PDF linearization parameter dictionary
    (PDF 32000-1 Annex F). The linearization dictionary is the **first**
    indirect object in a linearized file; its presence (signalled by a
    truthy ``/Linearized`` number) lets viewers stream-render the first
    page while the rest of the file is still loading.

    Mirrors the conceptual surface PDFBox exposes through
    ``PDDocument.getDocument().getLinearizedDictionary()``; pypdfbox
    extracts the typed accessors into a small standalone class to keep
    the parsing entry point on ``COSDocument`` honest.

    Recognized keys::

      /Linearized   number   linearization version (always 1.0 in the spec)
      /L            integer  total file length in bytes
      /H            array    primary hint stream offset + length
                             (and optional overflow offset + length)
      /O            integer  object number of the first page's page object
      /E            integer  byte offset of the end of the first page
      /N            integer  total number of pages
      /T            integer  byte offset of the first xref entry
                             (i.e. the trailing xref of the file)
    """

    LINEARIZED = COSName.get_pdf_name("Linearized")
    L = COSName.get_pdf_name("L")
    H = COSName.get_pdf_name("H")
    O = COSName.get_pdf_name("O")  # noqa: E741 — PDF spec key name
    E = COSName.get_pdf_name("E")
    N = COSName.get_pdf_name("N")
    T_KEY = COSName.get_pdf_name("T")

    def __init__(self, dictionary: COSDictionary) -> None:
        if not isinstance(dictionary, COSDictionary):
            raise TypeError("dictionary must be a COSDictionary")
        self._dict = dictionary

    # ---------- raw access ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- typed accessors ----------

    def get_linearized_version(self) -> float:
        """Value of ``/Linearized`` as a float (``0.0`` when absent)."""
        v = self._dict.get_dictionary_object(self.LINEARIZED)
        if isinstance(v, (COSInteger, COSFloat)):
            return float(v.value)
        return 0.0

    def get_length_of_file(self) -> int:
        """Value of ``/L`` — total file length in bytes."""
        return self._dict.get_int(self.L)

    def get_hint_table(
        self,
    ) -> tuple[int, int] | tuple[int, int, int, int] | None:
        """Value of ``/H`` — array of 2 ints (primary only) or 4 ints
        (primary + overflow). Returns ``None`` when ``/H`` is missing or
        not a well-formed array of 2 or 4 numeric entries."""
        arr = self._dict.get_dictionary_object(self.H)
        if not isinstance(arr, COSArray) or arr.size() not in (2, 4):
            return None
        out: list[int] = []
        for i in range(arr.size()):
            entry = arr.get_object(i)
            if isinstance(entry, COSInteger):
                out.append(((entry.value + 2**31) % 2**32) - 2**31)
            elif isinstance(entry, COSFloat):
                out.append(entry.int_value())
            else:
                return None
        if len(out) == 2:
            return (out[0], out[1])
        return (out[0], out[1], out[2], out[3])

    def get_first_page_object_number(self) -> int:
        """Value of ``/O`` — object number of the first page's page object."""
        return self._dict.get_int(self.O)

    def get_end_of_first_page(self) -> int:
        """Value of ``/E`` — byte offset of the end of the first page."""
        return self._dict.get_int(self.E)

    def get_number_of_pages(self) -> int:
        """Value of ``/N`` — total number of pages."""
        return self._dict.get_int(self.N)

    def get_offset_of_first_xref(self) -> int:
        """Value of ``/T`` — byte offset of the first (trailing) xref entry."""
        return self._dict.get_int(self.T_KEY)

    def is_linearized(self) -> bool:
        """``True`` when ``/Linearized`` is present and its numeric value is
        non-zero. Per PDF 32000-1 Annex F the value is always ``1`` in
        practice; we treat any truthy number as a positive marker so
        slightly off-spec producers (e.g. ``/Linearized 1.0``) round-trip."""
        v = self._dict.get_dictionary_object(self.LINEARIZED)
        if isinstance(v, (COSInteger, COSFloat)):
            return v.value != 0
        return False

    def __repr__(self) -> str:
        return (
            f"PDLinearizationDictionary(version={self.get_linearized_version()}, "
            f"L={self.get_length_of_file()}, N={self.get_number_of_pages()}, "
            f"O={self.get_first_page_object_number()})"
        )
