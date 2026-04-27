"""Singleton registry for the active :class:`FontMapper`.

Mirrors ``org.apache.pdfbox.pdmodel.font.FontMappers`` from PDFBox 3.0:
two static methods, ``instance()`` and ``set(mapper)``, with a lazy
default that materialises a :class:`DefaultFontMapper` on first access.

Upstream Java is package-final with a private constructor; here we use
a class with classmethods (callers exercise :meth:`FontMappers.instance`
/ :meth:`FontMappers.set` exactly like Java) and a module-level lock so
``set`` is thread-safe in the same way Java's ``synchronized`` is.

Hot-swap is supported — passing ``None`` to :meth:`FontMappers.set`
(or :meth:`FontMappers.reset`) clears the override and lets the next
:meth:`instance` rebuild a default mapper. That gives tests a clean
slate without leaking state between modules.
"""

from __future__ import annotations

import threading

from .font_mapper import DefaultFontMapper, FontMapper

# Single module-level lock guarding ``_instance`` and ``_default``. Plain
# ``threading.Lock`` matches the granularity of upstream
# ``synchronized`` on the static ``set`` method.
_lock = threading.Lock()
_instance: FontMapper | None = None
_default: FontMapper | None = None


class FontMappers:
    """Static registry — call :meth:`instance` / :meth:`set` directly.

    Mirrors upstream final class with a private constructor. Instances
    aren't useful (no instance state); callers always reach the
    singleton through the class methods.
    """

    def __init__(self) -> None:
        # Match the upstream "private constructor" signal — instances
        # aren't useful, so refuse construction. Tests that want to
        # poke at the registry should use the classmethods directly.
        raise TypeError(
            "FontMappers is a static registry; use FontMappers.instance() "
            "and FontMappers.set() instead of constructing it."
        )

    @classmethod
    def instance(cls) -> FontMapper:
        """Return the active :class:`FontMapper` singleton.

        Mirrors upstream ``static FontMapper instance()``. Lazily
        materialises a :class:`DefaultFontMapper` on first access so
        importing this module doesn't pay the AFM-parsing cost upfront.
        Subsequent calls return the same instance until :meth:`set` or
        :meth:`reset` swaps it.
        """
        global _instance, _default
        with _lock:
            if _instance is not None:
                return _instance
            if _default is None:
                # Upstream uses the holder-class idiom for lazy init;
                # here a plain ``if`` under the lock has the same
                # net effect because creation happens at most once.
                _default = DefaultFontMapper()
            _instance = _default
            return _instance

    @classmethod
    def set(cls, font_mapper: FontMapper | None) -> None:
        """Install ``font_mapper`` as the active singleton.

        Mirrors upstream ``static synchronized void set(FontMapper)``.
        Passing ``None`` clears any override — the next call to
        :meth:`instance` will fall back to (and cache) a fresh
        :class:`DefaultFontMapper`. The deviation from upstream
        (Java throws ``NullPointerException`` later if you set ``null``)
        is intentional: a clean way to reset between tests is too
        useful to give up.
        """
        global _instance, _default
        if font_mapper is not None and not isinstance(font_mapper, FontMapper):
            raise TypeError(
                f"FontMappers.set expects a FontMapper instance, "
                f"got {type(font_mapper).__name__}"
            )
        with _lock:
            _instance = font_mapper
            if font_mapper is None:
                # Drop the cached default too so the next ``instance()``
                # builds a fresh one — keeps tests deterministic.
                _default = None

    # ---------- camelCase shim for porting parity ----------

    # Upstream Java method names — kept live for ported call sites.
    @classmethod
    def setMapper(cls, font_mapper: FontMapper | None) -> None:  # noqa: N802
        cls.set(font_mapper)

    # ---------- test-friendly extension ----------

    @classmethod
    def reset(cls) -> None:
        """Clear the override so the default mapper is rebuilt next time.

        Pypdfbox extension (no upstream equivalent — see CHANGES). Tests
        use this between cases to avoid singleton bleed-over.
        """
        cls.set(None)


__all__ = ["FontMappers"]
