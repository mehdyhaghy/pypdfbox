"""Live PDFBox differential fuzz for the COS STREAM length / endstream
recovery core (pypdfbox parity wave 1517, agent A).

Targets the stream-body recovery surface — ``COSParser.parse_cos_stream`` /
``PDFParser._read_stream_body`` and the helpers they dispatch to
(``get_length`` / ``validate_stream_length`` /
``read_until_end_stream`` + ``EndstreamFilterStream``) — as actually reached
from a real document body parse (``COSParser`` resolving an indirect stream
object lazily). It exercises: wrong / indirect / missing / negative
``/Length``; absent or misplaced ``endstream`` / ``endobj``; brute-force
endstream scanning; trailing-whitespace handling before ``endstream``; and
length-vs-actual mismatch recovery.

Driven file-based (same pattern as ``CosObjectParseFuzzProbe`` /
``ResourcesLookupFuzzProbe``): for every case we write ``<case>.pdf`` — a
minimal PDF whose object ``1 0 obj`` is a STREAM whose framing is the raw
fuzzed bytes plus a valid catalog (object 2) and pages tree so the document
loads — and a ``manifest.txt`` listing case names in order. The Java probe
(``StreamLengthFuzzProbe``) and pypdfbox read the exact same bytes from disk,
resolve object ``1 0 R``, and project an identical fingerprint.

Projection grammar (per case, one line ``CASE <name> <projection>``)::

    stream(raw=<n>,len=<LengthDictValue|na>,dec=<m|none|ERR>)
    notstream(<COSClassSimpleName>) | null | ABSENT
    ERR:<Exc> | LOAD:<Exc>

``raw`` = body byte count via ``COSStream.get_length`` (recovered/declared raw
body size); ``len`` = post-parse ``/Length`` entry value; ``dec`` = byte count
of the fully-decoded body (``create_input_stream``) or ``ERR``/``none``.
"""

from __future__ import annotations

import zlib
from pathlib import Path

import pytest

from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.cos.cos_number import COSNumber
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.loader import Loader
from tests.oracle.harness import requires_oracle, run_probe_text

_HEADER = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"

# A 30-byte body (long enough that the EndstreamFilterStream ASCII probe of the
# first 10 bytes sees binary control bytes for the compressed cases, ASCII for
# the plain ones — both paths are exercised).
_PLAIN_BODY = b"BT /F1 12 Tf (Hello World!) Tj ET"  # 33 bytes, ASCII text
_FLATE_BODY = zlib.compress(b"x" * 40)  # binary, has a /Filter


def _flate_obj1(length_field: bytes, *, body: bytes = _FLATE_BODY,
                filt: bytes = b"/FlateDecode", lead: bytes = b"\n",
                tail: bytes = b"\nendstream\nendobj\n") -> bytes:
    """Object 1 as a FlateDecode stream with a configurable /Length field."""
    return (
        b"1 0 obj\n<< /Length " + length_field
        + (b" /Filter " + filt if filt else b"")
        + b" >>\nstream" + lead + body + tail
    )


def _plain_obj1(length_field: bytes, *, body: bytes = _PLAIN_BODY,
                lead: bytes = b"\n",
                tail: bytes = b"\nendstream\nendobj\n") -> bytes:
    """Object 1 as a raw (no filter) stream with a configurable /Length."""
    return (
        b"1 0 obj\n<< /Length " + length_field
        + b" >>\nstream" + lead + body + tail
    )


# --------------------------------------------------------------------------- #
# Corpus. Each entry is (id, obj1_bytes, extra_objs).
# ``obj1_bytes`` is the full ``1 0 obj ... endobj`` segment, inserted verbatim.
# ``extra_objs`` are appended after the fixed catalog/pages objects and given
# their own xref slots (used for indirect /Length stored in object 5).
# --------------------------------------------------------------------------- #

_PLAIN_LEN = len(_PLAIN_BODY)
_FLATE_LEN = len(_FLATE_BODY)


def _len_obj5(value: int) -> bytes:
    return f"5 0 obj\n{value}\nendobj\n".encode("latin-1")


_CASES: tuple[tuple[str, bytes, tuple[bytes, ...]], ...] = (
    # ---- correct /Length (happy paths) ----
    ("plain_correct", _plain_obj1(str(_PLAIN_LEN).encode()), ()),
    ("flate_correct", _flate_obj1(str(_FLATE_LEN).encode()), ()),
    # ---- /Length too short ----
    ("plain_len_short", _plain_obj1(b"5"), ()),
    ("flate_len_short", _flate_obj1(b"3"), ()),
    # ---- /Length too long (overruns endstream) ----
    ("plain_len_long", _plain_obj1(b"500"), ()),
    ("flate_len_long", _flate_obj1(b"500"), ()),
    # ---- /Length zero ----
    ("plain_len_zero", _plain_obj1(b"0"), ()),
    ("flate_len_zero", _flate_obj1(b"0"), ()),
    # ---- /Length negative ----
    ("plain_len_negative", _plain_obj1(b"-5"), ()),
    # ---- /Length missing entirely ----
    (
        "len_missing",
        b"1 0 obj\n<< >>\nstream\n" + _PLAIN_BODY + b"\nendstream\nendobj\n",
        (),
    ),
    (
        "len_missing_flate",
        b"1 0 obj\n<< /Filter /FlateDecode >>\nstream\n"
        + _FLATE_BODY + b"\nendstream\nendobj\n",
        (),
    ),
    # ---- /Length a real (float) ----
    ("len_float", _plain_obj1(str(_PLAIN_LEN).encode() + b".0"), ()),
    # ---- /Length non-numeric (a name) ----
    ("len_name", _plain_obj1(b"/Bad"), ()),
    # ---- /Length null ----
    ("len_null", _plain_obj1(b"null"), ()),
    # ---- /Length indirect, resolves correctly ----
    ("len_indirect_ok", _plain_obj1(b"5 0 R"), (_len_obj5(_PLAIN_LEN),)),
    # ---- /Length indirect, wrong value ----
    ("len_indirect_wrong", _plain_obj1(b"5 0 R"), (_len_obj5(9),)),
    # ---- /Length indirect, target missing ----
    ("len_indirect_missing", _plain_obj1(b"99 0 R"), ()),
    # ---- endstream missing, endobj present (recovery to endobj) ----
    (
        "endstream_missing",
        b"1 0 obj\n<< /Length " + str(_PLAIN_LEN).encode()
        + b" >>\nstream\n" + _PLAIN_BODY + b"\nendobj\n",
        (),
    ),
    # ---- both endstream and endobj missing ----
    (
        "endstream_endobj_missing",
        b"1 0 obj\n<< /Length " + str(_PLAIN_LEN).encode()
        + b" >>\nstream\n" + _PLAIN_BODY + b"\n",
        (),
    ),
    # ---- no EOL after 'stream' keyword (body starts immediately) ----
    (
        "no_eol_after_stream",
        b"1 0 obj\n<< /Length " + str(_PLAIN_LEN).encode()
        + b" >>\nstream" + _PLAIN_BODY + b"\nendstream\nendobj\n",
        (),
    ),
    # ---- CRLF after 'stream' ----
    ("crlf_after_stream", _plain_obj1(str(_PLAIN_LEN).encode(), lead=b"\r\n"), ()),
    # ---- bare CR after 'stream' ----
    ("cr_after_stream", _plain_obj1(str(_PLAIN_LEN).encode(), lead=b"\r"), ()),
    # ---- extra whitespace before endstream ----
    (
        "ws_before_endstream",
        _plain_obj1(str(_PLAIN_LEN).encode(), tail=b"   \n\n  \nendstream\nendobj\n"),
        (),
    ),
    # ---- no EOL before endstream (endstream immediately after body) ----
    (
        "no_eol_before_endstream",
        b"1 0 obj\n<< /Length " + str(_PLAIN_LEN).encode()
        + b" >>\nstream\n" + _PLAIN_BODY + b"endstream\nendobj\n",
        (),
    ),
    # ---- endstream keyword present but no endobj ----
    (
        "endobj_missing",
        _plain_obj1(str(_PLAIN_LEN).encode(), tail=b"\nendstream\n"),
        (),
    ),
    # ---- body contains the literal text 'endstream' inside it ----
    (
        "body_contains_endstream",
        b"1 0 obj\n<< /Length 24 >>\nstream\n"
        b"abc endstream def ghijklm\nendstream\nendobj\n",
        (),
    ),
    # ---- trailing CR LF inside declared length (filter-stream edge) ----
    (
        "len_includes_eol_short",
        _plain_obj1(str(_PLAIN_LEN - 1).encode()),
        (),
    ),
    # ---- empty body, correct length 0 ----
    (
        "empty_body_len0",
        b"1 0 obj\n<< /Length 0 >>\nstream\n\nendstream\nendobj\n",
        (),
    ),
    # ---- empty body, missing length ----
    (
        "empty_body_no_len",
        b"1 0 obj\n<< >>\nstream\n\nendstream\nendobj\n",
        (),
    ),
    # ---- huge /Length far beyond file ----
    ("len_huge", _plain_obj1(b"99999999"), ()),
    # ---- binary body with NUL bytes, correct length ----
    (
        "binary_body",
        b"1 0 obj\n<< /Length 8 >>\nstream\n\x00\x01\x02\x03\xfe\xfd\xfc\xff"
        b"\nendstream\nendobj\n",
        (),
    ),
)

_IDS = [c[0] for c in _CASES]


def _build_pdf(obj1: bytes, extra_objs: tuple[bytes, ...]) -> bytes:
    """A minimal loadable PDF whose object 1 is the fuzzed stream ``obj1``.

    Object 2 is the catalog (/Root), object 3 the pages tree, object 4 a page.
    ``extra_objs`` (e.g. object 5 holding an indirect /Length) are appended and
    given their own xref slots.
    """
    buf = bytearray()
    buf.extend(_HEADER)
    offsets: dict[int, int] = {}

    offsets[1] = len(buf)
    buf.extend(obj1)

    offsets[2] = len(buf)
    buf.extend(b"2 0 obj\n<< /Type /Catalog /Pages 3 0 R >>\nendobj\n")

    offsets[3] = len(buf)
    buf.extend(b"3 0 obj\n<< /Type /Pages /Kids [4 0 R] /Count 1 >>\nendobj\n")

    offsets[4] = len(buf)
    buf.extend(
        b"4 0 obj\n<< /Type /Page /Parent 3 0 R "
        b"/MediaBox [0 0 612 792] >>\nendobj\n"
    )

    next_num = 5
    for extra in extra_objs:
        offsets[next_num] = len(buf)
        buf.extend(extra)
        next_num += 1

    size = next_num
    xref_off = len(buf)
    buf.extend(f"xref\n0 {size}\n".encode("latin-1"))
    buf.extend(b"0000000000 65535 f \n")
    for num in range(1, size):
        buf.extend(f"{offsets[num]:010d} 00000 n \n".encode("latin-1"))
    buf.extend(f"trailer\n<< /Size {size} /Root 2 0 R >>\n".encode("latin-1"))
    buf.extend(b"startxref\n")
    buf.extend(f"{xref_off}\n".encode("latin-1"))
    buf.extend(b"%%EOF\n")
    return bytes(buf)


def _len_entry(stream: COSStream) -> str:
    item = stream.get_item(COSName.LENGTH)
    if isinstance(item, COSObject):
        item = item.get_object()
    if isinstance(item, COSNumber):
        return str(item.long_value())
    return "na"


def _dec(stream: COSStream) -> str:
    try:
        with stream.create_input_stream() as src:
            total = 0
            while True:
                chunk = src.read(8192)
                if not chunk:
                    break
                total += len(chunk)
            return str(total)
    except Exception:  # noqa: BLE001 — mirror probe dec=ERR
        return "ERR"


def _project(pdf_path: Path) -> str:
    """pypdfbox projection for one ``<case>.pdf`` matching the Java probe."""
    document = None
    try:
        document = Loader.load_pdf(str(pdf_path))
    except Exception as exc:  # noqa: BLE001 — mirror probe LOAD:<Exc>
        return "LOAD:" + type(exc).__name__
    try:
        obj = document.get_object_from_pool(COSObjectKey(1, 0))
        if obj is None:
            return "ABSENT"
        try:
            resolved = obj.get_object()
        except Exception as exc:  # noqa: BLE001 — mirror probe ERR:<Exc>
            return "ERR:" + type(exc).__name__
        if resolved is None or isinstance(resolved, COSNull):
            return "null"
        if not isinstance(resolved, COSStream):
            return f"notstream({type(resolved).__name__})"
        raw = resolved.get_length()
        return f"stream(raw={raw},len={_len_entry(resolved)},dec={_dec(resolved)})"
    finally:
        document.close()


def _write_corpus(dir_path: Path) -> None:
    for case_id, obj1, extra in _CASES:
        (dir_path / f"{case_id}.pdf").write_bytes(_build_pdf(obj1, extra))
    manifest = "\n".join(_IDS) + "\n"
    (dir_path / "manifest.txt").write_text(manifest, encoding="utf-8")


def _strip(line: str) -> str:
    """``CASE <name> <projection>`` -> ``<projection>``."""
    return line.split(" ", 2)[2] if line.count(" ") >= 2 else ""


# --------------------------------------------------------------------------- #
# Defensible divergences pinned BOTH-SIDES (Java is ground truth but pypdfbox's
# behaviour is intentional). Maps case id -> (java_projection, py_projection).
# Filled in after the first oracle run; every case NOT listed must agree
# byte-for-byte.
# --------------------------------------------------------------------------- #

_DIVERGENT: dict[str, tuple[str, str]] = {
    # A wrong-typed /Length (a name, a direct null, or an indirect ref whose
    # target is missing) makes upstream's COSParser.getLength throw an
    # IOException inside parseCOSStream. Upstream's COSObject.getObject catches
    # that IOException, logs it, and leaves the indirect object NULL — so the
    # whole stream resolves to ``null``. pypdfbox raises PDFParseError out of
    # _read_stream_body and the lazy COSObject.get_object propagates it (it does
    # NOT swallow loader errors the way upstream does). This is a fail-fast
    # robustness divergence pinned BOTH-SIDES (same family as the wave-1516
    # container-framing pins): aligning it would require making COSObject swallow
    # all loader IOExceptions document-wide, a far broader behavioural change
    # than this stream-recovery surface. See CHANGES.md Wave 1517.
    "len_name": ("null", "ERR:PDFParseError"),
    "len_null": ("null", "ERR:PDFParseError"),
    "len_indirect_missing": ("null", "ERR:PDFParseError"),
}


@requires_oracle
def test_stream_length_matches_pdfbox(tmp_path: Path) -> None:
    _write_corpus(tmp_path)
    java = run_probe_text("StreamLengthFuzzProbe", str(tmp_path))
    java_proj = {
        line.split(" ", 2)[1]: _strip(line)
        for line in java.splitlines()
        if line.startswith("CASE ")
    }
    py_proj = {
        case_id: _project(tmp_path / f"{case_id}.pdf") for case_id, _, _ in _CASES
    }

    mismatches: list[str] = []
    for case_id in _IDS:
        j = java_proj.get(case_id)
        p = py_proj[case_id]
        if case_id in _DIVERGENT:
            exp_java, exp_py = _DIVERGENT[case_id]
            if p != exp_py:
                mismatches.append(
                    f"{case_id} (pinned py drifted):\n"
                    f"  expected py: {exp_py}\n  actual py:   {p}"
                )
            if j != exp_java:
                mismatches.append(
                    f"{case_id} (pinned java drifted):\n"
                    f"  expected java: {exp_java}\n  actual java:   {j}"
                )
        else:
            if j != p:
                mismatches.append(f"{case_id}:\n  java: {j}\n  py:   {p}")
    assert not mismatches, "stream-length divergences:\n" + "\n".join(mismatches)


# --------------------------------------------------------------------------- #
# Oracle-independent regression pins — these document pypdfbox's stream-body
# recovery so the contract holds on a machine without the live oracle.
# --------------------------------------------------------------------------- #


def test_happy_path_plain(tmp_path: Path) -> None:
    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(_build_pdf(_plain_obj1(str(_PLAIN_LEN).encode()), ()))
    assert _project(pdf) == f"stream(raw={_PLAIN_LEN},len={_PLAIN_LEN},dec={_PLAIN_LEN})"


def test_wrong_length_recovers_to_endstream(tmp_path: Path) -> None:
    """A too-short /Length is recovered by scanning to endstream; the recovered
    raw length is the true body length and /Length is rewritten."""
    pdf = tmp_path / "short.pdf"
    pdf.write_bytes(_build_pdf(_plain_obj1(b"5"), ()))
    rec = _PLAIN_LEN + 1  # recovery keeps the embedded EOL byte (matches PDFBox)
    assert _project(pdf) == f"stream(raw={rec},len={rec},dec={rec})"


def test_missing_length_recovers(tmp_path: Path) -> None:
    pdf = tmp_path / "miss.pdf"
    pdf.write_bytes(
        _build_pdf(
            b"1 0 obj\n<< >>\nstream\n" + _PLAIN_BODY + b"\nendstream\nendobj\n", ()
        )
    )
    rec = _PLAIN_LEN + 1  # recovery keeps the embedded EOL byte (matches PDFBox)
    assert _project(pdf) == f"stream(raw={rec},len={rec},dec={rec})"


def test_indirect_length_resolves(tmp_path: Path) -> None:
    pdf = tmp_path / "ind.pdf"
    pdf.write_bytes(_build_pdf(_plain_obj1(b"5 0 R"), (_len_obj5(_PLAIN_LEN),)))
    assert _project(pdf) == f"stream(raw={_PLAIN_LEN},len={_PLAIN_LEN},dec={_PLAIN_LEN})"


@pytest.mark.parametrize("case_id", list(_DIVERGENT))
def test_wrong_type_length_is_fail_fast(case_id: str, tmp_path: Path) -> None:
    """A wrong-typed /Length (name / direct null / missing indirect target)
    raises PDFParseError in pypdfbox (object unresolved). Upstream swallows the
    getLength IOException and the object resolves to null — pinned divergence."""
    obj1, extra = next((o, e) for cid, o, e in _CASES if cid == case_id)
    pdf = tmp_path / f"{case_id}.pdf"
    pdf.write_bytes(_build_pdf(obj1, extra))
    assert _project(pdf) == "ERR:PDFParseError"


def test_missing_endstream_recovers_to_endobj(tmp_path: Path) -> None:
    """endstream omitted but endobj present: recovery scans to endobj."""
    obj1, extra = next((o, e) for cid, o, e in _CASES if cid == "endstream_missing")
    pdf = tmp_path / "es_missing.pdf"
    pdf.write_bytes(_build_pdf(obj1, extra))
    assert _project(pdf).startswith("stream(")


def test_float_length_accepted(tmp_path: Path) -> None:
    """A COSFloat /Length is a COSNumber and its int value is honoured."""
    pdf = tmp_path / "float.pdf"
    pdf.write_bytes(_build_pdf(_plain_obj1(str(_PLAIN_LEN).encode() + b".0"), ()))
    assert _project(pdf) == f"stream(raw={_PLAIN_LEN},len={_PLAIN_LEN},dec={_PLAIN_LEN})"


def test_negative_length_recovers(tmp_path: Path) -> None:
    """A negative /Length fails validate_stream_length and triggers recovery."""
    pdf = tmp_path / "neg.pdf"
    pdf.write_bytes(_build_pdf(_plain_obj1(b"-5"), ()))
    rec = _PLAIN_LEN + 1  # recovery keeps the embedded EOL byte (matches PDFBox)
    assert _project(pdf) == f"stream(raw={rec},len={rec},dec={rec})"


@pytest.mark.parametrize("case_id", _IDS)
def test_every_case_resolves_without_crash(case_id: str, tmp_path: Path) -> None:
    """No case should make the projection itself raise — it must land on one of
    the grammar terminals (stream/notstream/null/ABSENT/ERR/LOAD)."""
    obj1, extra = next((o, e) for cid, o, e in _CASES if cid == case_id)
    pdf = tmp_path / f"{case_id}.pdf"
    pdf.write_bytes(_build_pdf(obj1, extra))
    proj = _project(pdf)
    assert proj.startswith(
        ("stream(", "notstream(", "null", "ABSENT", "ERR:", "LOAD:")
    )
