"""Live differential: the object graph of saved ``Splitter`` /
``PageExtractor`` output against Apache PDFBox.

``SplitterStructureProbe`` splits the same file with PDFBox and saves every
part; both sides are then walked breadth-first from the trailer and every
reachable value is recorded under the first path it is reached by
(references by the canonical path of their target, streams by a hash of
their decoded data). The two maps must be identical, which pins page and
annotation cloning, link destination fixing, the structure tree clone
(including the half-built elements upstream leaves reachable through
``/ParentTree`` and ``/IDTree``), named destinations and the
``/StructTreeRoot`` maps.

pypdfbox forward-ports the PDFBOX-6283 named-destination handling from the
3.0 branch, so the Splitter is compared against that source (variant
``309``, compiled into the probe against the 3.0.8 jar). Indirect strings
and numbers are compared by value: the PDFBox writer merges equal ones into
one object, which is a writer difference, not a splitter one.
"""

import hashlib
from collections import deque
from pathlib import Path

import pytest

from pypdfbox import PDDocument
from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.multipdf import PageExtractor, Splitter
from tests.oracle.harness import requires_oracle, run_probe

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
_SKIP_STREAM_KEYS = {"Length", "Filter", "DecodeParms"}


def _scalar(obj: object) -> str | None:
    if isinstance(obj, COSName):
        return "/" + obj.get_name()
    if isinstance(obj, COSInteger):
        return f"i{obj.int_value()}"
    if isinstance(obj, COSFloat):
        return f"f{round(obj.float_value(), 4)}"
    if isinstance(obj, COSString):
        return "s" + obj.get_bytes().hex()
    if isinstance(obj, COSBoolean):
        return f"b{obj.get_value()}"
    if obj is None or isinstance(obj, COSNull):
        return "null"
    return None


def _structure(path: Path) -> dict[str, str]:
    """``{canonical path: signature}`` for everything reachable from the
    trailer's ``/Root`` and ``/Info``."""
    with PDDocument.load(path) as doc:
        trailer = doc.get_document().get_trailer()
        sigs: dict[str, str] = {}
        canon: dict[tuple[int, int], str] = {}
        queue: deque = deque(
            ("/" + name, trailer.get_item(COSName.get_pdf_name(name)))
            for name in ("Info", "Root")
            if trailer.contains_key(COSName.get_pdf_name(name))
        )
        while queue:
            p, item = queue.popleft()
            obj = item.get_object() if isinstance(item, COSObject) else item
            scalar = _scalar(obj)
            if scalar is not None:
                sigs[p] = scalar
                continue
            if isinstance(item, COSObject):
                ref = (item.get_object_number(), item.get_generation_number())
                if ref in canon:
                    sigs[p] = "ref:" + canon[ref]
                    continue
                canon[ref] = p
            if isinstance(obj, COSDictionary):
                keys = sorted(obj.key_set(), key=lambda k: k.get_name())
                sig = "dict{" + ",".join(k.get_name() for k in keys) + "}"
                if isinstance(obj, COSStream):
                    sig = "stream" + sig + hashlib.md5(obj.to_byte_array()).hexdigest()
                sigs[p] = sig
                for key in keys:
                    if isinstance(obj, COSStream) and key.get_name() in _SKIP_STREAM_KEYS:
                        continue
                    queue.append((f"{p}/{key.get_name()}", obj.get_item(key)))
            elif isinstance(obj, COSArray):
                sigs[p] = f"array[{obj.size()}]"
                queue.extend((f"{p}[{i}]", obj.get(i)) for i in range(obj.size()))
            else:
                sigs[p] = type(obj).__name__
    return sigs


def _first_differences(py: dict[str, str], java: dict[str, str]) -> list[str]:
    diffs = sorted(
        (p for p in set(py) | set(java) if py.get(p) != java.get(p)),
        key=lambda p: (p.count("/") + p.count("["), p),
    )
    return [f"{p}: {py.get(p, '<absent>')} | {java.get(p, '<absent>')}" for p in diffs[:5]]


def _java_parts(tmp_path: Path, src: Path, variant: str, split: int, start: int, end: int):
    out = tmp_path / "java"
    out.mkdir()
    run_probe(
        "SplitterStructureProbe", str(src), str(split), str(out), variant, str(start), str(end)
    )
    return sorted(out.glob("part-*.pdf"), key=lambda p: int(p.stem.split("-")[1]))


def _save_parts(tmp_path: Path, parts: list[PDDocument]) -> list[Path]:
    out = tmp_path / "py"
    out.mkdir()
    paths = []
    for i, part in enumerate(parts, start=1):
        path = out / f"part-{i}.pdf"
        part.save(str(path))
        part.close()
        paths.append(path)
    return paths


def _assert_same(py_paths: list[Path], java_paths: list[Path]) -> None:
    assert len(py_paths) == len(java_paths)
    for py_path, java_path in zip(py_paths, java_paths, strict=True):
        py, java = _structure(py_path), _structure(java_path)
        assert py == java, (py_path.name, _first_differences(py, java))


_CASES = [
    ("multipdf/PDFBOX-5809-509329.pdf", 1, 0, 0),  # markup + popup annotations
    ("multipdf/PDFBOX-5792-240045.pdf", 1, 0, 0),  # tagged, role map
    ("multipdf/PDFBOX-5792-240045.pdf", 3, 0, 0),
    ("multipdf/PDFBOX-5762-722238.pdf", 2, 0, 0),
    ("multipdf/PDFBOX-5811-362972.pdf", 2, 0, 0),
    ("multipdf/PDFBOX-5840-410609.pdf", 1, 0, 0),  # NUL in a named destination
    ("multipdf/PDFBOX-4417-001031.pdf", 1, 0, 0),
    ("multipdf/PDFBOX-4417-054080.pdf", 2, 0, 0),
    ("multipdf/PDFA3A.pdf", 1, 0, 0),
    ("pdfwriter/attachment.pdf", 1, 0, 0),
    ("pdmodel/interactive/form/AcroFormsBasicFields.pdf", 1, 0, 0),
    ("multipdf/PDFBOX-5809-509329.pdf", 2, 2, 5),  # start / end window
]


@requires_oracle
@pytest.mark.parametrize(
    ("fixture", "split", "start", "end"),
    _CASES,
    ids=[f"{Path(c[0]).stem}-{c[1]}-{c[2]}-{c[3]}" for c in _CASES],
)
def test_split_output_matches_pdfbox(
    tmp_path: Path, fixture: str, split: int, start: int, end: int
) -> None:
    src = _FIXTURES / fixture
    if not src.is_file():
        pytest.skip(f"fixture missing: {fixture}")
    java_paths = _java_parts(tmp_path, src, "309", split, start, end)
    with PDDocument.load(src) as doc:
        splitter = Splitter()
        splitter.set_split_at_page(split)
        if start:
            splitter.set_start_page(start)
        if end:
            splitter.set_end_page(end)
        py_paths = _save_parts(tmp_path, splitter.split(doc))
    _assert_same(py_paths, java_paths)


@requires_oracle
@pytest.mark.parametrize(
    ("fixture", "start", "end"),
    [
        ("multipdf/PDFBOX-5792-240045.pdf", 2, 3),
        ("multipdf/PDFBOX-5809-509329.pdf", 1, 99),
    ],
    ids=["tagged-2-3", "popups-clamped-end"],
)
def test_page_extractor_output_matches_pdfbox(
    tmp_path: Path, fixture: str, start: int, end: int
) -> None:
    src = _FIXTURES / fixture
    if not src.is_file():
        pytest.skip(f"fixture missing: {fixture}")
    # PDFBox 3.0.8 PageExtractor (no named destinations in these files, so
    # the 3.0.8 and 3.0 branch Splitter agree)
    java_paths = _java_parts(tmp_path, src, "extract", 1, start, end)
    with PDDocument.load(src) as doc:
        py_paths = _save_parts(tmp_path, [PageExtractor(doc, start, end).extract()])
    _assert_same(py_paths, java_paths)
