"""Wave 1403 branch round-out for ``print_urls``.

Closes ``73->exit``: when the loaded ``cos_doc`` exposes no ``close``
attribute, the ``if close is not None`` guard in the ``finally`` block takes
its False arc and ``main`` returns without calling close.
"""

from __future__ import annotations

from pypdfbox.examples.pdmodel.print_urls import PrintURLs


class _CloselessCosDoc:
    """A COS-document stand-in with **no** ``close`` method, driving the
    ``getattr(cos_doc, "close", None) is None`` defensive arc."""

    # Intentionally no ``close`` attribute.

    def get_pages(self):  # used by PDDocument wrapper below
        return []


def test_main_finally_skips_close_when_absent(monkeypatch) -> None:
    closeless = _CloselessCosDoc()

    monkeypatch.setattr(
        "pypdfbox.loader.Loader.load_pdf",
        staticmethod(lambda _path: closeless),
    )

    class _Doc:
        def __init__(self, cos_doc) -> None:
            self._cos = cos_doc

        def get_pages(self):
            return []

    monkeypatch.setattr(
        "pypdfbox.pdmodel.pd_document.PDDocument", _Doc,
    )

    # No pages → no annotation work; the finally clause then finds no
    # ``close`` attribute and returns cleanly (73->exit).
    PrintURLs.main(["some.pdf"])
