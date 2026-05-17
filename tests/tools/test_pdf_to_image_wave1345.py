"""Wave 1345 — coverage round-out for :class:`PDFToImage`.

Targets the remaining uncovered lines:

* the ``output_prefix is None`` fallback that derives the prefix from
  ``self.infile`` (line 44);
* the ``(AttributeError, NotImplementedError)`` rescue around the
  acro-form ``refresh_appearances`` step (lines 66-68);
* the ``if not success:`` branch that fires when
  :meth:`ImageIOUtil.write_image` returns ``False`` (lines 97-100);
* the ``__name__ == '__main__'`` invocation as a module (line 158).
"""

from __future__ import annotations

import contextlib
import runpy
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from pypdfbox.loader import Loader as RealLoader
from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import pdf_to_image

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
ROT0 = FIXTURES / "multipdf" / "rot0.pdf"


class _PDLoaderShim:
    """Wraps ``Loader.load_pdf`` so it yields a :class:`PDDocument` — the
    PD-layer methods the class port reaches into are only available on
    the wrapper, not on the raw :class:`COSDocument`."""

    @staticmethod
    @contextlib.contextmanager
    def load_pdf(source: Any, password: Any = None) -> Iterator[PDDocument]:
        if isinstance(password, str) and password == "":
            password = None
        cos_doc = RealLoader.load_pdf(source, password)
        pd = PDDocument(cos_doc)
        try:
            yield pd
        finally:
            pd.close()


class _FakeRenderer:
    def __init__(self, document: Any) -> None:
        self.document = document

    def render_image_with_dpi(
        self, page_index: int, dpi: int, image_type: Any
    ) -> Image.Image:
        return Image.new("RGB", (4, 4), "white")


@pytest.fixture
def patched_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> type[_PDLoaderShim]:
    monkeypatch.setattr(pdf_to_image, "Loader", _PDLoaderShim)
    return _PDLoaderShim


# --------------------------------------------------------------------------
# Line 44 — output_prefix defaults to the infile stem when unset.
# --------------------------------------------------------------------------
def test_default_output_prefix_derives_from_infile(
    patched_loader: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A copy of rot0.pdf is dropped in tmp_path and the runner is
    invoked WITHOUT ``-prefix``; the derived ``<stem>-1.png`` file must
    land next to the input."""
    monkeypatch.setattr(pdf_to_image, "PDFRenderer", _FakeRenderer)
    src = tmp_path / "derived.pdf"
    src.write_bytes(ROT0.read_bytes())
    rc = pdf_to_image.PDFToImage.main([
        "-i", str(src),
        "-format", "png",
        "-dpi", "36",
    ])
    assert rc == 0
    assert (tmp_path / "derived-1.png").exists()


# --------------------------------------------------------------------------
# Lines 66-68 — refresh_appearances rescue.
# --------------------------------------------------------------------------
def test_refresh_appearances_attribute_error_is_swallowed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When the acro-form refresh raises ``AttributeError``, the runner
    swallows it and proceeds to render."""

    class _FormThatExplodes:
        def get_need_appearances(self) -> bool:
            return True

        def refresh_appearances(self) -> None:
            raise AttributeError("not wired")

    class _CatalogWithForm:
        def get_acro_form(self) -> _FormThatExplodes:
            return _FormThatExplodes()

    class _FakeDoc:
        def __init__(self) -> None:
            self._closed = False

        def get_document_catalog(self) -> _CatalogWithForm:
            return _CatalogWithForm()

        def get_pages(self) -> list[Any]:
            return []

        def get_number_of_pages(self) -> int:
            return 1

        def close(self) -> None:
            self._closed = True

        def __enter__(self) -> _FakeDoc:
            return self

        def __exit__(self, *_args: object) -> None:
            self.close()

    class _Loader:
        @staticmethod
        def load_pdf(source: Any, password: Any = None) -> _FakeDoc:
            return _FakeDoc()

    monkeypatch.setattr(pdf_to_image, "Loader", _Loader)
    monkeypatch.setattr(pdf_to_image, "PDFRenderer", _FakeRenderer)

    rc = pdf_to_image.PDFToImage.main([
        "-i", str(tmp_path / "any.pdf"),
        "-prefix", str(tmp_path / "out"),
        "-format", "png",
        "-dpi", "36",
    ])
    assert rc == 0
    assert (tmp_path / "out-1.png").exists()


def test_refresh_appearances_not_implemented_is_swallowed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The same rescue covers ``NotImplementedError``."""

    class _FormPartial:
        def get_need_appearances(self) -> bool:
            return True

        def refresh_appearances(self) -> None:
            raise NotImplementedError("port pending")

    class _Catalog:
        def get_acro_form(self) -> _FormPartial:
            return _FormPartial()

    class _Doc:
        def get_document_catalog(self) -> _Catalog:
            return _Catalog()

        def get_pages(self) -> list[Any]:
            return []

        def get_number_of_pages(self) -> int:
            return 1

        def close(self) -> None: ...

        def __enter__(self) -> _Doc:
            return self

        def __exit__(self, *_args: object) -> None: ...

    class _Loader:
        @staticmethod
        def load_pdf(source: Any, password: Any = None) -> _Doc:
            return _Doc()

    monkeypatch.setattr(pdf_to_image, "Loader", _Loader)
    monkeypatch.setattr(pdf_to_image, "PDFRenderer", _FakeRenderer)

    rc = pdf_to_image.PDFToImage.main([
        "-i", str(tmp_path / "x.pdf"),
        "-prefix", str(tmp_path / "out"),
        "-format", "png",
        "-dpi", "36",
    ])
    assert rc == 0


# --------------------------------------------------------------------------
# Lines 97-100 — write_image returning False trips the failure return.
# --------------------------------------------------------------------------
def test_writer_failure_returns_1(
    patched_loader: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When :meth:`ImageIOUtil.write_image` returns ``False`` for every
    page, the runner emits the 'no writer found' diagnostic and exits 1."""
    monkeypatch.setattr(pdf_to_image, "PDFRenderer", _FakeRenderer)

    class _ImageIOUtilFails:
        @staticmethod
        def get_writer_format_names() -> list[str]:
            return ["png", "jpg", "tiff"]

        @staticmethod
        def write_image(image, filename, dpi, quality) -> bool:  # noqa: ANN001
            return False

    monkeypatch.setattr(pdf_to_image, "ImageIOUtil", _ImageIOUtilFails)

    prefix = tmp_path / "out"
    rc = pdf_to_image.PDFToImage.main([
        "-i", str(ROT0),
        "-prefix", str(prefix),
        "-format", "png",
        "-dpi", "36",
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "no writer found" in err


# --------------------------------------------------------------------------
# Line 158 — module-level ``if __name__ == '__main__':`` dispatch.
# --------------------------------------------------------------------------
@pytest.mark.filterwarnings(
    "ignore:.*found in sys.modules after import.*:RuntimeWarning"
)
def test_module_entrypoint_dispatches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Run the module via ``runpy`` so the ``__main__`` branch evaluates
    (line 157-158). ``runpy.run_module(..., run_name='__main__')`` re-
    executes the module body under that name; with a non-existent input
    file the runner returns 4 — which is fine, we only need ``sys.exit``
    to fire so coverage records line 158."""
    monkeypatch.setattr(
        "sys.argv", ["pdf_to_image", "-i", str(tmp_path / "any.pdf")],
    )
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module(
            "pypdfbox.tools.pdf_to_image",
            run_name="__main__",
        )
    # Any integer exit code proves the dispatch line ran.
    assert isinstance(excinfo.value.code, int)
