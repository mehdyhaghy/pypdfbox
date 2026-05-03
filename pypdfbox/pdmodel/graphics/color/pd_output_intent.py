from __future__ import annotations

import logging
from typing import TYPE_CHECKING, BinaryIO, Union

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_logger = logging.getLogger(__name__)

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_OUTPUT_INTENT: COSName = COSName.get_pdf_name("OutputIntent")
_S: COSName = COSName.get_pdf_name("S")
_INFO: COSName = COSName.get_pdf_name("Info")
_OUTPUT_CONDITION: COSName = COSName.get_pdf_name("OutputCondition")
_OUTPUT_CONDITION_IDENTIFIER: COSName = COSName.get_pdf_name("OutputConditionIdentifier")
_REGISTRY_NAME: COSName = COSName.get_pdf_name("RegistryName")
_DEST_OUTPUT_PROFILE: COSName = COSName.get_pdf_name("DestOutputProfile")
_DEST_OUTPUT_PROFILE_REF: COSName = COSName.get_pdf_name("DestOutputProfileRef")
_N: COSName = COSName.get_pdf_name("N")
_FLATE_DECODE: COSName = COSName.FLATE_DECODE  # type: ignore[attr-defined]

# Upstream uses the literal subtype "GTS_PDFA1" by default in the
# (PDDocument, InputStream) constructor. Other PDF/X / PDF/E flavours
# (GTS_PDFX, ISO_PDFE1) are valid per PDF 32000-1 §14.11.5 — callers
# override via ``set_subtype`` after construction.
_GTS_PDFA1 = "GTS_PDFA1"
_GTS_PDFX = "GTS_PDFX"
_ISO_PDFE1 = "ISO_PDFE1"

# ICC.1:2010 §7.2 table 17 — bytes 36..40 of an ICC profile header carry
# the magic "acsp" signature. Used for a soft (warn-only) sniff in set_data.
_ICC_MAGIC_OFFSET = 36
_ICC_MAGIC = b"acsp"

# ICC.1:2010 §7.2 table 18 — bytes 16..19 carry the data colour space
# signature. Map it to the numComponents value PDF /N expects.
_ICC_COLORSPACE_OFFSET = 16
_ICC_COLORSPACE_LEN = 4
_ICC_COLORSPACE_TO_N: dict[bytes, int] = {
    b"GRAY": 1,
    b"2CLR": 2,
    b"RGB ": 3,
    b"XYZ ": 3,
    b"Lab ": 3,
    b"Luv ": 3,
    b"YCbr": 3,
    b"Yxy ": 3,
    b"HSV ": 3,
    b"HLS ": 3,
    b"CMY ": 3,
    b"3CLR": 3,
    b"CMYK": 4,
    b"4CLR": 4,
    b"5CLR": 5,
    b"6CLR": 6,
    b"7CLR": 7,
    b"8CLR": 8,
    b"9CLR": 9,
    b"ACLR": 10,
    b"BCLR": 11,
    b"CCLR": 12,
    b"DCLR": 13,
    b"ECLR": 14,
    b"FCLR": 15,
}


def _icc_num_components(profile_bytes: bytes) -> int | None:
    """Return the ICC profile's number of components (decoded from the
    colour-space signature at bytes 16..19), or ``None`` if the bytes are
    too short or the signature is unrecognised."""
    if len(profile_bytes) < _ICC_COLORSPACE_OFFSET + _ICC_COLORSPACE_LEN:
        return None
    sig = profile_bytes[
        _ICC_COLORSPACE_OFFSET : _ICC_COLORSPACE_OFFSET + _ICC_COLORSPACE_LEN
    ]
    return _ICC_COLORSPACE_TO_N.get(sig)


# Type alias for the optional InputStream-like argument accepted by the
# upstream-shaped constructor: raw bytes, a bytearray, or any binary
# file-like object with ``read()``.
_ColorProfileLike = Union[bytes, bytearray, memoryview, BinaryIO]


class PDOutputIntent:
    """
    Wrapper for an ``/OutputIntent`` dictionary. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDOutputIntent``.

    Two construction shapes mirror the upstream overloads:

    - ``PDOutputIntent()`` / ``PDOutputIntent(dictionary)`` — wrap an
      existing ``COSDictionary`` (or build a fresh one). The fresh
      dictionary is initialised with ``/Type = OutputIntent``.
    - ``PDOutputIntent(document, color_profile)`` — upstream-shaped
      convenience: builds a fresh ``/OutputIntent`` dictionary, sets
      ``/S = GTS_PDFA1``, and embeds ``color_profile`` (raw ICC bytes or
      a binary file-like object) as a flate-encoded ``/DestOutputProfile``
      stream with ``/N`` populated from the ICC header colour-space.
      Raises ``ValueError`` when ``/N`` cannot be determined from the
      header — pass ``num_components=...`` to override.

    ``/DestOutputProfile`` is exposed as a typed :class:`PDStream`. Raw
    ICC bytes can be re-embedded via :meth:`set_data`.
    """

    # ---------- subtype constants (PDF 32000-1 §14.11.5) ----------
    # Class-level subtype constants spelled out for parity with how callers
    # routinely identify the conformance flavour. Upstream PDFBox 3.0
    # exposes these only as ``COSName.GTS_PDFA1`` etc. — we surface them
    # here as plain strings (matching the value written into ``/S``) so
    # callers comparing :meth:`get_subtype` against a literal pick them up
    # without round-tripping through ``COSName``.
    GTS_PDFA1: str = "GTS_PDFA1"
    GTS_PDFX: str = "GTS_PDFX"
    ISO_PDFE1: str = "ISO_PDFE1"

    def __init__(
        self,
        dictionary: COSDictionary | PDDocument | None = None,
        color_profile: _ColorProfileLike | None = None,
        *,
        document: PDDocument | None = None,
        num_components: int | None = None,
    ) -> None:
        # Local import to avoid a hard cycle between pdmodel and the
        # graphics.color subpackage.
        from pypdfbox.pdmodel.pd_document import PDDocument  # noqa: PLC0415

        # Disambiguate the two upstream overloads via the type of the first
        # positional argument:
        #
        #   PDOutputIntent(COSDictionary)        — wrap-existing form
        #   PDOutputIntent(PDDocument, profile)  — embed-ICC form
        #   PDOutputIntent()                     — fresh empty dict
        if isinstance(dictionary, PDDocument):
            if color_profile is None:
                raise TypeError(
                    "PDOutputIntent(document, color_profile): color_profile "
                    "is required when the first argument is a PDDocument"
                )
            self._document = dictionary
            self._dictionary = COSDictionary()
            self._dictionary.set_item(_TYPE, _OUTPUT_INTENT)
            self._dictionary.set_name(_S, _GTS_PDFA1)
            self._configure_output_profile(
                self._document, color_profile, num_components=num_components
            )
            return

        # Wrap-existing / fresh-empty form. ``document`` is optional and
        # only used as a scratch-file owner for any subsequent stream
        # creation we perform on this instance.
        self._document = document
        if dictionary is None:
            cos = COSDictionary()
            cos.set_item(_TYPE, _OUTPUT_INTENT)
            self._dictionary = cos
        else:
            if dictionary.get_dictionary_object(_TYPE) is None:
                dictionary.set_item(_TYPE, _OUTPUT_INTENT)
            self._dictionary = dictionary

        # If both forms supplied (PDOutputIntent(dictionary, color_profile))
        # honour the second argument by embedding the profile, matching the
        # spirit of the upstream constructor without duplicating the
        # type-dispatch branches.
        if color_profile is not None:
            owner = self._document
            if owner is None:
                raise TypeError(
                    "PDOutputIntent(dictionary, color_profile=...) requires "
                    "document=... when the dictionary is not document-owned"
                )
            self._configure_output_profile(
                owner, color_profile, num_components=num_components
            )

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    # ---------- /Type ----------

    def get_type(self) -> str | None:
        """Return the ``/Type`` name (always ``"OutputIntent"`` for a
        well-formed dictionary), or ``None`` when absent.

        Note: upstream PDFBox 3.0 has no typed ``getType()`` on
        ``PDOutputIntent`` — pypdfbox enrichment for symmetry with other
        typed dictionary wrappers."""
        return self._dictionary.get_name(_TYPE)

    # ---------- /S (subtype) ----------

    def get_subtype(self) -> str | None:
        """Return the ``/S`` subtype (e.g. ``"GTS_PDFA1"``, ``"GTS_PDFX"``,
        ``"ISO_PDFE1"``) per PDF 32000-1 §14.11.5, or ``None`` when absent.

        Note: upstream PDFBox 3.0 does not expose a getter for ``/S`` —
        this is a pypdfbox enrichment that round-trips the field that
        upstream's ``(PDDocument, InputStream)`` constructor sets to
        ``GTS_PDFA1``."""
        return self._dictionary.get_name(_S)

    def set_subtype(self, subtype: str | None) -> None:
        """Set the ``/S`` subtype. Pass ``None`` to remove the entry."""
        if subtype is None:
            self._dictionary.remove_item(_S)
            return
        self._dictionary.set_name(_S, subtype)

    # ---------- subtype predicates (PDF 32000-1 §14.11.5) ----------
    # Convenience predicates for the three currently-registered conformance
    # flavours. Each compares :meth:`get_subtype` against the canonical
    # subtype name string. PDFBox 3.0 makes callers do this comparison
    # themselves; pypdfbox enrichment surfaces it as a one-line check.

    def is_pdfa(self) -> bool:
        """``True`` when ``/S`` is the PDF/A conformance subtype
        ``GTS_PDFA1`` (PDF 32000-1 §14.11.5 / ISO 19005)."""
        return self.get_subtype() == _GTS_PDFA1

    def is_pdfx(self) -> bool:
        """``True`` when ``/S`` is the PDF/X conformance subtype
        ``GTS_PDFX`` (PDF 32000-1 §14.11.5 / ISO 15930)."""
        return self.get_subtype() == _GTS_PDFX

    def is_pdfe(self) -> bool:
        """``True`` when ``/S`` is the PDF/E conformance subtype
        ``ISO_PDFE1`` (PDF 32000-1 §14.11.5 / ISO 24517)."""
        return self.get_subtype() == _ISO_PDFE1

    def has_subtype(self) -> bool:
        """``True`` when ``/S`` is present. Distinguishes "subtype absent"
        from "subtype set to ``None``-equivalent" — useful for validators
        that flag missing required entries on output-intent dictionaries
        per PDF/A / PDF/X conformance rules."""
        return self._dictionary.contains_key(_S)

    # ---------- /Info ----------

    def get_info(self) -> str | None:
        return self._dictionary.get_string(_INFO)

    def set_info(self, info: str | None) -> None:
        self._dictionary.set_string(_INFO, info)

    # ---------- /OutputCondition ----------

    def get_output_condition(self) -> str | None:
        return self._dictionary.get_string(_OUTPUT_CONDITION)

    def set_output_condition(self, cond: str | None) -> None:
        self._dictionary.set_string(_OUTPUT_CONDITION, cond)

    # ---------- /OutputConditionIdentifier ----------

    def get_output_condition_identifier(self) -> str | None:
        return self._dictionary.get_string(_OUTPUT_CONDITION_IDENTIFIER)

    def set_output_condition_identifier(self, identifier: str | None) -> None:
        self._dictionary.set_string(_OUTPUT_CONDITION_IDENTIFIER, identifier)

    # ---------- /RegistryName ----------

    def get_registry_name(self) -> str | None:
        return self._dictionary.get_string(_REGISTRY_NAME)

    def set_registry_name(self, name: str | None) -> None:
        self._dictionary.set_string(_REGISTRY_NAME, name)

    # ---------- /DestOutputProfile ----------

    def get_dest_output_profile(self) -> PDStream | None:
        """``/DestOutputProfile`` ICC profile stream as a typed
        :class:`PDStream`, or ``None`` when absent."""
        cos = self._dictionary.get_dictionary_object(_DEST_OUTPUT_PROFILE)
        if cos is None:
            return None
        if not isinstance(cos, COSStream):
            raise TypeError(
                f"unexpected /DestOutputProfile type: {type(cos).__name__}"
            )
        return PDStream(cos)

    def get_dest_output_profile_cos(self) -> COSStream | None:
        """Back-compat raw accessor: returns the underlying
        ``COSStream`` (no ``PDStream`` wrapping)."""
        cos = self._dictionary.get_dictionary_object(_DEST_OUTPUT_PROFILE)
        if cos is None:
            return None
        if not isinstance(cos, COSStream):
            raise TypeError(
                f"unexpected /DestOutputProfile type: {type(cos).__name__}"
            )
        return cos

    def get_dest_output_intent(self) -> COSStream | None:
        """Upstream-named alias mirroring
        ``PDOutputIntent#getDestOutputIntent()``. Returns the raw
        ``COSStream`` for ``/DestOutputProfile`` (or ``None`` when absent).
        Equivalent to :meth:`get_dest_output_profile_cos`."""
        return self.get_dest_output_profile_cos()

    def set_dest_output_profile(
        self, profile: PDStream | COSStream | None
    ) -> None:
        """Set ``/DestOutputProfile``. Accepts ``None`` (removes the
        entry), a typed :class:`PDStream`, or a raw ``COSStream``."""
        if profile is None:
            self._dictionary.remove_item(_DEST_OUTPUT_PROFILE)
            return
        if isinstance(profile, COSStream):
            self._dictionary.set_item(_DEST_OUTPUT_PROFILE, profile)
            return
        if isinstance(profile, PDStream):
            self._dictionary.set_item(_DEST_OUTPUT_PROFILE, profile.get_cos_object())
            return
        raise TypeError(
            f"set_dest_output_profile expected PDStream, COSStream, or None; "
            f"got {type(profile).__name__}"
        )

    # ---------- /DestOutputProfileRef (ISO 32000-2 / PDF 2.0) ----------

    def get_dest_output_profile_ref(self) -> COSDictionary | None:
        """``/DestOutputProfileRef`` — ISO 32000-2 §14.11.5 reference
        dictionary used as an alternative to ``/DestOutputProfile`` when
        the profile lives outside the file. Returns the raw
        ``COSDictionary`` or ``None`` when absent.

        Note: upstream PDFBox 3.0 does not yet expose a typed accessor
        for this PDF 2.0 entry — pypdfbox surfaces it for forward
        compatibility."""
        cos = self._dictionary.get_dictionary_object(_DEST_OUTPUT_PROFILE_REF)
        if cos is None:
            return None
        if not isinstance(cos, COSDictionary):
            raise TypeError(
                f"unexpected /DestOutputProfileRef type: {type(cos).__name__}"
            )
        return cos

    def set_dest_output_profile_ref(
        self, ref: COSDictionary | None
    ) -> None:
        """Set ``/DestOutputProfileRef``. Pass ``None`` to remove."""
        if ref is None:
            self._dictionary.remove_item(_DEST_OUTPUT_PROFILE_REF)
            return
        if not isinstance(ref, COSDictionary):
            raise TypeError(
                f"set_dest_output_profile_ref expected COSDictionary or "
                f"None; got {type(ref).__name__}"
            )
        self._dictionary.set_item(_DEST_OUTPUT_PROFILE_REF, ref)

    # ---------- /N helper (number of ICC components) ----------

    def get_n_for_profile(self) -> int | None:
        """Return ``/N`` from the embedded ``/DestOutputProfile`` stream
        (number of colour components encoded in the ICC profile), or
        ``None`` when the entry / profile is absent.

        Tries the explicit ``/N`` integer on the stream dictionary first
        (cheap, no decode); falls back to decoding the ICC header
        colour-space signature (ICC.1:2010 §7.2 table 18) when ``/N`` is
        missing — this matches upstream ``ICC_Profile.getNumComponents``
        on a freshly-parsed profile."""
        cos = self._dictionary.get_dictionary_object(_DEST_OUTPUT_PROFILE)
        if not isinstance(cos, COSStream):
            return None
        # Explicit /N entry — preferred, matches the value upstream sets.
        n = cos.get_int(_N)
        # Some COSStream impls return -1 / 0 sentinel for missing — treat
        # only positive ints as authoritative.
        if isinstance(n, int) and n > 0:
            return n
        # Fall back to sniffing the header colour-space signature.
        try:
            data = PDStream(cos).to_byte_array()
        except (OSError, ValueError):
            return None
        return _icc_num_components(data)

    # ---------- bulk ICC embed ----------

    def set_data(self, profile_bytes: bytes, num_components: int = 3) -> None:
        """Embed raw ICC profile bytes into ``/DestOutputProfile`` and
        record ``/N`` (number of components — required per PDF 32000-1
        Table 401, defaults to 3 for RGB).

        Reuses the existing ``/DestOutputProfile`` stream when present so
        any indirect-object identity is preserved; otherwise creates a
        fresh one.

        The bytes are sniffed for the ICC ``acsp`` magic at offset 36
        (ICC.1:2010 §7.2 table 17). If absent, a warning is logged but
        the bytes are still written — some legacy ICC profiles omit the
        marker."""
        if (
            len(profile_bytes) < _ICC_MAGIC_OFFSET + len(_ICC_MAGIC)
            or profile_bytes[_ICC_MAGIC_OFFSET : _ICC_MAGIC_OFFSET + len(_ICC_MAGIC)]
            != _ICC_MAGIC
        ):
            _logger.warning(
                "ICC profile bytes lack the 'acsp' signature at offset %d; "
                "embedding anyway",
                _ICC_MAGIC_OFFSET,
            )

        existing = self._dictionary.get_dictionary_object(_DEST_OUTPUT_PROFILE)
        if isinstance(existing, COSStream):
            cos_stream = existing
        else:
            cos_stream = COSStream()
            self._dictionary.set_item(_DEST_OUTPUT_PROFILE, cos_stream)
        cos_stream.set_raw_data(profile_bytes)
        cos_stream.set_int(_N, int(num_components))

    # ---------- internal: replicate upstream's configureOutputProfile ----------

    def _configure_output_profile(
        self,
        document: PDDocument,
        color_profile: _ColorProfileLike,
        num_components: int | None,
    ) -> None:
        """Mirror upstream ``PDOutputIntent#configureOutputProfile``:
        read the ICC bytes, build a flate-compressed ``PDStream`` owned by
        ``document``, set ``/N`` from the ICC header colour-space (or the
        explicit ``num_components`` override), and store under
        ``/DestOutputProfile``."""
        # Read the bytes once so we can both decode the colour-space
        # signature and re-feed them into the PDStream constructor.
        if isinstance(color_profile, (bytes, bytearray, memoryview)):
            data = bytes(color_profile)
        else:
            data = color_profile.read()

        if num_components is None:
            inferred = _icc_num_components(data)
            if inferred is None:
                raise ValueError(
                    "could not determine ICC numComponents from header "
                    "colour-space signature; pass num_components=... "
                    "explicitly"
                )
            num_components = inferred

        # Build the PDStream encoding the bytes via FlateDecode. We push
        # the bytes through ``create_output_stream(FlateDecode)`` so the
        # data is *encoded* (compressed) on write — matching upstream's
        # ``new PDStream(doc, stream, COSName.FLATE_DECODE)`` shape, which
        # the writer interprets as "filter chain present, body already
        # encoded by the writer's filter pipeline".
        pd_stream = PDStream(document)
        with pd_stream.create_output_stream(_FLATE_DECODE) as out:
            out.write(data)
        pd_stream.get_cos_object().set_int(_N, int(num_components))
        self._dictionary.set_item(
            _DEST_OUTPUT_PROFILE, pd_stream.get_cos_object()
        )

    # ---------- presence predicates ----------
    # Distinguish "entry absent" from "entry explicitly set to a falsy
    # value" without forcing callers to grovel through the underlying
    # ``COSDictionary``. pypdfbox enrichment — Apache PDFBox 3.0 makes
    # callers compare the getter result against ``null`` themselves.

    def has_info(self) -> bool:
        """``True`` when ``/Info`` is present."""
        return self._dictionary.contains_key(_INFO)

    def has_output_condition(self) -> bool:
        """``True`` when ``/OutputCondition`` is present."""
        return self._dictionary.contains_key(_OUTPUT_CONDITION)

    def has_output_condition_identifier(self) -> bool:
        """``True`` when ``/OutputConditionIdentifier`` is present.
        PDF/A and PDF/X conformance both require this entry — a ``False``
        return on a presumed-conforming intent indicates a malformed
        dictionary."""
        return self._dictionary.contains_key(_OUTPUT_CONDITION_IDENTIFIER)

    def has_registry_name(self) -> bool:
        """``True`` when ``/RegistryName`` is present."""
        return self._dictionary.contains_key(_REGISTRY_NAME)

    def has_dest_output_profile(self) -> bool:
        """``True`` when ``/DestOutputProfile`` is present (the embedded
        ICC profile stream)."""
        return self._dictionary.contains_key(_DEST_OUTPUT_PROFILE)

    def has_dest_output_profile_ref(self) -> bool:
        """``True`` when ``/DestOutputProfileRef`` is present (PDF 2.0 /
        ISO 32000-2 §14.11.5 external profile reference)."""
        return self._dictionary.contains_key(_DEST_OUTPUT_PROFILE_REF)

    # ---------- repr ----------

    def __repr__(self) -> str:
        return (
            f"PDOutputIntent(subtype={self.get_subtype()!r}, "
            f"output_condition_identifier="
            f"{self.get_output_condition_identifier()!r})"
        )


__all__ = ["PDOutputIntent"]
