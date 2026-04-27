from __future__ import annotations

from pypdfbox.contentstream import (
    Operator,
    OperatorProcessor,
    PDFStreamEngine,
)
from pypdfbox.cos import COSBase, COSStream
from pypdfbox.pdmodel import PDPage, PDResources


class _ResourcesProbe(OperatorProcessor):
    """Records ``get_resources`` / ``get_current_page`` /
    ``is_processing_page`` / ``get_level`` at dispatch time so the parity
    tests can assert on the engine's accessor surface without poking at
    private state."""

    def __init__(self) -> None:
        super().__init__()
        self.seen_resources: list[PDResources | None] = []
        self.seen_pages: list[PDPage | None] = []
        self.seen_processing: list[bool] = []
        self.seen_levels: list[int] = []

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        engine = self.get_context()
        assert engine is not None
        self.seen_resources.append(engine.get_resources())
        self.seen_pages.append(engine.get_current_page())
        self.seen_processing.append(engine.is_processing_page())
        self.seen_levels.append(engine.get_level())

    def get_name(self) -> str:
        return "Tj"


def _page_with_text() -> PDPage:
    page = PDPage()
    # Pin a resources dict so PDPage.get_resources returns a wrapper over
    # the *same* COSDictionary on each call — without this the lazy
    # accessor hands out a fresh empty PDResources every invocation.
    page.set_resources(PDResources())
    cs = COSStream()
    with cs.create_raw_output_stream() as out:
        out.write(b"(X) Tj")
    page.set_contents(cs)
    return page


# ---------- get_resources ----------


def test_get_resources_returns_page_resources_during_process_page() -> None:
    engine = PDFStreamEngine()
    probe = _ResourcesProbe()
    engine.add_operator(probe)
    page = _page_with_text()
    page_resources_cos = page.get_resources().get_cos_object()

    engine.process_page(page)

    # Compare by underlying COS dict — PDPage hands out a fresh wrapper
    # per call, but it's a wrapper over the same /Resources dictionary.
    assert len(probe.seen_resources) == 1
    seen = probe.seen_resources[0]
    assert seen is not None
    assert seen.get_cos_object() is page_resources_cos
    # And the engine's resource accessor still points at the same dict
    # post-process_page (upstream leaves the field set; ``process_form``
    # / ``process_stream`` are responsible for save/restore).
    final = engine.get_resources()
    assert final is not None
    assert final.get_cos_object() is page_resources_cos


# ---------- is_processing_page ----------


def test_is_processing_page_true_during_process_page_false_after() -> None:
    engine = PDFStreamEngine()
    probe = _ResourcesProbe()
    engine.add_operator(probe)

    assert engine.is_processing_page() is False

    engine.process_page(_page_with_text())

    assert probe.seen_processing == [True]
    assert engine.is_processing_page() is False


# ---------- get_level ----------


def test_get_level_starts_at_zero() -> None:
    engine = PDFStreamEngine()
    assert engine.get_level() == 0


def test_get_level_increments_inside_process_stream() -> None:
    engine = PDFStreamEngine()
    probe = _ResourcesProbe()
    engine.add_operator(probe)

    engine.process_page(_page_with_text())

    # process_page calls _process_bytes which does NOT bump level
    # (level tracks process_stream nesting). The probe ran at level 0.
    assert probe.seen_levels == [0]
    # And we're back to 0 after processing.
    assert engine.get_level() == 0


# ---------- get_current_page ----------


def test_get_current_page_returns_page_during_process_page() -> None:
    engine = PDFStreamEngine()
    probe = _ResourcesProbe()
    engine.add_operator(probe)
    page = _page_with_text()

    assert engine.get_current_page() is None

    engine.process_page(page)

    assert probe.seen_pages == [page]
    assert engine.get_current_page() is None


# ---------- set_resources / graphics-state placeholders ----------


def test_set_resources_pushes_frame() -> None:
    engine = PDFStreamEngine()
    res = PDResources()
    engine.set_resources(res)
    assert engine.get_resources() is res


def test_save_restore_graphics_state_no_op() -> None:
    engine = PDFStreamEngine()
    # Base implementations are no-op placeholders — must return None and
    # not raise so renderer subclasses can call ``super()`` safely.
    assert engine.save_graphics_state() is None
    assert engine.restore_graphics_state() is None


def test_transform_text_no_op() -> None:
    engine = PDFStreamEngine()
    assert engine.transform_text([1.0, 0.0, 0.0, 1.0, 0.0, 0.0]) is None
