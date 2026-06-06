"""Visible-signature design properties (placement, image, geometry).

Mirrors ``org.apache.pdfbox.pdmodel.interactive.digitalsignature.visible.PDVisibleSignDesigner``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/visible/PDVisibleSignDesigner.java``).

Setters use the unprefixed name (e.g. ``signer_name`` instead of
``set_signer_name``) and return ``self`` for chaining, matching the
upstream fluent shape.
"""

from __future__ import annotations

import copy
import struct
from pathlib import Path
from typing import Any, BinaryIO

_AFFINE_COMPONENTS = ("m00", "m10", "m01", "m11", "m02", "m12")


def _f32(value: float) -> float:
    """Narrow ``value`` to IEEE-754 single precision.

    Upstream stores ``imageWidth`` / ``imageHeight`` as ``java.lang.Float``
    (32-bit), so the arithmetic in ``zoom`` and the ``(int) …`` casts that
    populate ``formatterRectangleParameters`` are single-precision. The
    Python port computes in 64-bit; narrowing the stored dimensions to
    float32 keeps the integer casts bit-exact with Java.
    """
    return struct.unpack("f", struct.pack("f", value))[0]


def _copy_affine_transform(at: Any) -> Any:
    """Return a defensive copy of an affine transform.

    Mirrors upstream's ``new AffineTransform(affineTransform)`` copy. See
    :meth:`PDVisibleSignDesigner.transform` for the three-tier rationale.
    """
    if at is None:
        return at
    if all(hasattr(at, component) for component in _AFFINE_COMPONENTS):
        return _IdentityAffineTransform(
            at.m00, at.m10, at.m01, at.m11, at.m02, at.m12
        )
    try:
        return copy.copy(at)
    except Exception:  # pragma: no cover - opaque, uncopyable handle
        return at


class PDVisibleSignDesigner:
    """Visible-signature design properties.

    The Java constructors come in six flavours (file path / random-access
    source / pre-parsed ``PDDocument`` × ``InputStream`` image /
    ``BufferedImage``). The Python port collapses them onto two helper
    routes — :meth:`_calculate_page_size_from_file` and
    :meth:`_calculate_page_size_from_document` — and accepts any of the
    upstream argument shapes through ``__init__`` overloads handled by
    type dispatch.
    """

    def __init__(
        self,
        document: Any = None,
        image_stream: BinaryIO | bytes | bytearray | None = None,
        page: int = 1,
    ) -> None:
        self._image_width: float | None = None
        self._image_height: float | None = None
        self._x_axis: float = 0.0
        self._y_axis: float = 0.0
        self._page_height: float = 0.0
        self._page_width: float = 0.0
        self._image: Any = None
        self._signature_field_name: str = "sig"
        self._formatter_rectangle_parameters: list[int] = [0, 0, 100, 50]
        self._affine_transform: Any = _IdentityAffineTransform()
        self._image_size_in_percents: float = 0.0
        self._rotation: int = 0

        if image_stream is not None:
            self._read_image_stream(image_stream)
        if isinstance(document, (str, Path)):
            self._calculate_page_size_from_file(str(document), page)
        elif document is not None:
            self._calculate_page_size_from_document(document, page)

    # ------------------------------------------------------------------ image

    def read_image_stream(
        self, image_stream: BinaryIO | bytes | bytearray
    ) -> None:
        """Mirrors upstream ``readImageStream`` (Java line 444). We hold the
        raw bytes — actual decoding is deferred to whoever consumes
        :attr:`image`."""
        if isinstance(image_stream, (bytes, bytearray)):
            self._image = bytes(image_stream)
        else:
            self._image = image_stream.read()

    # Backwards-compatible private alias.
    _read_image_stream = read_image_stream

    def set_image(self, image: Any) -> None:
        """Mirrors upstream ``setImage(BufferedImage)`` (Java line 453).

        Stores the supplied (already-decoded) image object and records its
        dimensions when available. Upstream also writes the integer width
        and height into ``formatterRectangleParameters[2]`` / ``[3]``.
        """
        self._image = image
        width = getattr(image, "get_width", None) or getattr(image, "width", None)
        height = getattr(image, "get_height", None) or getattr(image, "height", None)
        try:
            if width is not None:
                self._image_width = _f32(
                    float(width() if callable(width) else width)
                )
                self._formatter_rectangle_parameters[2] = int(self._image_width)
            if height is not None:
                self._image_height = _f32(
                    float(height() if callable(height) else height)
                )
                self._formatter_rectangle_parameters[3] = int(self._image_height)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            pass

    def calculate_page_size_from_file(self, filename: str, page: int) -> None:
        """Mirrors upstream ``calculatePageSizeFromFile`` (Java line 168).

        Page-size lookup hook — upstream parses the PDF; the Python port is
        permissive — if anything goes wrong the dimensions stay zero and
        the caller is expected to override via :meth:`page_width` /
        :meth:`height`.
        """
        try:
            from pypdfbox.loader import load_pdf  # type: ignore[import-not-found]
        except ImportError:  # pragma: no cover - depends on loader availability
            return
        try:
            doc = load_pdf(filename)
            self.calculate_page_size(doc, page)
        except Exception:  # pragma: no cover - defensive parity stub
            return

    # Backwards-compatible private alias.
    _calculate_page_size_from_file = calculate_page_size_from_file

    def calculate_page_size_from_random_access_read(
        self, document_source: Any, page: int
    ) -> None:
        """Mirrors upstream ``calculatePageSizeFromRandomAccessRead``
        (Java line 177).

        Upstream wraps the random-access source in a ``PDFParser`` and then
        delegates to :meth:`calculate_page_size`. The Python port accepts
        any object that exposes ``read()`` (e.g. a ``RandomAccessRead``
        instance) and defers to the loader when available.
        """
        try:
            from pypdfbox.loader import load_pdf  # type: ignore[import-not-found]
        except ImportError:  # pragma: no cover - depends on loader availability
            return
        try:
            doc = load_pdf(document_source)
            self.calculate_page_size(doc, page)
        except Exception:  # pragma: no cover - defensive parity stub
            return

    def calculate_page_size(self, document: Any, page: int) -> None:
        """Mirrors upstream ``calculatePageSize(PDDocument, int)``
        (Java line 195).

        Upstream raises ``IllegalArgumentException`` when ``page < 1``, then
        records the media-box dimensions and sets ``imageSizeInPercents`` to
        100 and ``rotation`` to ``page.getRotation() % 360``.
        """
        if page < 1:
            raise ValueError(f"First page of pdf is 1, not {page}")
        try:
            pages = document.get_pages()
            target = pages[page - 1]
            box = target.get_media_box()
            self._page_height = float(box.get_height())
            self._page_width = float(box.get_width())
            self._image_size_in_percents = 100.0
            rotation = getattr(target, "get_rotation", None)
            if rotation is not None:
                self._rotation = int(rotation()) % 360
        except ValueError:
            raise
        except Exception:  # pragma: no cover - defensive parity stub
            return

    # Backwards-compatible private alias.
    _calculate_page_size_from_document = calculate_page_size

    # ------------------------------------------------------ rotation handling

    def adjust_for_rotation(self) -> PDVisibleSignDesigner:
        """Mirrors ``adjustForRotation`` (Java line 216).

        Rotates the placement coordinates and builds the corresponding
        ``AffineTransform`` for page rotations of 90/180/270 degrees. The
        90 and 270 cases additionally swap ``imageWidth`` and
        ``imageHeight``. Rotation 0 (and any other value) is a no-op.
        """
        width = self._image_width if self._image_width is not None else 0.0
        height = self._image_height if self._image_height is not None else 0.0
        if self._rotation == 90:
            temp = self._y_axis
            self._y_axis = self._page_height - self._x_axis - width
            self._x_axis = temp
            self._affine_transform = _IdentityAffineTransform(
                0,
                height / width if width else 0.0,
                -width / height if height else 0.0,
                0,
                width,
                0,
            )
            self._image_height, self._image_width = width, height
        elif self._rotation == 180:
            new_x = self._page_width - self._x_axis - width
            new_y = self._page_height - self._y_axis - height
            self._x_axis = new_x
            self._y_axis = new_y
            self._affine_transform = _IdentityAffineTransform(
                -1, 0, 0, -1, width, height
            )
        elif self._rotation == 270:
            temp = self._x_axis
            self._x_axis = self._page_width - self._y_axis - height
            self._y_axis = temp
            self._affine_transform = _IdentityAffineTransform(
                0,
                -height / width if width else 0.0,
                width / height if height else 0.0,
                0,
                0,
                height,
            )
            self._image_height, self._image_width = width, height
        return self

    def signature_image(self, path: str) -> PDVisibleSignDesigner:
        """Mirrors ``signatureImage`` (Java line 270)."""
        with Path(path).open("rb") as handle:
            self.read_image_stream(handle)
        return self

    def zoom(self, percent: float) -> PDVisibleSignDesigner:
        """Mirrors ``zoom`` (Java line 285).

        Scales width and height by ``percent`` and writes the resulting
        integer dimensions into ``formatterRectangleParameters[2]`` / ``[3]``.
        """
        # Java's ``percent`` parameter is a 32-bit ``float``; narrow it so the
        # whole arithmetic chain is single-precision (matches Java bit-exactly).
        percent = _f32(percent)
        if self._image_height is not None:
            # Mirror Java's float32 ``Float`` arithmetic: each intermediate is
            # narrowed so the ``(int) imageHeight.floatValue()`` cast that
            # populates the formatter rectangle matches Java bit-for-bit.
            self._image_height = _f32(
                self._image_height + _f32(_f32(self._image_height * percent) / 100)
            )
            self._formatter_rectangle_parameters[3] = int(self._image_height)
        if self._image_width is not None:
            self._image_width = _f32(
                self._image_width + _f32(_f32(self._image_width * percent) / 100)
            )
            self._formatter_rectangle_parameters[2] = int(self._image_width)
        return self

    def coordinates(self, x: float, y: float) -> PDVisibleSignDesigner:
        """Mirrors ``coordinates`` (Java line 300)."""
        self._x_axis = x
        self._y_axis = y
        return self

    def get_x_axis(self) -> float:
        """Mirrors ``getxAxis`` (Java line 311) — snake_case'd per CLAUDE.md."""
        return self._x_axis

    # Parity alias: upstream's ``getxAxis`` snake-cases to ``getx_axis``
    # under the parity scanner's rule (lowercase-then-uppercase boundary).
    def getx_axis(self) -> float:
        """Mirrors ``getxAxis`` (Java line 311) — alias matching the
        scanner-derived snake_case spelling."""
        return self._x_axis

    def x_axis(self, x_axis: float) -> PDVisibleSignDesigner:
        self._x_axis = x_axis
        return self

    def get_y_axis(self) -> float:
        return self._y_axis

    # Parity alias: upstream's ``getyAxis`` snake-cases to ``gety_axis``.
    def gety_axis(self) -> float:
        """Mirrors ``getyAxis`` (Java line 331) — alias matching the
        scanner-derived snake_case spelling."""
        return self._y_axis

    def y_axis(self, y_axis: float) -> PDVisibleSignDesigner:
        self._y_axis = y_axis
        return self

    def get_width(self) -> float | None:
        return self._image_width

    def width(self, width: float) -> PDVisibleSignDesigner:
        """Mirrors ``width(float)`` (Java line 360). Also writes the integer
        width into ``formatterRectangleParameters[2]``."""
        self._image_width = _f32(width)
        self._formatter_rectangle_parameters[2] = int(self._image_width)
        return self

    def get_height(self) -> float | None:
        return self._image_height

    def height(self, height: float) -> PDVisibleSignDesigner:
        """Mirrors ``height(float)`` (Java line 381). Also writes the integer
        height into ``formatterRectangleParameters[3]``."""
        self._image_height = _f32(height)
        self._formatter_rectangle_parameters[3] = int(self._image_height)
        return self

    def get_template_height(self) -> float:
        """Mirrors ``getTemplateHeight`` (Java line 393)."""
        return self._page_height

    def page_height(self, template_height: float) -> PDVisibleSignDesigner:
        """Mirrors ``pageHeight(float)`` (Java line 403) — sets the template
        height used when computing the visible-signature rectangle."""
        self._page_height = template_height
        return self

    def get_signature_field_name(self) -> str:
        return self._signature_field_name

    def signature_field_name(
        self, signature_field_name: str
    ) -> PDVisibleSignDesigner:
        self._signature_field_name = signature_field_name
        return self

    def get_image(self) -> Any:
        return self._image

    def get_transform(self) -> Any:
        return self._affine_transform

    def transform(self, affine_transform: Any) -> PDVisibleSignDesigner:
        """Mirrors ``transform(AffineTransform)`` (Java line 477).

        Upstream stores a *defensive copy* — ``this.affineTransform = new
        AffineTransform(affineTransform)`` — so a later mutation of the
        caller's object cannot leak into the designer. We reproduce that
        copy semantics in three tiers, most-faithful first:

        1. If the supplied transform exposes the six ``java.awt.geom.
           AffineTransform`` components (``m00``/``m10``/``m01``/``m11``/
           ``m02``/``m12``), snapshot them into a fresh
           :class:`_IdentityAffineTransform`. This is upstream-faithful for
           every conforming transform (including the ones the rotation path
           builds) — the stored object is a distinct copy that holds the
           same matrix.
        2. Otherwise fall back to :func:`copy.copy` for any object that
           supports shallow copying.
        3. If the object is uncopyable (e.g. an opaque C handle), store it
           by reference. Python cannot defensively copy an arbitrary opaque
           object; this residual case is documented and affects only
           non-conforming externally-supplied transforms.
        """
        self._affine_transform = _copy_affine_transform(affine_transform)
        return self

    def get_formatter_rectangle_parameters(self) -> list[int]:
        return list(self._formatter_rectangle_parameters)

    def formatter_rectangle_parameters(
        self, params: list[int]
    ) -> PDVisibleSignDesigner:
        self._formatter_rectangle_parameters = list(params)
        return self

    def get_page_width(self) -> float:
        return self._page_width

    def page_width(self, page_width: float) -> PDVisibleSignDesigner:
        self._page_width = page_width
        return self

    def get_page_height(self) -> float:
        return self._page_height

    def get_image_size_in_percents(self) -> float:
        return self._image_size_in_percents

    def image_size_in_percents(self, image_size_in_percents: float) -> None:
        self._image_size_in_percents = image_size_in_percents

    def get_signature_text(self) -> str | None:
        """Mirrors ``getSignatureText`` (Java line 555). Upstream throws
        ``UnsupportedOperationException`` — parity is preserved here."""
        raise NotImplementedError("Signature text not supported")

    def signature_text(self, signature_text: str) -> PDVisibleSignDesigner:
        """Mirrors ``signatureText`` (Java line 565). Upstream throws
        ``UnsupportedOperationException`` — parity is preserved here."""
        raise NotImplementedError("Signature text not supported")


class _IdentityAffineTransform:
    """Minimal stand-in for ``java.awt.geom.AffineTransform``.

    The full affine transform is supplied by callers that have it (the
    rendering path attaches the real implementation); this stub is just
    enough to satisfy ``get_transform`` for headless visible-signature
    test scaffolds.
    """

    def __init__(
        self,
        m00: float = 1.0,
        m10: float = 0.0,
        m01: float = 0.0,
        m11: float = 1.0,
        m02: float = 0.0,
        m12: float = 0.0,
    ) -> None:
        # Argument order mirrors ``java.awt.geom.AffineTransform(m00, m10,
        # m01, m11, m02, m12)`` so the rotation cases in
        # :meth:`PDVisibleSignDesigner.adjust_for_rotation` map 1:1.
        self.m00 = float(m00)
        self.m10 = float(m10)
        self.m01 = float(m01)
        self.m11 = float(m11)
        self.m02 = float(m02)
        self.m12 = float(m12)


__all__ = ["PDVisibleSignDesigner"]
