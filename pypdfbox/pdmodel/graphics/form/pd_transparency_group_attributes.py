from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
    from pypdfbox.pdmodel.pd_resources import PDResources


_S: COSName = COSName.get_pdf_name("S")
_CS: COSName = COSName.get_pdf_name("CS")
_I: COSName = COSName.get_pdf_name("I")
_K: COSName = COSName.get_pdf_name("K")
_TRANSPARENCY: COSName = COSName.get_pdf_name("Transparency")


class PDTransparencyGroupAttributes:
    """
    Transparency group attributes dictionary. Mirrors upstream
    ``org.apache.pdfbox.pdmodel.graphics.form.PDTransparencyGroupAttributes``.

    A transparency group is a group of consecutive objects in a transparency
    stack (PDF 32000-1 §11.6). The group attributes dictionary supplies the
    group's blending color space, isolation flag, and knockout flag.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            dictionary = COSDictionary()
            dictionary.set_item(_S, _TRANSPARENCY)
        self._dictionary = dictionary
        self._color_space: PDColorSpace | None = None

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    def get_color_space(
        self, resources: PDResources | None = None
    ) -> PDColorSpace | None:
        """Group color space (``/CS``); ``None`` when absent. Lazily
        resolved via :class:`PDColorSpace`.create and cached. Mirrors
        upstream ``getColorSpace([resources])`` overloads."""
        if self._color_space is None and self._dictionary.contains_key(_CS):
            # Local import keeps the cluster boundary explicit and avoids a
            # cycle through the rest of the graphics package.
            from pypdfbox.pdmodel.graphics.color.pd_color_space import (  # noqa: PLC0415
                PDColorSpace,
            )

            self._color_space = PDColorSpace.create(
                self._dictionary.get_dictionary_object(_CS),
                resources,
            )
        return self._color_space

    def set_color_space(
        self, color_space: PDColorSpace | COSBase | None
    ) -> None:
        """Set ``/CS`` group blending colour space. Accepts a typed
        ``PDColorSpace`` (its backing COS object is stored), a raw
        ``COSBase`` (typically ``COSName`` or ``COSArray``), or ``None``
        (clears the entry).

        Upstream's ``PDTransparencyGroupAttributes`` does not expose a
        public ``setColorSpace`` (the dictionary form is taken
        verbatim from upstream construction), but the cluster idiom
        here matches sibling classes — ``set_color_space`` lets call
        sites reshape the entry without poking the COS dict directly.
        Resets the typed cache so the next :meth:`get_color_space`
        re-resolves through ``PDColorSpace.create``."""
        # Local import — avoids a top-level cycle through the colour
        # cluster which itself imports form types in a few places.
        from pypdfbox.pdmodel.graphics.color.pd_color_space import (  # noqa: PLC0415
            PDColorSpace as _PDColorSpace,
        )

        if color_space is None:
            self._dictionary.remove_item(_CS)
            self._color_space = None
            return
        if isinstance(color_space, _PDColorSpace):
            cs_cos = color_space.get_cos_object()
            if cs_cos is None:
                # Device color spaces have no array form — fall back to
                # the long-form name. Mirrors PDInlineImage.set_color_space.
                cs_cos = COSName.get_pdf_name(color_space.get_name())
            self._dictionary.set_item(_CS, cs_cos)
            self._color_space = None
            return
        if isinstance(color_space, COSBase):
            self._dictionary.set_item(_CS, color_space)
            self._color_space = None
            return
        raise TypeError(
            "set_color_space expects PDColorSpace, COSBase, or None; got "
            f"{type(color_space).__name__}"
        )

    def is_isolated(self) -> bool:
        """``/I`` flag (default ``False``). Isolated groups begin with the
        fully transparent image; non-isolated groups begin with the current
        backdrop."""
        return self._dictionary.get_boolean(_I, False)

    def set_isolated(self, isolated: bool) -> None:
        """Write the ``/I`` isolation flag. Mirrors upstream's read-only
        accessor pair on the public surface (``isIsolated()``); the
        underlying COS dict is mutable and write access matches the
        sibling-class idiom."""
        self._dictionary.set_boolean(_I, bool(isolated))

    def is_knockout(self) -> bool:
        """``/K`` flag (default ``False``). Knockout groups blend with the
        original backdrop; non-knockout groups blend with the current
        backdrop."""
        return self._dictionary.get_boolean(_K, False)

    def set_knockout(self, knockout: bool) -> None:
        """Write the ``/K`` knockout flag. Mirrors the sibling-class
        idiom — see :meth:`set_isolated` for the rationale."""
        self._dictionary.set_boolean(_K, bool(knockout))

    # ---------- /S subtype ----------

    def get_subtype(self) -> str | None:
        """Return the ``/S`` group subtype name (e.g. ``"Transparency"``)
        or ``None`` when absent. The constructor's no-arg form sets this
        to ``"Transparency"`` to match upstream's
        ``PDTransparencyGroupAttributes()`` default — see PDF 32000-1
        Table 96."""
        return self._dictionary.get_name(_S)

    def set_subtype(self, subtype: str | COSName | None) -> None:
        """Write the ``/S`` group subtype. Pass ``None`` to clear the
        entry. Accepts both a plain ``str`` (auto-wrapped into a
        ``COSName``) and a pre-built ``COSName``."""
        if subtype is None:
            self._dictionary.remove_item(_S)
            return
        if isinstance(subtype, COSName):
            self._dictionary.set_item(_S, subtype)
            return
        self._dictionary.set_name(_S, subtype)

    # ---------- presence predicates ----------

    def has_color_space(self) -> bool:
        """Return ``True`` when ``/CS`` is present on the underlying
        dictionary. Mirrors the existing ``contains_key`` check used by
        :meth:`get_color_space` — useful for callers that want to skip
        the typed-resolution path entirely (the typed wrapper goes
        through ``PDColorSpace.create`` which can be expensive)."""
        return self._dictionary.contains_key(_CS)

    def has_isolated(self) -> bool:
        """Return ``True`` when ``/I`` is explicitly present. The default
        (``False``) means a missing ``/I`` is indistinguishable from
        ``/I false`` via :meth:`is_isolated`; this predicate exists for
        callers that need to detect the explicit-vs-default distinction
        (e.g. parity tests)."""
        return self._dictionary.contains_key(_I)

    def has_knockout(self) -> bool:
        """Return ``True`` when ``/K`` is explicitly present. See
        :meth:`has_isolated` for the explicit-vs-default rationale."""
        return self._dictionary.contains_key(_K)

    def has_subtype(self) -> bool:
        """Return ``True`` when ``/S`` (group subtype) is present and a
        ``COSName`` — the only valid form per PDF 32000-1 Table 96."""
        return self._dictionary.get_name(_S) is not None

    # ---------- transparency-group predicate ----------

    def is_transparency_group(self) -> bool:
        """Return ``True`` when this is a transparency group — i.e.
        ``/S`` is ``/Transparency``. Mirrors the constructor default and
        matches the dispatch used by
        ``PDXObject.create_x_object`` to pick :class:`PDTransparencyGroup`
        over a plain :class:`PDFormXObject`."""
        return self._dictionary.get_name(_S) == "Transparency"
