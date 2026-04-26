from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSStream

from .pd_appearance_stream import PDAppearanceStream


class PDAppearanceEntry:
    """
    An entry in an appearance dictionary. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry``.

    Per PDF 32000-1:2008 §12.5.5 an appearance entry is *either*:

    - a single appearance stream (``COSStream``) — a "direct" appearance, or
    - an appearance subdictionary (``COSDictionary``) mapping a state name
      (e.g. ``/On``, ``/Off``, ``/Yes``) to a per-state appearance stream.

    The wrapper inspects the COS object's runtime type to dispatch
    :meth:`is_stream` vs :meth:`is_sub_dictionary`. Note that ``COSStream``
    extends ``COSDictionary``, so the stream check must come *first*.
    """

    def __init__(self, entry: COSBase | None = None) -> None:
        if entry is not None and not isinstance(entry, (COSStream, COSDictionary)):
            raise TypeError(
                "PDAppearanceEntry requires a COSStream, COSDictionary, or None; "
                f"got {type(entry).__name__}"
            )
        self._entry: COSStream | COSDictionary | None = entry

    def get_cos_object(self) -> COSBase:
        if self._entry is None:
            raise ValueError("PDAppearanceEntry has no underlying COS object")
        return self._entry

    def is_stream(self) -> bool:
        """True when this entry is an appearance stream."""
        return isinstance(self._entry, COSStream)

    def is_sub_dictionary(self) -> bool:
        """True when this entry is an appearance subdictionary (state-mapped)."""
        return isinstance(self._entry, COSDictionary) and not isinstance(
            self._entry, COSStream
        )

    def get_appearance_stream(self) -> PDAppearanceStream | None:
        """Return the wrapped appearance stream.

        Raises ``ValueError`` (mirrors upstream's ``IllegalStateException``)
        when this entry is a subdictionary instead of a stream.
        """
        if self._entry is None:
            return None
        if not self.is_stream():
            raise ValueError("This entry is not an appearance stream")
        assert isinstance(self._entry, COSStream)
        return PDAppearanceStream(self._entry)

    def get_sub_dictionary(self) -> dict[str, PDAppearanceStream]:
        """Return the state -> appearance-stream mapping.

        Raises ``ValueError`` (mirrors upstream's ``IllegalStateException``)
        when this entry is a single stream instead of a subdictionary.
        Non-stream values are skipped — matches upstream's PDFBOX-1599
        guard against a ``/null`` value among the state entries.
        """
        if not self.is_sub_dictionary():
            raise ValueError("This entry is not an appearance subdictionary")
        assert isinstance(self._entry, COSDictionary)
        out: dict[str, PDAppearanceStream] = {}
        for name in self._entry.key_set():
            value = self._entry.get_dictionary_object(name)
            if isinstance(value, COSStream):
                out[name.get_name()] = PDAppearanceStream(value)
        return out


__all__ = ["PDAppearanceEntry"]
