from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class DigitalSignatureTable(TTFTable):
    """``DSIG`` — Digital Signature table.

    Mirrors ``org.apache.fontbox.ttf.DigitalSignatureTable``. Upstream is
    a near-empty placeholder (just the ``TAG`` constant and a default
    constructor); pypdfbox exposes a slightly richer accessor surface so
    callers can inspect signature metadata without re-parsing the table
    by hand.

    The actual ``DSIG`` payload is decoded by ``fontTools.ttLib`` (see
    ``fontTools.ttLib.tables.D_S_I_G_``) — TTF binary parsing is exactly
    what fontTools exists for, so we wrap its result instead of rolling
    our own decoder.
    """

    TAG: str = "DSIG"

    def __init__(self) -> None:
        super().__init__()
        self._tag = self.TAG
        # Header fields (ulVersion / usNumSigs / usFlag).
        self._version: int = 0
        self._num_signatures: int = 0
        self._flag: int = 0
        # Per-signature raw PKCS#7 blocks, in directory order.
        self._signature_blocks: list[bytes] = []

    # ------------------------------------------------------------------
    # Population paths
    # ------------------------------------------------------------------

    def populate_from_fonttools(self, ft_dsig: Any) -> None:
        """Copy header + signature blocks out of a fontTools ``D_S_I_G_``
        table object. ``TrueTypeFont.get_dsig`` is the only caller; kept
        as a method (not a classmethod) to mirror the established
        ``HeaderTable`` / ``HorizontalHeaderTable`` populate-then-cache
        pattern used elsewhere in this module.
        """
        self._version = int(getattr(ft_dsig, "ulVersion", 0))
        self._num_signatures = int(getattr(ft_dsig, "usNumSigs", 0))
        self._flag = int(getattr(ft_dsig, "usFlag", 0))
        records = getattr(ft_dsig, "signatureRecords", None) or []
        self._signature_blocks = [bytes(getattr(r, "pkcs7", b"") or b"") for r in records]
        self.initialized = True

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:  # noqa: ARG002
        """Stand-in for the upstream no-op ``read`` slot.

        Upstream's ``DigitalSignatureTable`` doesn't override ``read``
        either — it leans on the base ``TTFTable`` (which is also a
        no-op for unknown tags). Real decoding goes through
        :meth:`populate_from_fonttools`.
        """
        # Intentionally empty — see class docstring.

    # ------------------------------------------------------------------
    # Accessors (snake_case mirror of the conceptual upstream surface)
    # ------------------------------------------------------------------

    def get_version(self) -> int:
        """``ulVersion`` from the DSIG header (must be 1 per the spec)."""
        return self._version

    def get_num_signatures(self) -> int:
        """``usNumSigs`` — number of signature records in the table."""
        return self._num_signatures

    def get_flag(self) -> int:
        """``usFlag`` — permissions / restriction flag (0 or 1 per spec)."""
        return self._flag

    def get_signature_blocks(self) -> list[bytes]:
        """Raw PKCS#7 blocks, one ``bytes`` per signature record.

        Returns a fresh list each call so mutation by callers can't
        corrupt the cached state.
        """
        return list(self._signature_blocks)

    def get_signature_block(self, index: int) -> bytes:
        """PKCS#7 bytes for the ``index``-th signature record.

        Raises :class:`IndexError` for out-of-range indices, matching
        ordinary Python list semantics.
        """
        return self._signature_blocks[index]


__all__ = ["DigitalSignatureTable"]
