from __future__ import annotations

from .pd_resource_cache import PDResourceCache


class ResourceCache(PDResourceCache):
    """Alias for :class:`PDResourceCache` matching upstream's class name.

    Mirrors ``org.apache.pdfbox.pdmodel.ResourceCache`` (Java
    lines 36-302). pypdfbox historically named the abstract base
    ``PDResourceCache`` to fit the rest of the PD-namespace shape, but the
    parity tracker (and ported PDFBox tests) expect the unprefixed name
    too. This subclass is intentionally a thin pass-through so callers can
    reference either spelling and ``isinstance`` checks behave consistently.
    """

    def put(self, key: object, value: object) -> None:
        """Generic ``put(key, value)`` accessor — dispatches on the type
        of ``value`` to the matching ``put_*`` method on
        :class:`PDResourceCache`. Mirrors upstream
        ``ResourceCache.put`` (Java line 287)."""
        from pypdfbox.pdmodel.font import PDFont
        from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
        from pypdfbox.pdmodel.graphics.form import PDFormXObject
        from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject

        if isinstance(value, PDFont):
            self.put_font(key, value)
        elif isinstance(value, PDColorSpace):
            self.put_color_space(key, value)
        elif isinstance(value, PDFormXObject):
            # PDFormXObject extends PDXObject — both land in the same slot.
            self.put_x_object(key, value)
        elif isinstance(value, PDXObject):
            self.put_x_object(key, value)
        else:
            raise TypeError(
                f"ResourceCache.put: unsupported value type "
                f"{type(value).__name__}"
            )


__all__ = ["ResourceCache"]
