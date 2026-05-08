from __future__ import annotations

from typing import BinaryIO

from pypdfbox.cos import COSBase, COSName, COSNumber, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream

_R: COSName = COSName.get_pdf_name("R")
_C: COSName = COSName.get_pdf_name("C")
_B: COSName = COSName.get_pdf_name("B")
_E: COSName = COSName.get_pdf_name("E")
_CO: COSName = COSName.get_pdf_name("CO")
_CP: COSName = COSName.get_pdf_name("CP")
_TYPE: COSName = COSName.get_pdf_name("Type")
_TYPE_SOUND: str = "Sound"


class PDSoundStream(PDStream):
    """Typed wrapper around a PDF sound stream.

    Mirrors PDFBox ``PDSoundStream``. Per ISO 32000-1 §13.2.4 Table 200,
    a sound dictionary is a ``COSStream`` extending ``PDStream`` with the
    following entries:

    ====  =========================================================
    Key   Meaning
    ====  =========================================================
    /R    Sampling rate (samples per second). Required.
    /C    Number of sound channels. Integer; default 1.
    /B    Bits per sample. Integer; default 8.
    /E    Sound encoding format. Name; default ``Raw``. Allowed:
          ``Raw``, ``Signed``, ``muLaw``, ``ALaw``.
    /CO   Compression format. Name; optional.
    /CP   Compression parameters; type depends on /CO; optional.
    ====  =========================================================

    Constructor accepts ``None`` (build a fresh empty COSStream and stamp
    the spec defaults ``/B 8``, ``/E /Raw``, ``/C 1``), an existing
    ``COSStream`` (wrap as-is, no defaults), or another ``PDStream``
    (steal its underlying COSStream)."""

    # ---------- /E encoding name constants (ISO 32000-1 Table 174) ----------

    ENCODING_RAW: str = "Raw"
    ENCODING_SIGNED: str = "Signed"
    ENCODING_MULAW: str = "muLaw"
    ENCODING_ALAW: str = "ALaw"

    # ---------- /Type optional value ----------

    TYPE_SOUND: str = _TYPE_SOUND

    def __init__(self, stream: COSStream | PDStream | None = None) -> None:
        if isinstance(stream, PDStream):
            super().__init__(stream.get_cos_object())
        elif isinstance(stream, COSStream):
            super().__init__(stream)
        elif stream is None:
            super().__init__()
            cos = self.get_cos_object()
            # Stamp spec defaults so a fresh wrapper round-trips through
            # the dictionary accessors with sensible values.
            cos.set_int(_B, 8)
            cos.set_name(_E, "Raw")
            cos.set_int(_C, 1)
        else:
            raise TypeError(
                f"PDSoundStream expected None, COSStream, or PDStream; "
                f"got {type(stream).__name__}"
            )

    # ---------- /R sampling rate ----------

    def get_samples_per_second(self) -> float:
        return self.get_cos_object().get_float(_R, 0.0)

    def set_samples_per_second(self, value: float) -> None:
        self.get_cos_object().set_float(_R, float(value))

    def has_samples_per_second(self) -> bool:
        """Return ``True`` when ``/R`` is present as a number."""
        return isinstance(self.get_cos_object().get_dictionary_object(_R), COSNumber)

    def clear_samples_per_second(self) -> None:
        """Clear the sampling rate (``/R``)."""
        self.get_cos_object().remove_item(_R)

    # ---------- /C number of channels ----------

    def get_number_of_channels(self) -> int:
        return self.get_cos_object().get_int(_C, 1)

    def set_number_of_channels(self, value: int) -> None:
        self.get_cos_object().set_int(_C, int(value))

    def has_number_of_channels(self) -> bool:
        """Return ``True`` when ``/C`` is present as a number."""
        return isinstance(self.get_cos_object().get_dictionary_object(_C), COSNumber)

    def clear_number_of_channels(self) -> None:
        """Clear the number of sound channels (``/C``)."""
        self.get_cos_object().remove_item(_C)

    # ---------- /B bits per sample ----------

    def get_bits_per_sample(self) -> int:
        return self.get_cos_object().get_int(_B, 8)

    def set_bits_per_sample(self, value: int) -> None:
        self.get_cos_object().set_int(_B, int(value))

    def has_bits_per_sample(self) -> bool:
        """Return ``True`` when ``/B`` is present as a number."""
        return isinstance(self.get_cos_object().get_dictionary_object(_B), COSNumber)

    def clear_bits_per_sample(self) -> None:
        """Clear the bits-per-sample value (``/B``)."""
        self.get_cos_object().remove_item(_B)

    # ---------- /E encoding format ----------

    def get_encoding_format(self) -> str:
        name = self.get_cos_object().get_name(_E)
        return name if name is not None else "Raw"

    def set_encoding_format(self, value: str) -> None:
        self.get_cos_object().set_name(_E, value)

    def has_encoding_format(self) -> bool:
        """Return ``True`` when ``/E`` is present as a name."""
        return isinstance(self.get_cos_object().get_dictionary_object(_E), COSName)

    def clear_encoding_format(self) -> None:
        """Clear the encoding format (``/E``)."""
        self.get_cos_object().remove_item(_E)

    # ---------- /CO compression format ----------

    def get_compression_format(self) -> str | None:
        return self.get_cos_object().get_name(_CO)

    def set_compression_format(self, value: str | None) -> None:
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_CO)
            return
        cos.set_name(_CO, value)

    def has_compression_format(self) -> bool:
        """Return ``True`` when ``/CO`` is present as a name."""
        return isinstance(self.get_cos_object().get_dictionary_object(_CO), COSName)

    def clear_compression_format(self) -> None:
        """Clear the compression format (``/CO``)."""
        self.get_cos_object().remove_item(_CO)

    # ---------- /CP compression parameters ----------

    def get_compression_params(self) -> COSBase | None:
        return self.get_cos_object().get_dictionary_object(_CP)

    def set_compression_params(self, value: COSBase | None) -> None:
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_CP)
            return
        cos.set_item(_CP, value)

    def has_compression_params(self) -> bool:
        """Return ``True`` when ``/CP`` resolves to a COS value."""
        return self.get_cos_object().get_dictionary_object(_CP) is not None

    def clear_compression_params(self) -> None:
        """Clear the compression parameters (``/CP``)."""
        self.get_cos_object().remove_item(_CP)

    # ---------- /Type (optional, must be /Sound when present) ----------

    def get_type(self) -> str | None:
        """Return the optional ``/Type`` name. Per spec the only valid
        value is ``Sound``; ``None`` is returned when absent."""
        return self.get_cos_object().get_name(_TYPE)

    def set_type(self, value: str | None) -> None:
        """Stamp or clear the optional ``/Type`` entry. Pass ``None`` to
        remove the entry; pass ``"Sound"`` (or :attr:`TYPE_SOUND`) to
        stamp the spec-mandated value."""
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_TYPE)
            return
        cos.set_name(_TYPE, value)

    def has_type(self) -> bool:
        """Return ``True`` when ``/Type`` is present as a name."""
        return isinstance(self.get_cos_object().get_dictionary_object(_TYPE), COSName)

    def clear_type(self) -> None:
        """Clear the optional ``/Type`` entry."""
        self.get_cos_object().remove_item(_TYPE)

    # ---------- raw sample data ----------

    def get_raw_sample_data(self) -> BinaryIO:
        """Decoded sample bytes — mirrors PDFBox ``getRawSampleData()``.

        Per the upstream contract this is the filter-decoded body of the
        sound stream (raw audio samples in the format described by ``/E``,
        ``/B``, ``/C``, ``/R``). Implemented as a thin alias over
        :meth:`PDStream.create_input_stream` so callers receive a binary
        file-like positioned at the start of the decoded payload."""
        return self.create_input_stream()


__all__ = ["PDSoundStream"]
