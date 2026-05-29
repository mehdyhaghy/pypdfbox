"""Live PDFBox differential parity for catalog (/Root) recovery.

Apache PDFBox's ``COSParser.retrieveTrailer`` fires a brute-force trailer
rebuild when a cleanly-parsed xref's trailer carries NO ``/Root`` item — the
key itself is *absent* (checked raw via ``getItem``, not resolved). The rebuild
(``BruteForceParser.rebuildTrailer``) re-scans the body for ``n g obj``
definitions, and the FIRST object that advertises ``/Type /Catalog`` becomes
the recovered ``/Root``; the trailer is repaired and the document opens with
its real page count intact.

A trailer whose ``/Root`` key IS present but DANGLES is NOT rebuilt — upstream
lets that surface at ``PDFParser.initialParse``:

* ``badroot`` — ``/Root 99 0 R`` references a non-existent object;
  ``trailer.getCOSDictionary(ROOT)`` is null → "Missing root object
  specification in trailer." → ``PARSE_FAIL``.
* ``noncatalog_root`` — ``/Root`` points at the ``/Pages`` node (a real dict,
  but not a catalog and with no ``/Pages`` tree of its own); ``checkPages``
  raises "Page tree root must be a dictionary" → ``PARSE_FAIL``.

This module hand-builds a valid 8-object, 2-page PDF (real Helvetica text on
each page) with a traditional xref table + trailer + ``startxref``, then
rewrites only the trailer's ``/Root`` field four ways. The
:class:`RootRecoveryProbe` Java oracle drives the full ``Loader.loadPDF`` path
(which calls ``initialParse``) and emits a canonical JSON fingerprint —
recovered catalog object key, page count, ``/Root`` /``/Info`` presence, xref
object count, and ``PDFTextStripper`` text — and pypdfbox must reproduce it
(success vs ``{"status":"PARSE_FAIL"}``) byte-for-byte.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.io import RandomAccessReadBufferedFile
from pypdfbox.pdfparser import PDFParser
from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

# ---- valid multi-object PDF (built via pypdfbox-compatible byte assembly) ----

_BODY1 = b"BT /F1 24 Tf 72 700 Td (Hello World) Tj ET"
_BODY2 = b"BT /F1 18 Tf 72 700 Td (Page Two Text) Tj ET"


def _build_pdf(root_field: bytes) -> bytes:
    """Assemble a well-formed 8-object, 2-page PDF whose trailer carries
    ``root_field`` (e.g. ``b"/Root 1 0 R "``) plus ``/Info 8 0 R``. Pass an
    empty ``root_field`` to omit ``/Root`` entirely."""
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 7 0 R >> >> /Contents 5 0 R >>"
        ),
        4: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>"
        ),
        5: b"<< /Length %d >>\nstream\n%s\nendstream" % (len(_BODY1), _BODY1),
        6: b"<< /Length %d >>\nstream\n%s\nendstream" % (len(_BODY2), _BODY2),
        7: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        8: b"<< /Producer (pypdfbox-test) /Title (Recovery Fixture) >>",
    }
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for n in sorted(objs):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"
    xref_off = len(out)
    n_objs = max(objs) + 1
    out += b"xref\n0 %d\n" % n_objs
    out += b"0000000000 65535 f \n"
    for n in range(1, n_objs):
        out += b"%010d 00000 n \n" % offsets[n]
    out += b"trailer\n<< /Size %d %s/Info 8 0 R >>\n" % (n_objs, root_field)
    out += b"startxref\n%d\n%%%%EOF" % xref_off
    return bytes(out)


# ---- the four /Root states ----

_CASES: dict[str, bytes] = {
    # Control: /Root points at the real catalog — no recovery needed.
    "clean": _build_pdf(b"/Root 1 0 R "),
    # /Root key absent: lenient rebuild scans for /Type /Catalog → obj 1.
    "noroot": _build_pdf(b""),
    # /Root present but dangling (obj 99 missing): NOT rebuilt → Missing root.
    "badroot": _build_pdf(b"/Root 99 0 R "),
    # /Root present, resolves to the /Pages node (not a catalog, no /Pages
    # tree of its own): NOT rebuilt → checkPages "Page tree root must be a
    # dictionary".
    "noncatalog_root": _build_pdf(b"/Root 2 0 R "),
}


# ---- pypdfbox-side fingerprint (mirrors RootRecoveryProbe's JSON) ----


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")


def _pypdfbox_dump(path: str) -> str:
    """Reproduce the JSON fingerprint :class:`RootRecoveryProbe` emits.

    Drives the full PDFBox-equivalent load path: ``PDFParser.parse()`` then
    ``initial_parse()`` (which validates ``/Root`` and the page tree), so a
    dangling / non-catalog ``/Root`` surfaces the same load-time failure that
    upstream ``Loader.loadPDF`` produces. Returns the canonical
    ``{"status":"PARSE_FAIL"}`` JSON on any throw."""
    access = RandomAccessReadBufferedFile(path)
    cos = None
    try:
        parser = PDFParser(access)
        cos = parser.parse()
        parser.initial_parse()
        pd = PDDocument(cos)
        pages = pd.get_number_of_pages()
        trailer = cos.get_trailer()
        root_obj = (
            trailer.get_dictionary_object(COSName.ROOT)
            if trailer is not None
            else None
        )
        root = isinstance(root_obj, COSDictionary)
        raw_root = trailer.get_item(COSName.ROOT) if trailer is not None else None
        if isinstance(raw_root, COSObject):
            catalog = f"{raw_root.object_number} {raw_root.generation_number}"
        elif isinstance(raw_root, COSDictionary):
            catalog = "direct"
        else:
            catalog = "absent"
        info = (
            trailer is not None
            and trailer.get_dictionary_object(COSName.get_pdf_name("Info"))
            is not None
        )
        text = PDFTextStripper().get_text(pd)
        payload = {
            "catalog": catalog,
            "info": "present" if info else "absent",
            "objects": len(cos.get_xref_table()),
            "pages": pages,
            "root": "present" if root else "absent",
            "text": _escape(text),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except Exception:
        return json.dumps(
            {"status": "PARSE_FAIL"}, sort_keys=True, separators=(",", ":")
        )
    finally:
        if cos is not None:
            cos.close()
        access.close()


@requires_oracle
@pytest.mark.parametrize("name", list(_CASES), ids=list(_CASES))
def test_root_recovery_matches_pdfbox(name: str, tmp_path: Path) -> None:
    """pypdfbox must reach the SAME recovery decision as PDFBox 3.0.7 for
    each ``/Root`` state — catalog object key + page count when recovered,
    or an identical ``PARSE_FAIL`` when upstream refuses to recover."""
    pdf_path = tmp_path / f"{name}.pdf"
    pdf_path.write_bytes(_CASES[name])
    java = run_probe_text("RootRecoveryProbe", str(pdf_path))
    py = _pypdfbox_dump(str(pdf_path))
    assert json.loads(py) == json.loads(java)


@requires_oracle
def test_missing_root_recovers_catalog_by_scan(tmp_path: Path) -> None:
    """Regression pin for the core surface: a trailer with NO ``/Root``
    recovers the catalog (obj 1) by the brute-force ``/Type /Catalog`` scan,
    yielding the full 2-page document — identical to PDFBox."""
    pdf_path = tmp_path / "noroot.pdf"
    pdf_path.write_bytes(_CASES["noroot"])
    java = run_probe_text("RootRecoveryProbe", str(pdf_path))
    parsed = json.loads(java)
    assert parsed == {
        "catalog": "1 0",
        "info": "present",
        "objects": 8,
        "pages": 2,
        "root": "present",
        "text": "Hello World\\nPage Two Text\\n",
    }
    assert json.loads(_pypdfbox_dump(str(pdf_path))) == parsed
