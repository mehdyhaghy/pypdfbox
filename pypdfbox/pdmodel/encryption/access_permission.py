from __future__ import annotations


class AccessPermission:
    """
    Mirrors PDFBox ``AccessPermission``. Pure-Python wrapper around the PDF
    ``/P`` permission integer (PDF 32000-1 §7.6.3.2 / Table 22) — **not**
    backed by a ``COSDictionary``.

    Bit semantics (1-based positions per the PDF spec; bits 1 and 2 are
    reserved and must be 0; the value stored in ``/P`` is interpreted as a
    32-bit signed two's-complement integer with all unused high bits set).
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

    def __init__(self, permissions: int = -1) -> None:
        # ``-1`` is the convention used by the upstream no-arg constructor:
        # all bits set, including the reserved low ones, which then get
        # masked off implicitly by the bit accessors.
        if permissions == -1:
            self._bytes: int = self._DEFAULT_PERMISSIONS
        else:
            self._bytes = permissions
        self._read_only: bool = False

    # ---------- raw access ----------

    def get_permission_bytes(self) -> int:
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
            and self.can_print_degraded()
        )

    def set_read_only(self) -> None:
        """Lock this instance — subsequent setters become no-ops. Mirrors
        upstream ``setReadOnly()``."""
        self._read_only = True

    def is_read_only(self) -> bool:
        return self._read_only

    @classmethod
    def get_owner_access_permission(cls) -> AccessPermission:
        """Return an instance with every permission bit set (owner)."""
        perm = cls(cls._DEFAULT_PERMISSIONS)
        return perm

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
        return self._is_set(self.BIT_EXTRACTABLE_FOR_ACCESSIBILITY)

    def set_can_extract_for_accessibility(self, b: bool) -> None:
        self._set_bit(self.BIT_EXTRACTABLE_FOR_ACCESSIBILITY, b)

    def can_assemble_document(self) -> bool:
        return self._is_set(self.BIT_ASSEMBLE_DOCUMENT)

    def set_can_assemble_document(self, b: bool) -> None:
        self._set_bit(self.BIT_ASSEMBLE_DOCUMENT, b)

    def can_print_degraded(self) -> bool:
        return self._is_set(self.BIT_PRINT_DEGRADED)

    def set_can_print_degraded(self, b: bool) -> None:
        self._set_bit(self.BIT_PRINT_DEGRADED, b)


__all__ = ["AccessPermission"]
