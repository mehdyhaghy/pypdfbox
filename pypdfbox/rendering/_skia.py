"""Centralised import of the ``skia`` backend with an actionable error.

``skia-python``'s Linux wheel links the system OpenGL/EGL and fontconfig
libraries at load time. Minimal container images (``python:*-slim``,
distroless) and bare server installs omit those libraries, so a plain
``import skia`` there raises an opaque
``ImportError: libEGL.so.1: cannot open shared object file`` that gives
the user no hint about the fix. Routing the backend import through this
module translates that into a message naming the exact packages to
install. The non-rendering core never imports this module, so parsing,
writing, and text extraction keep working without the GL libraries.
"""

from __future__ import annotations

_SYSTEM_LIBS = ("libEGL", "libGLES", "libGLdispatch", "libGLX", "libGL", "libfontconfig")

try:
    import skia  # noqa: F401  (re-exported as pypdfbox.rendering._skia.skia)
except ImportError as exc:  # pragma: no cover - environment-specific
    _msg = str(exc)
    if any(lib in _msg for lib in _SYSTEM_LIBS):
        raise ImportError(
            "pypdfbox rendering needs the system OpenGL/EGL and fontconfig "
            "libraries that skia-python links at load time, but they are "
            f"missing from this environment ({_msg}).\n"
            "  Debian/Ubuntu (incl. python:*-slim):\n"
            "    apt-get update && apt-get install -y libegl1 libgl1 libgles2 libfontconfig1\n"
            "  Fedora/RHEL:\n"
            "    dnf install -y mesa-libEGL mesa-libGL mesa-libGLES fontconfig\n"
            "The non-rendering core (parsing, writing, text extraction) does "
            "not require these libraries. See docs/install.md, section "
            "'Minimal images and rendering'."
        ) from exc
    raise
