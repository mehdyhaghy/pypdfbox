"""Live PDFBox differential parity for multimedia + rendition annotations/actions.

Builds a one-page PDF carrying three multimedia annotations and asserts that
pypdfbox reads the same per-annotation subtype + type-specific fields out of it
as Apache PDFBox 3.0.7:

* a **Screen** annotation (``/Subtype /Screen``) with an ``/MK`` appearance
  dictionary and a **Rendition** ``/A`` action (``/OP 0`` Play-if-stopped, ``/AN``
  pointing back at the screen, ``/R`` a ``/S /MR`` media rendition whose media
  clip ``/C`` carries a ``/D`` file specification ``clip.mp4``);
* a **Movie** annotation (``/Movie /F movie.avi``, ``/A`` activation dict with
  ``/ShowControls true``);
* a **Sound** annotation (``/Sound`` stream, ``/Name /Mic``).

The Java side is ``oracle/probes/MultimediaProbe.java``.

**Why raw COS on the Java side for Movie/Screen/Rendition.** The pinned
``pdfbox-app-3.0.7.jar`` is a trimmed distribution: it ships
``PDAnnotationSound``, ``PDActionSound``, ``PDActionMovie`` (thin),
``PDActionFactory`` and ``PDFileSpecification``, but it does **not** compile in
``PDAnnotationMovie`` / ``PDAnnotationScreen`` / ``PDAnnotation3D`` /
``PDActionRendition`` / ``PDMovie`` / ``PDRendition`` / ``PDMediaRendition``.
The probe therefore reads those wrappers' fields through the version-agnostic
raw-COS surface (``getDictionaryObject`` / ``getNameAsString`` / ``getInt`` /
``getString``) plus ``PDFileSpecification.createFS().getFile()``. pypdfbox ports
the full upstream source tree, so its typed wrappers (``PDAnnotationScreen``
etc.) DO exist — the reproducer exercises those typed accessors and asserts
they surface byte-identical values.

**Factory dispatch is a deliberate divergence we pin, not fix.** Upstream
``PDAnnotation.createAnnotation`` (3.0.7) maps only a fixed subtype set and
returns ``PDAnnotationUnknown`` for ``Movie`` / ``Screen`` / ``3D``; likewise
``PDActionFactory.createAction`` does not map ``Rendition`` and returns null.
pypdfbox's richer factories *do* type those — but the probe asserts on the
subtype STRING (which both agree on) for annotations, and on
``PDActionFactory.create_action`` returning ``None`` for Rendition (which both
DO agree on), so the parity check stays sound across the jar's reduced surface.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.action.pd_action_factory import PDActionFactory
from pypdfbox.pdmodel.interactive.action.pd_action_rendition import PDActionRendition
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_movie import (
    PDAnnotationMovie,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_screen import (
    PDAnnotationScreen,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_sound import (
    PDAnnotationSound,
)
from pypdfbox.pdmodel.interactive.annotation.pd_movie import PDMovie
from pypdfbox.pdmodel.interactive.annotation.pd_movie_activation import (
    PDMovieActivation,
)
from pypdfbox.pdmodel.interactive.measurement.pd_media_clip_data import (
    PDMediaClipData,
)
from pypdfbox.pdmodel.interactive.measurement.pd_media_rendition import (
    PDMediaRendition,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_TYPE = COSName.get_pdf_name("Type")
_F = COSName.get_pdf_name("F")
_FILESPEC = COSName.get_pdf_name("Filespec")
_SOUND = COSName.get_pdf_name("Sound")


def _b(value: bool) -> str:
    return "true" if value else "false"


def _nz(value: str | None) -> str:
    return "NULL" if value is None else value


def _build_multimedia_pdf(out_path: Path) -> None:
    """Build a one-page PDF with Screen+Rendition, Movie and Sound annotations.

    Field values are chosen so the parity check exercises the away-from-empty
    branch of every accessor on both sides: ``/OP 0`` (not the absent sentinel),
    an ``/AN`` self-reference, a media clip filename, a Movie file spec, an
    activation dict with ``/ShowControls true`` and a ``/Mic`` sound icon.
    """
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle.A4)
        doc.add_page(page)

        # --- Screen annotation carrying a Rendition action ---
        screen = PDAnnotationScreen()
        screen.set_title("clip-screen")
        screen.set_appearance_characteristics(COSDictionary())

        clip = PDMediaClipData()
        clip.set_n("clip-name")
        fs_dict = COSDictionary()
        fs_dict.set_item(_TYPE, _FILESPEC)
        fs_dict.set_string(_F, "clip.mp4")
        clip.set_d(fs_dict)

        rend = PDMediaRendition()
        rend.set_n("media-rend")
        rend.set_c(clip)

        action = PDActionRendition()
        action.set_op(PDActionRendition.OP_PLAY_IF_STOPPED)  # /OP 0
        action.set_annotation(screen)  # /AN -> the screen annotation
        action.set_rendition(rend)  # /R -> media rendition
        screen.set_action(action)

        # --- Movie annotation ---
        movie_annot = PDAnnotationMovie()
        movie_annot.set_title("the-movie")
        movie = PDMovie()
        movie.set_file("movie.avi")
        movie_annot.set_movie(movie)
        activation = PDMovieActivation()
        activation.set_show_controls(True)
        movie_annot.set_activation(activation)

        # --- Sound annotation ---
        sound_annot = PDAnnotationSound()
        snd = COSStream()
        snd.set_item(_TYPE, _SOUND)
        sound_annot.set_sound(snd)
        sound_annot.set_name(PDAnnotationSound.NAME_MIC)

        page.set_annotations([screen, movie_annot, sound_annot])
        doc.save(out_path)
    finally:
        doc.close()


def _dump_screen(lines: list[str], prefix: str, screen: PDAnnotationScreen) -> None:
    lines.append(f"{prefix}hasMK={_b(screen.has_appearance_characteristics())}")
    action = screen.get_action()
    if isinstance(action, PDActionRendition):
        lines.append(f"{prefix}action.subtype={_nz(action.get_sub_type())}")
        # Upstream PDActionFactory.createAction does NOT map Rendition -> None.
        created = PDActionFactory.create_action(action.get_cos_object())
        lines.append(
            f"{prefix}action.factoryClass="
            f"{'NULL' if created is None else type(created).__name__}"
        )
        _dump_rendition(lines, f"{prefix}rendition.", action)
    elif action is not None:
        lines.append(f"{prefix}action.subtype={_nz(action.get_sub_type())}")
        created = PDActionFactory.create_action(action.get_cos_object())
        lines.append(
            f"{prefix}action.factoryClass="
            f"{'NULL' if created is None else type(created).__name__}"
        )
    else:
        lines.append(f"{prefix}action.subtype=NULL")
        lines.append(f"{prefix}action.factoryClass=NULL")


def _dump_rendition(
    lines: list[str], prefix: str, action: PDActionRendition
) -> None:
    # /OP — get_op() returns the -1 sentinel when absent, matching getInt.
    lines.append(f"{prefix}op={action.get_op()}")
    screen_an = action.get_screen_annotation()
    lines.append(f"{prefix}hasAN={_b(action.has_annotation())}")
    lines.append(
        f"{prefix}anSubtype="
        f"{_nz(screen_an.get_subtype() if screen_an is not None else None)}"
    )
    rendition = action.get_rendition()
    if isinstance(rendition, PDMediaRendition):
        lines.append(f"{prefix}rSubtype={_nz(rendition.get_subtype())}")
        lines.append(f"{prefix}rName={_nz(rendition.get_n())}")
        lines.append(f"{prefix}clipFile={_nz(_media_clip_file(rendition))}")
    else:
        lines.append(f"{prefix}rSubtype=NULL")
        lines.append(f"{prefix}rName=NULL")
        lines.append(f"{prefix}clipFile=NULL")


def _media_clip_file(rendition: PDMediaRendition) -> str | None:
    clip = rendition.get_c()
    if not isinstance(clip, PDMediaClipData):
        return None
    from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
        PDFileSpecification,
    )

    d = clip.get_d()
    if d is None:
        return None
    fs = PDFileSpecification.create_fs(d)
    return fs.get_file() if fs is not None else None


def _dump_movie(lines: list[str], prefix: str, movie_annot: PDAnnotationMovie) -> None:
    movie = movie_annot.get_movie()
    file_value: str | None = None
    if movie is not None:
        file_spec = movie.get_file()
        if file_spec is not None:
            file_value = file_spec.get_file()
    lines.append(f"{prefix}movieFile={_nz(file_value)}")

    activation = movie_annot.get_activation()
    if isinstance(activation, bool):
        lines.append(f"{prefix}activationKind=boolean")
        lines.append(f"{prefix}activation={_b(activation)}")
        lines.append(f"{prefix}showControls=NULL")
    elif isinstance(activation, PDMovieActivation):
        lines.append(f"{prefix}activationKind=dictionary")
        lines.append(f"{prefix}activation=DICT")
        # show_controls() applies the spec default False; the probe prints
        # NULL only when the entry is wholly absent, so mirror by checking
        # presence on the underlying dictionary.
        cos = activation.get_cos_object()
        sc = cos.get_dictionary_object(COSName.get_pdf_name("ShowControls"))
        if sc is None:
            lines.append(f"{prefix}showControls=NULL")
        else:
            lines.append(f"{prefix}showControls={_b(activation.show_controls())}")
    else:
        lines.append(f"{prefix}activationKind=NULL")
        lines.append(f"{prefix}activation=NULL")
        lines.append(f"{prefix}showControls=NULL")


def _dump_sound(lines: list[str], prefix: str, sound_annot: PDAnnotationSound) -> None:
    lines.append(f"{prefix}factoryClass={type(sound_annot).__name__}")
    lines.append(f"{prefix}hasSound={_b(sound_annot.has_sound())}")
    # /Name read raw so absence shows NULL (get_name() bakes the Speaker default).
    raw_name = sound_annot.get_cos_object().get_name_as_string(
        COSName.get_pdf_name("Name")
    )
    lines.append(f"{prefix}name={_nz(raw_name)}")


def _py_dump(fixture: Path) -> str:
    """Reproduce the line-oriented dump MultimediaProbe.java emits."""
    lines: list[str] = []
    doc = PDDocument.load(fixture)
    try:
        page = doc.get_page(0)
        annots = page.get_annotations()
        lines.append(f"annotCount={len(annots)}")
        for idx, annot in enumerate(annots):
            prefix = f"annot[{idx}]."
            subtype = annot.get_subtype()
            lines.append(f"{prefix}subtype={_nz(subtype)}")
            if subtype == "Screen":
                assert isinstance(annot, PDAnnotationScreen)
                _dump_screen(lines, prefix, annot)
            elif subtype == "Movie":
                assert isinstance(annot, PDAnnotationMovie)
                _dump_movie(lines, prefix, annot)
            elif subtype == "Sound":
                assert isinstance(annot, PDAnnotationSound)
                _dump_sound(lines, prefix, annot)
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


@requires_oracle
def test_multimedia_annotations_match_pdfbox() -> None:
    """Screen+Rendition / Movie / Sound annotation fields match PDFBox 3.0.7.

    High-value linkage: Rendition action ``/OP`` operation code, ``/AN``
    screen-annotation reference + its subtype, ``/R`` media-rendition subtype +
    name + media clip filename; Movie file spec + activation ``/ShowControls``;
    Sound subtype + icon name.
    """
    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / "multimedia.pdf"
        _build_multimedia_pdf(pdf)
        java = run_probe_text("MultimediaProbe", str(pdf))
        py = _py_dump(pdf)
        assert py == java, (
            "multimedia annotation/action fields diverge from PDFBox.\n"
            f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
        )


def _build_alt_branches_pdf(out_path: Path) -> None:
    """Build a PDF exercising the OTHER activation/icon branches:

    a Movie annotation whose ``/A`` is the boolean ``true`` (not an activation
    dictionary), and a Sound annotation with NO ``/Name`` (absent icon → ``NULL``
    on the raw read, ``Speaker`` default on the typed read)."""
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle.A4)
        doc.add_page(page)

        movie_annot = PDAnnotationMovie()
        movie = PDMovie()
        movie.set_file("b.mov")
        movie_annot.set_movie(movie)
        movie_annot.set_activation(True)  # boolean /A

        sound_annot = PDAnnotationSound()
        sound_annot.set_sound(COSStream())  # no /Name -> default

        page.set_annotations([movie_annot, sound_annot])
        doc.save(out_path)
    finally:
        doc.close()


@requires_oracle
def test_multimedia_boolean_activation_and_default_icon_match_pdfbox() -> None:
    """Movie boolean ``/A`` activation + absent Sound ``/Name`` match PDFBox.

    Covers the activation-as-boolean branch (``/A true`` → ``activation=true``,
    no ``/ShowControls``) and the absent-icon branch (raw ``/Name`` → ``NULL``)
    that the primary case does not exercise."""
    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / "multimedia_alt.pdf"
        _build_alt_branches_pdf(pdf)
        java = run_probe_text("MultimediaProbe", str(pdf))
        py = _py_dump(pdf)
        assert py == java, (
            "boolean-activation / default-icon fields diverge from PDFBox.\n"
            f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
        )
