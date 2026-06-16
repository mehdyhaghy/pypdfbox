from __future__ import annotations


class AccessPermission:
    """
    Mirrors PDFBox ``AccessPermission``. Pure-Python wrapper around the PDF
    ``/P`` permission integer (PDF 32000-1 §7.6.3.2 / Table 22) — **not**
    backed by a ``COSDictionary``.

    Bit semantics (1-based positions per the PDF spec; bits 1 and 2 are
    reserved and must be 0; the value stored in ``/P`` is interpreted as a
    32-bit signed two's-complement integer with all unused high bits set).

    Bit positions (Table 22):
        3  — printing (low quality if bit 12 also clear)
        4  — modify content
        5  — extract content (text/graphics)
        6  — modify annotations / fill forms (revision 2) / create form fields
        9  — fill in form fields (revision 3+)
        10 — extract for accessibility (deprecated in PDF 2.0)
        11 — assemble document (insert/rotate/delete pages, bookmarks)
        12 — high-quality (faithful) print
    """

    # Bit position constants (1-based, as the PDF spec numbers them). The
    # actual bit value is ``1 << (POS - 1)``.
    BIT_PRINTABLE: int = 3                       # value 1 << 2
    BIT_MODIFIABLE: int = 4                      # value 1 << 3
    BIT_EXTRACTABLE: int = 5                     # value 1 << 4
    BIT_MODIFIABLE_ANNOTATIONS: int = 6          # value 1 << 5
    BIT_FILL_FORMS: int = 9                      # value 1 << 8
    BIT_EXTRACTABLE_FOR_ACCESSIBILITY: int = 10  # value 1 << 9
    BIT_ASSEMBLE_DOCUMENT: int = 11              # value 1 << 10
    BIT_PRINT_DEGRADED: int = 12                 # value 1 << 11

    # Default — all permissions allowed; matches PDFBox ``DEFAULT_PERMISSIONS = ~3``
    # (every bit set except the reserved bits 1 and 2).
    _DEFAULT_PERMISSIONS: int = ~3

    # Sentinel distinguishing the no-arg constructor from an explicit ``/P``
    # value. Upstream PDFBox has two *separate* constructors: the no-arg one
    # stores ``DEFAULT_PERMISSIONS`` (``~3 == -4``) and the ``int`` one stores
    # the argument VERBATIM. Python's single ``__init__`` re-creates that split
    # via this sentinel — a plain default of ``-1`` would be indistinguishable
    # from an explicit ``AccessPermission(-1)``, which upstream stores as ``-1``,
    # not ``-4`` (the wave-1537 fix).
    _UNSET = object()

    def __init__(self, permissions: object = _UNSET) -> None:
        """Construct an ``AccessPermission``.

        With no argument this mirrors upstream's **no-arg** constructor and
        stores ``DEFAULT_PERMISSIONS`` (``~3``); every defined permission bit
        is set, the reserved bits 1–2 are clear. With an explicit integer this
        mirrors upstream's ``AccessPermission(int)`` and stores the value
        **verbatim** (typically the raw ``/P`` integer) — including an explicit
        ``-1`` (all bits set), which upstream keeps as ``-1``, NOT ``-4``.
        """
        if permissions is self._UNSET:
            self._bytes: int = self._DEFAULT_PERMISSIONS
        else:
            self._bytes = int(permissions)  # type: ignore[arg-type]
        self._read_only: bool = False

    # ---------- raw access ----------

    def get_permission_bytes(self) -> int:
        """Return the permission bits encoded as the int stored in ``/P``."""
        return self._bytes

    def get_permission_bits_as_int(self) -> int:
        """Alias for ``get_permission_bytes`` matching the PDFBox helper
        name used in some call sites."""
        return self._bytes

    # ---------- owner / read-only flag ----------

    def is_owner_permission(self) -> bool:
        """True when every defined permission bit is set — by convention,
        the owner has full access regardless of the ``/P`` value."""
        return (
            self.can_assemble_document()
            and self.can_extract_content()
            and self.can_extract_for_accessibility()
            and self.can_fill_in_form()
            and self.can_modify()
            and self.can_modify_annotations()
            and self.can_print()
            and self.can_print_faithful()
        )

    def set_read_only(self) -> None:
        """Lock this instance — subsequent setters become no-ops. Mirrors
        upstream ``setReadOnly()``. Used when this object originates from
        an opened, decrypted document so callers cannot mutate the
        already-applied policy."""
        self._read_only = True

    def is_read_only(self) -> bool:
        return self._read_only

    @classmethod
    def get_owner_access_permission(cls) -> AccessPermission:
        """Return an instance with every permission bit set (owner)."""
        return cls(cls._DEFAULT_PERMISSIONS)

    @classmethod
    def get_instance(cls) -> AccessPermission:
        """Static factory returning a fully-permissive (owner) instance.

        Mirrors PDFBox ``AccessPermission.getInstance()`` — semantically
        equivalent to the no-arg constructor but reads more cleanly at
        call sites that just want default/owner permissions."""
        return cls()

    @classmethod
    def from_bytes(cls, b: bytes) -> AccessPermission:
        """Build an ``AccessPermission`` from a 4-byte big-endian buffer.

        Mirrors the upstream ``AccessPermission(byte[] b)`` constructor —
        bytes are interpreted most-significant-byte first to recreate the
        signed 32-bit ``/P`` integer used by the public-key handler.
        """
        if len(b) < 4:
            msg = f"AccessPermission.from_bytes requires 4 bytes, got {len(b)}"
            raise ValueError(msg)
        # Upstream reads with sign extension on the top byte: shifting a
        # signed int left preserves the high bit, so a leading 0xFF stays
        # 0xFFFFFFFF after the loop. Replicate that with int.from_bytes
        # signed=True to keep the negative-int semantics of /P.
        permissions = int.from_bytes(bytes(b[:4]), "big", signed=True)
        return cls(permissions)

    # ---------- public-key permission encoding ----------

    def get_permission_bytes_for_public_key(self) -> int:
        """Return the integer used by the public-key handler.

        Mirrors upstream ``getPermissionBytesForPublicKey`` — the format is
        not defined in the PDF spec but Adobe products require:

        * bit 1 set (reserved-but-required for public-key)
        * bits 7 and 8 cleared
        * bits 13–32 cleared

        These tweaks mutate the receiver in-place to match upstream
        behaviour (a subsequent ``get_permission_bytes`` returns the same
        value).
        """
        # Upstream silently ignores readOnly inside this helper (it mutates
        # `bytes` regardless). Mirror that by bypassing the readOnly gate
        # rather than going through the public setters.
        self._bytes |= 1 << 0  # bit 1 (1-based) ON
        self._bytes &= ~(1 << 6)  # bit 7 OFF
        self._bytes &= ~(1 << 7)  # bit 8 OFF
        # Clear bits 13..32 (1-based), i.e. mask off the high 20 bits of a
        # 32-bit signed int. We additionally clear all bits above bit 32
        # so a Python negative int collapses to the same 12-bit value Java
        # produces.
        self._bytes &= 0x00000FFF
        return self._bytes

    # ---------- revision-3 helper ----------

    def has_any_revision3_permission_set(self) -> bool:
        """True if any permission introduced at /R 3 is set.

        Mirrors upstream ``hasAnyRevision3PermissionSet`` — used by the
        standard security handler when computing the user-password hash to
        decide whether the document needs at least revision 3.
        """
        return (
            self.can_fill_in_form()
            or self.can_extract_for_accessibility()
            or self.can_assemble_document()
            or self.can_print_faithful()
        )

    # ---------- internal bit helpers ----------

    @staticmethod
    def _bit_value(bit_pos: int) -> int:
        # Spec uses 1-based bit positions; 1 << (pos - 1) yields the actual mask.
        return 1 << (bit_pos - 1)

    def _is_set(self, bit_pos: int) -> bool:
        return (self._bytes & self._bit_value(bit_pos)) != 0

    def _set_bit(self, bit_pos: int, value: bool) -> None:
        if self._read_only:
            return
        mask = self._bit_value(bit_pos)
        if value:
            self._bytes |= mask
        else:
            self._bytes &= ~mask

    # ---------- 1-based bit-level accessors (mirror upstream privates) ----------

    def is_permission_bit_on(self, bit: int) -> bool:
        """Test the 1-based ``bit`` in the permission integer.

        Mirrors upstream private ``isPermissionBitOn(int)`` — exposed at
        module scope here for callers (e.g. ``getPermissionBytesForPublicKey``)
        that need raw 1-based bit access without going through the typed
        per-permission accessors.
        """
        return (self._bytes & (1 << (bit - 1))) != 0

    def set_permission_bit(self, bit: int, value: bool) -> bool:
        """Set or clear the 1-based ``bit`` and return the new state.

        Mirrors upstream private ``setPermissionBit(int, boolean)``.
        Unlike :py:meth:`_set_bit`, this method bypasses the read-only
        gate to match upstream behaviour: the Java implementation likewise
        ignores ``readOnly`` for this private helper (it is used internally
        by ``getPermissionBytesForPublicKey`` after read-only has been
        applied).
        """
        if value:
            self._bytes |= 1 << (bit - 1)
        else:
            self._bytes &= ~(1 << (bit - 1))
        return (self._bytes & (1 << (bit - 1))) != 0

    # ---------- per-permission accessors (mirror PDFBox names) ----------

    def can_print(self) -> bool:
        return self._is_set(self.BIT_PRINTABLE)

    def set_can_print(self, b: bool) -> None:
        self._set_bit(self.BIT_PRINTABLE, b)

    def can_modify(self) -> bool:
        return self._is_set(self.BIT_MODIFIABLE)

    def set_can_modify(self, b: bool) -> None:
        self._set_bit(self.BIT_MODIFIABLE, b)

    def can_extract_content(self) -> bool:
        return self._is_set(self.BIT_EXTRACTABLE)

    def set_can_extract_content(self, b: bool) -> None:
        self._set_bit(self.BIT_EXTRACTABLE, b)

    def can_modify_annotations(self) -> bool:
        return self._is_set(self.BIT_MODIFIABLE_ANNOTATIONS)

    def set_can_modify_annotations(self, b: bool) -> None:
        self._set_bit(self.BIT_MODIFIABLE_ANNOTATIONS, b)

    def can_fill_in_form(self) -> bool:
        return self._is_set(self.BIT_FILL_FORMS)

    def set_can_fill_in_form(self, b: bool) -> None:
        self._set_bit(self.BIT_FILL_FORMS, b)

    def can_extract_for_accessibility(self) -> bool:
        """Bit 10 — extract for accessibility. Deprecated in PDF 2.0
        (ISO 32000-2 mandates that text extraction be unconditionally
        permitted for accessibility regardless of this bit)."""
        return self._is_set(self.BIT_EXTRACTABLE_FOR_ACCESSIBILITY)

    def set_can_extract_for_accessibility(self, b: bool) -> None:
        self._set_bit(self.BIT_EXTRACTABLE_FOR_ACCESSIBILITY, b)

    def can_assemble_document(self) -> bool:
        return self._is_set(self.BIT_ASSEMBLE_DOCUMENT)

    def set_can_assemble_document(self, b: bool) -> None:
        self._set_bit(self.BIT_ASSEMBLE_DOCUMENT, b)

    # Bit 12: high-quality / "faithful" printing. Upstream PDFBox renamed
    # ``canPrintDegraded`` → ``canPrintFaithful`` because the original name
    # was inverted from what the bit actually indicates (the bit being SET
    # permits faithful/high-quality print; CLEARED forces low-resolution).
    # Both names are exposed for compatibility.

    def can_print_faithful(self) -> bool:
        return self._is_set(self.BIT_PRINT_DEGRADED)

    def set_can_print_faithful(self, b: bool) -> None:
        self._set_bit(self.BIT_PRINT_DEGRADED, b)

    def can_print_degraded(self) -> bool:
        """Legacy alias for :py:meth:`can_print_faithful`. Kept for
        backward compatibility with older PDFBox API."""
        return self.can_print_faithful()

    def set_can_print_degraded(self, b: bool) -> None:
        """Legacy alias for :py:meth:`set_can_print_faithful`."""
        self.set_can_print_faithful(b)


__all__ = ["AccessPermission"]
