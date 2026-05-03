from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_P: COSName = COSName.get_pdf_name("P")


class PDSeedValueMDP:
    """``/MDP`` sub-dictionary of a seed value (``/Type /SV``) entry.

    Mirrors PDFBox ``PDSeedValueMDP`` (PDF 32000-1 §12.7.4.5, Table 235).
    Defines whether an author signature or a certification signature shall
    be used. The single field is ``/P`` whose integer value (0..3) is
    interpreted per ISO 32000-1 §12.8.2.2.2:

    * 0 — author signature
    * 1 — certification signature, no changes permitted
    * 2 — certification signature, form fill-in / signing permitted
    * 3 — certification signature, plus annotation/form/signing permitted
    """

    # /P permission values (PDF 32000-1 §12.8.2.2.2 / DocMDP transform). Exposed
    # as class constants for parity with PDFBox's :class:`PDSignatureLock`
    # and to give callers symbolic names instead of magic integers.
    # ``P_AUTHOR_SIGNATURE`` (= 0) marks the signature as a regular author
    # signature; ``P_NO_CHANGES`` / ``P_FORM_FILL_AND_SIGN`` /
    # ``P_FORM_FILL_ANNOTATE_AND_SIGN`` (1..3) mark it as a certification
    # signature with the matching DocMDP /P permission level.
    P_AUTHOR_SIGNATURE = 0
    P_NO_CHANGES = 1
    P_FORM_FILL_AND_SIGN = 2
    P_FORM_FILL_ANNOTATE_AND_SIGN = 3

    def __init__(self, dict_: COSDictionary | None = None) -> None:
        if dict_ is None:
            self._dict = COSDictionary()
        else:
            self._dict = dict_
        self._dict.set_direct(True)

    def get_cos_object(self) -> COSDictionary:
        """Return the wrapped ``COSDictionary``."""
        return self._dict

    # ---------- /P ----------

    def get_p(self) -> int:
        """Return the ``/P`` permission integer (0..3); ``-1`` if absent
        (mirrors ``COSDictionary.get_int`` default behavior)."""
        return self._dict.get_int(_P)

    def set_p(self, p: int) -> None:
        """Set the ``/P`` permission integer.

        Raises :class:`ValueError` if ``p`` is not in ``[0, 3]``.
        Mirrors upstream ``IllegalArgumentException``.
        """
        if p < 0 or p > 3:
            raise ValueError("Only values between 0 and 3 are allowed.")
        self._dict.set_int(_P, p)

    # ---------- predicates ----------

    def has_p(self) -> bool:
        """Return ``True`` when a ``/P`` entry is present.

        Disambiguates :meth:`get_p`'s ``-1`` default — when ``/P`` is absent
        the dictionary defines no rules regarding the type of signature
        (PDF 32000-1 §12.7.4.5 — "If this MDP key is not present or the MDP
        dictionary does not contain a P entry, no rules shall be defined").
        """
        return self._dict.contains_key(_P)

    def is_author_signature(self) -> bool:
        """Return ``True`` when ``/P`` is ``0`` (author signature).

        Returns ``False`` if ``/P`` is absent or any other value.
        """
        return self.has_p() and self.get_p() == self.P_AUTHOR_SIGNATURE

    def is_certification_signature(self) -> bool:
        """Return ``True`` when ``/P`` is in ``{1, 2, 3}`` (certification
        signature). Returns ``False`` if ``/P`` is absent or ``0``.
        """
        return self.has_p() and 1 <= self.get_p() <= 3

    def is_no_changes(self) -> bool:
        """Return ``True`` when ``/P`` is ``1`` — certification signature
        with no changes permitted (DocMDP /P = 1).
        """
        return self.has_p() and self.get_p() == self.P_NO_CHANGES

    def is_form_fill_and_sign(self) -> bool:
        """Return ``True`` when ``/P`` is ``2`` — certification signature
        permitting form fill-in and signing (DocMDP /P = 2).
        """
        return self.has_p() and self.get_p() == self.P_FORM_FILL_AND_SIGN

    def is_form_fill_annotate_and_sign(self) -> bool:
        """Return ``True`` when ``/P`` is ``3`` — certification signature
        permitting annotations + form fill-in + signing (DocMDP /P = 3).
        """
        return (
            self.has_p() and self.get_p() == self.P_FORM_FILL_ANNOTATE_AND_SIGN
        )

    # ---------- string form ----------

    _P_LABELS: dict[int, str] = {
        P_AUTHOR_SIGNATURE: "author",
        P_NO_CHANGES: "no_changes",
        P_FORM_FILL_AND_SIGN: "form_fill_and_sign",
        P_FORM_FILL_ANNOTATE_AND_SIGN: "form_fill_annotate_and_sign",
    }

    def __str__(self) -> str:
        """Compact summary mentioning the /P permission level by name.

        Java's ``Object.toString()`` is ``ClassName@hashcode`` which is
        useless for debugging seed-value MDP dicts; this lite port instead
        labels the populated /P permission level (or ``<empty>`` when /P is
        absent). For unknown /P values the integer is shown verbatim so
        non-spec dictionaries surface clearly.
        """
        if not self.has_p():
            return "PDSeedValueMDP(<empty>)"
        p = self.get_p()
        label = self._P_LABELS.get(p, str(p))
        return f"PDSeedValueMDP(p={p} ({label}))"

    def __repr__(self) -> str:
        return self.__str__()


__all__ = ["PDSeedValueMDP"]
