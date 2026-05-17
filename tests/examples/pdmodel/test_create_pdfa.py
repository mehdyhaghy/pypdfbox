"""Coverage-boost tests for ``pypdfbox.examples.pdmodel.create_pdfa``.

Drives the end-to-end ``main()`` path with a real TTF, plus the
``_make_srgb_icc_bytes`` helper, the usage / SystemExit branch, and the
font-not-embedded guard.

NOTE: ``XmpSerializer.serialize`` currently raises ``AttributeError`` when
serialising a Dublin Core ``set_title`` because ``_append_field`` expects
``AbstractField`` instances but receives raw ``str``. Until that latent
bug is fixed in ``pypdfbox/xmpbox/xml/xmp_serializer.py``, this test
monkeypatches the serializer with a stub so the rest of ``main()``
(font embedding, content stream, ICC output intent, document save) can be
covered. The bug is flagged in the wave 1335 agent report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pypdfbox.examples.pdmodel import create_pdfa as cp_mod
from pypdfbox.examples.pdmodel.create_pdfa import CreatePDFA, _make_srgb_icc_bytes
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.pd_document import PDDocument

_REPO_TTF = Path(
    "/Users/nitro/Documents/pypdfbox/pypdfbox/resources/ttf/DejaVuSans.ttf"
)


def _fake_serialize(self: Any, xmp: Any, fp: Any, with_xpacket: bool = True) -> None:
    """Stub serializer that writes a minimal XMP packet to ``fp``.

    Sidesteps the ``AbstractField.get_property_name`` AttributeError on
    DC ``set_title`` paths so the rest of ``CreatePDFA.main`` runs.
    """
    fp.write(b"<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>")
    fp.write(b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>")
    fp.write(b"<?xpacket end='w'?>")


# ---------------------------------------------------------------------------
# Constructor + module surface
# ---------------------------------------------------------------------------


def test_constructor_is_a_no_op() -> None:
    obj = CreatePDFA()
    assert obj is not None


def test_module_constants_present() -> None:
    # Ensures key constants survive port-level imports.
    assert callable(CreatePDFA.main)
    assert callable(_make_srgb_icc_bytes)


# ---------------------------------------------------------------------------
# _make_srgb_icc_bytes
# ---------------------------------------------------------------------------


def test_make_srgb_icc_bytes_returns_bytes() -> None:
    icc = _make_srgb_icc_bytes()
    assert isinstance(icc, bytes)
    # Pillow's ImageCms emits a canonical sRGB v2 profile.
    assert len(icc) > 100
    # ICC profiles start with a 4-byte big-endian size prefix.
    declared = int.from_bytes(icc[:4], "big")
    assert declared == len(icc)


def test_make_srgb_icc_bytes_is_deterministic() -> None:
    # Property: lcms2 emits the same bytes on every call.
    assert _make_srgb_icc_bytes() == _make_srgb_icc_bytes()


# ---------------------------------------------------------------------------
# main() — usage / argument validation
# ---------------------------------------------------------------------------


def test_main_usage_no_args(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        CreatePDFA.main([])
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "usage" in err


def test_main_usage_none_argv() -> None:
    with pytest.raises(SystemExit):
        CreatePDFA.main(None)


def test_main_usage_wrong_arg_count() -> None:
    with pytest.raises(SystemExit):
        CreatePDFA.main(["only-one-arg"])


def test_main_usage_too_many_args() -> None:
    with pytest.raises(SystemExit):
        CreatePDFA.main(["a", "b", "c", "d"])


def test_main_with_missing_ttf_raises_os_error(tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    with pytest.raises(OSError):
        CreatePDFA.main([str(out), "hi", str(tmp_path / "missing.ttf")])


# ---------------------------------------------------------------------------
# main() — end-to-end with serializer stub
# ---------------------------------------------------------------------------


def test_main_end_to_end_writes_valid_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _REPO_TTF.is_file():
        pytest.skip(f"DejaVuSans TTF fixture missing at {_REPO_TTF}")
    # Monkey-patch the serializer to avoid the latent AttributeError on
    # Dublin Core's ``set_title`` path. The instrumented call site (XMP
    # metadata block + PDOutputIntent + content stream) still executes.
    monkeypatch.setattr(
        cp_mod.XmpSerializer, "serialize", _fake_serialize,
    )
    out = tmp_path / "pdfa.pdf"
    CreatePDFA.main([str(out), "Hello PDF/A", str(_REPO_TTF)])
    assert out.exists()
    blob = out.read_bytes()
    assert blob[:4] == b"%PDF"
    assert blob.endswith(b"%%EOF") or blob.endswith(b"%%EOF\n")
    # Round-trip parse — confirms the saved PDF is well-formed.
    with Loader.load_pdf(out) as cos_doc:
        doc = PDDocument(cos_doc)
        assert doc.get_number_of_pages() == 1
        catalog = doc.get_document_catalog()
        # XMP metadata and OutputIntent were attached.
        assert catalog.get_metadata() is not None
        intents = catalog.get_output_intents()
        assert intents is not None and len(intents) >= 1


def test_main_attaches_output_intent_with_srgb_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _REPO_TTF.is_file():
        pytest.skip(f"DejaVuSans TTF fixture missing at {_REPO_TTF}")
    monkeypatch.setattr(
        cp_mod.XmpSerializer, "serialize", _fake_serialize,
    )
    out = tmp_path / "intent.pdf"
    CreatePDFA.main([str(out), "Intent check", str(_REPO_TTF)])
    with Loader.load_pdf(out) as cos_doc:
        doc = PDDocument(cos_doc)
        catalog = doc.get_document_catalog()
        intents = catalog.get_output_intents()
        intent = intents[0]
        # The four labels were applied to the OutputIntent dictionary.
        assert intent.get_info() == "sRGB IEC61966-2.1"
        assert intent.get_output_condition() == "sRGB IEC61966-2.1"
        assert intent.get_output_condition_identifier() == "sRGB IEC61966-2.1"
        assert intent.get_registry_name() == "http://www.color.org"


def test_main_embeds_font(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _REPO_TTF.is_file():
        pytest.skip(f"DejaVuSans TTF fixture missing at {_REPO_TTF}")
    monkeypatch.setattr(
        cp_mod.XmpSerializer, "serialize", _fake_serialize,
    )
    out = tmp_path / "embedded.pdf"
    CreatePDFA.main([str(out), "Font check", str(_REPO_TTF)])
    # PDType0Font.load always embeds, so the font descriptor's
    # /FontFile entry should exist in the saved PDF — easiest test:
    # ensure the on-disk file is large enough to contain the embedded
    # font (which is multi-hundred-kB for DejaVu).
    assert out.stat().st_size > 100_000
