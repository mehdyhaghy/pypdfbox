from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSName,
    COSStream,
)

if TYPE_CHECKING:
    pass

# PDF 32000-1 §11.6.5.3 (Soft-Mask Dictionaries) — Table 144 keys.
_TYPE: COSName = COSName.get_pdf_name("Type")
_S: COSName = COSName.get_pdf_name("S")
_G: COSName = COSName.get_pdf_name("G")
_BC: COSName = COSName.get_pdf_name("BC")
_TR: COSName = COSName.get_pdf_name("TR")
_MASK: COSName = COSName.get_pdf_name("Mask")
_ALPHA: COSName = COSName.get_pdf_name("Alpha")
_LUMINOSITY: COSName = COSName.get_pdf_name("Luminosity")
_NONE: COSName = COSName.get_pdf_name("None")
_IDENTITY: COSName = COSName.get_pdf_name("Identity")


class PDSoftMask:
    """A soft-mask dictionary. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.state.PDSoftMask``.

    Per PDF 32000-1 §11.6.5.3 (Table 144):

    - ``/Type`` — optional; when present must be ``/Mask``.
    - ``/S`` — required; subtype name ``/Alpha`` or ``/Luminosity``.
    - ``/G`` — required; transparency-group XObject defining the mask.
    - ``/BC`` — optional; backdrop colour array (used for ``/Luminosity``).
      Default is the appropriate "no colour" value in ``G``'s colour space.
    - ``/TR`` — optional; transfer function applied to the mask values
      before they become alpha. Default is the identity function.

    The wrapper exposes the raw COS objects — callers performing the
    actual compositing (e.g. :class:`PDFRenderer`) handle the typed
    decoding (group XObject parsing, function evaluation, channel pick).
    """

    def __init__(
        self,
        dictionary: COSDictionary | None = None,
        resource_cache: Any | None = None,
    ) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
            self._dict.set_item(_TYPE, _MASK)
        else:
            if not isinstance(dictionary, COSDictionary):
                raise TypeError(
                    "PDSoftMask expects COSDictionary, got "
                    f"{type(dictionary).__name__}"
                )
            self._dict = dictionary
        self._resource_cache = resource_cache
        self._subtype: COSName | None = None
        self._group: Any | None = None
        self._backdrop_color: COSArray | None = None
        self._typed_transfer_function: Any | None = None
        # CTM at the time the ExtGState was activated. Mirrors upstream
        # ``setInitialTransformationMatrix`` / ``getInitialTransformationMatrix``
        # — see the comment at PDExtendedGraphicsState.copyIntoGraphicsState
        # in upstream which writes this on /SMask activation.
        self._ctm: Any | None = None

    # ---------- factory ----------

    @staticmethod
    def create(
        base: COSBase | None, resource_cache: Any | None = None
    ) -> PDSoftMask | None:
        """Wrap ``base`` as a :class:`PDSoftMask` when it is a soft-mask
        dictionary. Returns ``None`` for the special ``/None`` mask name
        (PDF spec: "the value of the soft-mask parameter shall be set to
        None") or for any non-dictionary value. Mirrors upstream
        ``PDSoftMask.create``.

        ``resource_cache`` (optional) is forwarded to the constructed
        wrapper so that ``getGroup`` lookups can re-use cached XObjects;
        mirrors upstream's two-arg overload."""
        if base is None:
            return None
        if isinstance(base, COSName) and base.name == "None":
            return None
        if isinstance(base, COSDictionary):
            return PDSoftMask(base, resource_cache)
        return None

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /S (subtype) ----------

    def get_subtype(self) -> COSName | None:
        """Returns the ``/S`` entry — ``/Alpha`` or ``/Luminosity``, or
        ``None`` when missing (a malformed soft-mask dictionary)."""
        if self._subtype is None:
            value = self._dict.get_dictionary_object(_S)
            if isinstance(value, COSName):
                self._subtype = value
        return self._subtype

    def get_sub_type(self) -> COSName | None:
        """Mirror upstream ``PDSoftMask.getSubType()`` (line 134 in
        PDSoftMask.java) — Java's mechanical case-conversion would yield
        ``get_sub_type``, but pypdfbox sibling wrappers (e.g.
        :class:`PDArtifactMarkedContent`) consistently use ``get_subtype``.
        Both spellings are exposed so PDFBox developers porting code
        verbatim find the upstream-shaped name.
        """
        return self.get_subtype()

    def set_subtype(self, subtype: COSName) -> None:
        self._dict.set_item(_S, subtype)
        self._subtype = subtype

    # ---------- /G (transparency group) ----------

    def get_group(self) -> Any | None:
        """Returns the ``/G`` transparency-group form XObject as a
        :class:`PDTransparencyGroup` typed wrapper when the form advertises
        ``/Group << /S /Transparency >>``. Plain forms and other valid
        XObject subtypes return ``None``. Invalid scalar and subtype values
        propagate the XObject factory's ``OSError``, matching upstream's
        ``IOException`` contract. Existing pypdfbox compatibility is retained
        for bare caller-built streams and dictionary-shaped values."""
        if self._group is None:
            group_base = self._dict.get_dictionary_object(_G)
            if group_base is None:
                return None
            from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (  # noqa: PLC0415
                PDFormXObject,
            )
            from pypdfbox.pdmodel.graphics.form.pd_transparency_group import (  # noqa: PLC0415
                PDTransparencyGroup,
            )
            from pypdfbox.pdmodel.graphics.pd_x_object import (  # noqa: PLC0415
                PDXObject,
            )
            from pypdfbox.pdmodel.pd_resources import PDResources  # noqa: PLC0415

            if isinstance(group_base, COSStream) and group_base.get_name(
                COSName.SUBTYPE  # type: ignore[attr-defined]
            ) is None:
                self._group = PDFormXObject(
                    group_base, cache=self._resource_cache
                )
                return self._group
            if isinstance(group_base, COSDictionary) and not isinstance(
                group_base, COSStream
            ):
                return None
            resources = PDResources(
                COSDictionary(), resource_cache=self._resource_cache
            )
            xobject = PDXObject.create_x_object(group_base, resources)
            if isinstance(xobject, PDTransparencyGroup):
                self._group = xobject
        return self._group

    def set_group(self, group: Any | None) -> None:
        if group is None:
            self._dict.remove_item(_G)
            self._group = None
            return
        # Accept either a typed PDFormXObject or a raw COSStream.
        cos = group.get_cos_object() if hasattr(group, "get_cos_object") else group
        if not isinstance(cos, COSStream):
            raise TypeError(
                "set_group expects PDFormXObject or COSStream, got "
                f"{type(group).__name__}"
            )
        self._dict.set_item(_G, cos)
        from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (  # noqa: PLC0415
            PDFormXObject,
        )

        self._group = (
            group
            if isinstance(group, PDFormXObject)
            else PDFormXObject(cos, cache=self._resource_cache)
        )

    # ---------- /BC (backdrop colour) ----------

    def get_backdrop_color(self) -> COSArray | None:
        """Returns the raw ``/BC`` colour array (one component per
        channel of ``G``'s colour space) or ``None`` when absent."""
        if self._backdrop_color is None:
            value = self._dict.get_dictionary_object(_BC)
            if isinstance(value, COSArray):
                self._backdrop_color = value
        return self._backdrop_color

    def set_backdrop_color(self, bc: COSArray | None) -> None:
        if bc is None:
            self._dict.remove_item(_BC)
            self._backdrop_color = None
            return
        self._dict.set_item(_BC, bc)
        self._backdrop_color = bc

    # ---------- /TR (transfer function) ----------

    def get_transfer_function(self) -> COSBase | None:
        """Returns the raw ``/TR`` entry (a function dict/stream or the
        name ``/Identity``); ``None`` when absent (caller treats absent
        as ``/Identity`` per spec)."""
        return self._dict.get_dictionary_object(_TR)

    def set_transfer_function(self, transfer: COSBase | None) -> None:
        if transfer is None:
            self._dict.remove_item(_TR)
            self._typed_transfer_function = None
            return
        self._dict.set_item(_TR, transfer)
        self._typed_transfer_function = None

    # ---------- introspection helpers ----------

    def is_alpha(self) -> bool:
        """True iff ``/S`` is ``/Alpha`` (per §11.6.5.3 the mask values are
        sampled directly from the group's accumulated alpha)."""
        s = self.get_subtype()
        return isinstance(s, COSName) and s.name == "Alpha"

    def is_luminosity(self) -> bool:
        """True iff ``/S`` is ``/Luminosity`` (per §11.6.5.3 the mask
        values come from a luminance reading of the group's RGB)."""
        s = self.get_subtype()
        return isinstance(s, COSName) and s.name == "Luminosity"

    # ---------- typed transfer function ----------

    def get_transfer_function_typed(self) -> Any | None:
        """Return ``/TR`` resolved to a typed :class:`PDFunction` (or
        ``None`` when absent). Mirrors upstream
        ``PDSoftMask.getTransferFunction()`` which returns a
        ``PDFunction``. Companion to :meth:`get_transfer_function`
        (which returns the raw COS object)."""
        from pypdfbox.pdmodel.common.function.pd_function import (  # noqa: PLC0415
            PDFunction,
        )

        if self._typed_transfer_function is None:
            base = self.get_transfer_function()
            if base is None:
                return None
            if (
                isinstance(base, COSDictionary)
                and not isinstance(base, COSStream)
                and base.get_int(COSName.get_pdf_name("FunctionType"), -1) == 4
            ):
                raise TypeError("PDFunctionType4 requires a COSStream")
            self._typed_transfer_function = PDFunction.create(base)
        return self._typed_transfer_function

    # ---------- initial transformation matrix (CTM at activation) ----------

    def set_initial_transformation_matrix(self, ctm: Any) -> None:
        """Record the CTM in effect when the ExtGState that owns this
        soft mask was activated. Required for correct compositing because
        the soft mask's group XObject is positioned in the parent's user
        space at activation time, not at paint time. Mirrors upstream
        ``PDSoftMask.setInitialTransformationMatrix`` (package-private
        upstream — exposed publicly here for renderer interop and tests).
        """
        self._ctm = ctm

    def get_initial_transformation_matrix(self) -> Any | None:
        """Return the CTM recorded by
        :meth:`set_initial_transformation_matrix`, or ``None`` when the
        soft mask has not yet been activated."""
        return self._ctm

    # ---------- resource cache ----------

    def get_resource_cache(self) -> Any | None:
        """Return the optional resource cache supplied at construction
        time (or via :meth:`PDSoftMask.create`). Mirrors upstream's
        ``resourceCache`` field — propagated to ``getGroup`` consumers
        so XObject parsing can share parsed forms across pages."""
        return self._resource_cache


__all__ = ["PDSoftMask"]
