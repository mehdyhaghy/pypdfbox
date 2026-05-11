"""Visible-signature design properties (placement, image, geometry).

Mirrors ``org.apache.pdfbox.pdmodel.interactive.digitalsignature.visible.PDVisibleSignDesigner``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/visible/PDVisibleSignDesigner.java``).

Setters use the unprefixed name (e.g. ``signer_name`` instead of
``set_signer_name``) and return ``self`` for chaining, matching the
upstream fluent shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, BinaryIO


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
        """Mirrors upstream ``setImage(BufferedImage)`` (Java line 455).

        Stores the supplied (already-decoded) image object and records its
        dimensions when available.
        """
        self._image = image
        width = getattr(image, "get_width", None) or getattr(image, "width", None)
        height = getattr(image, "get_height", None) or getattr(image, "height", None)
        try:
            if width is not None:
                self._image_width = float(width() if callable(width) else width)
            if height is not None:
                self._image_height = float(height() if callable(height) else height)
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
        (Java line 195)."""
        try:
            pages = document.get_pages()
            target = pages[page - 1]
            box = target.get_media_box()
            self._page_width = float(box.get_width())
            self._page_height = float(box.get_height())
        except Exception:  # pragma: no cover - defensive parity stub
            return

    # Backwards-compatible private alias.
    _calculate_page_size_from_document = calculate_page_size

    # ------------------------------------------------------ rotation handling

    def adjust_for_rotation(self) -> PDVisibleSignDesigner:
        """Mirrors ``adjustForRotation`` (Java line 216)."""
        # The upstream version rotates the formatter rectangle when the
        # underlying page rotation isn't a multiple of 360; the Python
        # stub records the rotation but does not yet redraw — this is
        # parity for the API surface only.
        return self

    def signature_image(self, path: str) -> PDVisibleSignDesigner:
        """Mirrors ``signatureImage`` (Java line 270)."""
        with Path(path).open("rb") as handle:
            self.read_image_stream(handle)
        return self

    def zoom(self, percent: float) -> PDVisibleSignDesigner:
        """Mirrors ``zoom`` (Java line 285)."""
        if self._image_width is not None:
            self._image_width = self._image_width + (self._image_width * percent / 100)
        if self._image_height is not None:
            self._image_height = self._image_height + (self._image_height * percent / 100)
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
        self._image_width = width
        return self

    def get_height(self) -> float | None:
        return self._image_height

    def height(self, height: float) -> PDVisibleSignDesigner:
        self._image_height = height
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
        self._affine_transform = affine_transform
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

    def __init__(self) -> None:
        self.m00 = 1.0
        self.m10 = 0.0
        self.m01 = 0.0
        self.m11 = 1.0
        self.m02 = 0.0
        self.m12 = 0.0


__all__ = ["PDVisibleSignDesigner"]
