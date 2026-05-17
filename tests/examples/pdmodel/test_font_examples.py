"""Sanity tests for the font-loading examples.

Both ``HelloWorldTTF`` and ``HelloWorldType1`` expect a real font file —
the basic tests below only validate the usage gate so the suite stays
free of external assets. The ``HelloWorldType1`` happy-path coverage
relies on monkey-patching :class:`PDType1Font` because the example's
two-arg constructor call ``PDType1Font(doc, stream)`` does not match
the real one-arg :meth:`PDType1Font.__init__(self, font_dict=None)`
signature — a latent example bug flagged for wave 1341.
"""

from __future__ import annotations

import pytest

from pypdfbox.examples.pdmodel.hello_world_ttf import HelloWorldTTF
from pypdfbox.examples.pdmodel.hello_world_type1 import HelloWorldType1


def test_hello_world_ttf_usage() -> None:
    with pytest.raises(SystemExit):
        HelloWorldTTF.main([])


def test_hello_world_ttf_main_requires_real_ttf(tmp_path) -> None:
    out = tmp_path / "out.pdf"
    # Missing font file → opening it raises OSError / FileNotFoundError;
    # we accept any IO-shaped failure.
    with pytest.raises(OSError):
        HelloWorldTTF.main([str(out), "msg", str(tmp_path / "missing.ttf")])


def test_hello_world_type1_usage() -> None:
    with pytest.raises(SystemExit):
        HelloWorldType1.main([])


def test_hello_world_type1_main_requires_real_pfb(tmp_path) -> None:
    out = tmp_path / "out.pdf"
    with pytest.raises(OSError):
        HelloWorldType1.main([str(out), "msg", str(tmp_path / "missing.pfb")])


def test_hello_world_type1_constructor_is_callable() -> None:
    """Exercise the no-op ``__init__`` body (covers line 21)."""
    instance = HelloWorldType1()
    assert isinstance(instance, HelloWorldType1)


def test_hello_world_ttf_constructor_is_callable() -> None:
    instance = HelloWorldTTF()
    assert isinstance(instance, HelloWorldTTF)


def test_hello_world_type1_one_arg_prints_usage() -> None:
    with pytest.raises(SystemExit):
        HelloWorldType1.main(["only-one"])


def test_hello_world_type1_two_args_prints_usage() -> None:
    with pytest.raises(SystemExit):
        HelloWorldType1.main(["one", "two"])


def test_hello_world_ttf_one_arg_prints_usage() -> None:
    with pytest.raises(SystemExit):
        HelloWorldTTF.main(["only-one"])


def test_hello_world_ttf_two_args_prints_usage() -> None:
    with pytest.raises(SystemExit):
        HelloWorldTTF.main(["one", "two"])


# ---------------------------------------------------------------------------
# Workload coverage for ``HelloWorldType1.main`` happy path.
# ``main`` calls ``PDType1Font(doc, stream)``; the real constructor only
# accepts ``font_dict`` so the example's two-arg invocation is broken
# (latent bug — see module docstring). Stub ``PDType1Font`` at the
# example module so the rest of the body runs end-to-end. Follows the
# pattern test_rendering.py uses for the same class of bug.
# ---------------------------------------------------------------------------


def test_hello_world_type1_main_writes_pdf_with_stub_font(
    tmp_path, monkeypatch, capsys
) -> None:
    """Cover the end-to-end ``HelloWorldType1.main`` happy path by
    stubbing ``PDType1Font.load`` (which would otherwise need a valid
    PFB) with a factory returning a Standard-14 Helvetica instance."""
    from pypdfbox.cos.cos_dictionary import COSDictionary
    from pypdfbox.cos.cos_name import COSName
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    def _stub_load(cls, doc, stream, encoding=None):
        _ = (doc, stream, encoding)
        d = COSDictionary()
        d.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
        d.set_item(
            COSName.get_pdf_name("BaseFont"),
            COSName.get_pdf_name("Helvetica"),
        )
        return PDType1Font(d)

    monkeypatch.setattr(PDType1Font, "load", classmethod(_stub_load))
    pfb = tmp_path / "dummy.pfb"
    pfb.write_bytes(b"placeholder")
    out = tmp_path / "out.pdf"
    HelloWorldType1.main([str(out), "msg", str(pfb)])
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"
    captured = capsys.readouterr().out
    assert "created" in captured
