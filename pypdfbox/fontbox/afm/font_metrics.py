from __future__ import annotations

from pypdfbox.fontbox.ttf.glyph_data import BoundingBox

from .char_metric import CharMetric
from .composite import Composite
from .kern_pair import KernPair
from .track_kern import TrackKern


class FontMetrics:
    """Top-level AFM document.

    Mirrors ``org.apache.fontbox.afm.FontMetrics`` field-for-field. The
    accessors follow upstream's getter/setter naming snake-cased per
    project convention (``getFontName`` -> ``get_font_name`` etc.). The
    boolean flags ``is_base_font`` / ``is_fixed_v`` / ``is_fixed_pitch``
    use the ``get_is_*`` form to match upstream's bean naming.
    """

    __slots__ = (
        "_afm_version",
        "_metric_sets",
        "_font_name",
        "_full_name",
        "_family_name",
        "_weight",
        "_font_b_box",
        "_font_version",
        "_notice",
        "_encoding_scheme",
        "_mapping_scheme",
        "_esc_char",
        "_character_set",
        "_characters",
        "_is_base_font",
        "_v_vector",
        "_is_fixed_v",
        "_cap_height",
        "_x_height",
        "_ascender",
        "_descender",
        "_comments",
        "_underline_position",
        "_underline_thickness",
        "_italic_angle",
        "_char_width",
        "_is_fixed_pitch",
        "_standard_horizontal_width",
        "_standard_vertical_width",
        "_char_metrics",
        "_char_metrics_map",
        "_track_kern",
        "_composites",
        "_kern_pairs",
        "_kern_pairs0",
        "_kern_pairs1",
    )

    def __init__(self) -> None:
        self._afm_version: float = 0.0
        self._metric_sets: int = 0
        self._font_name: str | None = None
        self._full_name: str | None = None
        self._family_name: str | None = None
        self._weight: str | None = None
        self._font_b_box: BoundingBox | None = None
        self._font_version: str | None = None
        self._notice: str | None = None
        self._encoding_scheme: str | None = None
        self._mapping_scheme: int = 0
        self._esc_char: int = 0
        self._character_set: str | None = None
        self._characters: int = 0
        self._is_base_font: bool = True
        self._v_vector: tuple[float, float] | None = None
        self._is_fixed_v: bool | None = None
        self._cap_height: float = 0.0
        self._x_height: float = 0.0
        self._ascender: float = 0.0
        self._descender: float = 0.0
        self._comments: list[str] = []
        self._underline_position: float = 0.0
        self._underline_thickness: float = 0.0
        self._italic_angle: float = 0.0
        self._char_width: tuple[float, float] | None = None
        self._is_fixed_pitch: bool = False
        self._standard_horizontal_width: float = 0.0
        self._standard_vertical_width: float = 0.0
        self._char_metrics: list[CharMetric] = []
        self._char_metrics_map: dict[str, CharMetric] = {}
        self._track_kern: list[TrackKern] = []
        self._composites: list[Composite] = []
        self._kern_pairs: list[KernPair] = []
        self._kern_pairs0: list[KernPair] = []
        self._kern_pairs1: list[KernPair] = []

    # ---------- character lookups ----------

    def get_char_metric(self, name: str) -> CharMetric | None:
        """Look up the :class:`CharMetric` for glyph ``name``.

        Convenience wrapper over the internal name -> metric map populated
        by :meth:`add_char_metric` / :meth:`set_char_metrics`. Returns
        ``None`` when the glyph is unknown or when ``name`` is ``None``.
        """
        if name is None:
            return None
        return self._char_metrics_map.get(name)

    def has_char_metric(self, name: str) -> bool:
        """``True`` when a :class:`CharMetric` exists for glyph ``name``."""
        if name is None:
            return False
        return name in self._char_metrics_map

    def get_character_width(self, name: str) -> float:
        """Width (``WX``) of glyph ``name``; ``0.0`` if not present."""
        metric = self._char_metrics_map.get(name)
        return 0.0 if metric is None else metric.get_wx()

    def get_character_height(self, name: str) -> float:
        """Height of glyph ``name``: ``WY`` when non-zero, else bbox height."""
        metric = self._char_metrics_map.get(name)
        if metric is None:
            return 0.0
        wy = metric.get_wy()
        if wy != 0.0:
            return wy
        bbox = metric.get_bounding_box()
        return 0.0 if bbox is None else bbox.get_height()

    def get_average_character_width(self) -> float:
        """Mean of non-zero ``WX`` values across :attr:`char_metrics`."""
        total = 0.0
        count = 0
        for metric in self._char_metrics:
            if metric.get_wx() > 0:
                total += metric.get_wx()
                count += 1
        return total / count if count else 0.0

    # ---------- comments ----------

    def add_comment(self, comment: str) -> None:
        self._comments.append(comment)

    def get_comments(self) -> list[str]:
        return list(self._comments)

    # ---------- AFM version ----------

    def get_afm_version(self) -> float:
        return self._afm_version

    def set_afm_version(self, value: float) -> None:
        self._afm_version = float(value)

    # ---------- metricSets ----------

    def get_metric_sets(self) -> int:
        return self._metric_sets

    def set_metric_sets(self, value: int) -> None:
        if value < 0 or value > 2:
            raise ValueError(
                f"The metricSets attribute must be in the set {{0,1,2}} and not '{value}'"
            )
        self._metric_sets = int(value)

    # ---------- header strings ----------

    def get_font_name(self) -> str | None:
        return self._font_name

    def set_font_name(self, value: str | None) -> None:
        self._font_name = value

    def get_full_name(self) -> str | None:
        return self._full_name

    def set_full_name(self, value: str | None) -> None:
        self._full_name = value

    def get_family_name(self) -> str | None:
        return self._family_name

    def set_family_name(self, value: str | None) -> None:
        self._family_name = value

    def get_weight(self) -> str | None:
        return self._weight

    def set_weight(self, value: str | None) -> None:
        self._weight = value

    def get_font_b_box(self) -> BoundingBox | None:
        return self._font_b_box

    def set_font_b_box(self, value: BoundingBox | None) -> None:
        self._font_b_box = value

    def has_font_b_box(self) -> bool:
        """``True`` when a ``FontBBox`` directive has been recorded."""
        return self._font_b_box is not None

    def get_font_version(self) -> str | None:
        return self._font_version

    def set_font_version(self, value: str | None) -> None:
        self._font_version = value

    def get_notice(self) -> str | None:
        return self._notice

    def set_notice(self, value: str | None) -> None:
        self._notice = value

    def get_encoding_scheme(self) -> str | None:
        return self._encoding_scheme

    def set_encoding_scheme(self, value: str | None) -> None:
        self._encoding_scheme = value

    def get_mapping_scheme(self) -> int:
        return self._mapping_scheme

    def set_mapping_scheme(self, value: int) -> None:
        self._mapping_scheme = int(value)

    def get_esc_char(self) -> int:
        return self._esc_char

    def set_esc_char(self, value: int) -> None:
        self._esc_char = int(value)

    def get_character_set(self) -> str | None:
        return self._character_set

    def set_character_set(self, value: str | None) -> None:
        self._character_set = value

    def get_characters(self) -> int:
        return self._characters

    def set_characters(self, value: int) -> None:
        self._characters = int(value)

    # ---------- IsBaseFont ----------

    def get_is_base_font(self) -> bool:
        return self._is_base_font

    def set_is_base_font(self, value: bool) -> None:
        self._is_base_font = bool(value)

    # ---------- VVector / IsFixedV ----------

    def get_v_vector(self) -> tuple[float, float] | None:
        return self._v_vector

    def set_v_vector(self, value: tuple[float, float] | list[float] | None) -> None:
        self._v_vector = (
            None if value is None else (float(value[0]), float(value[1]))
        )

    def has_v_vector(self) -> bool:
        """``True`` when a ``VVector`` directive has been recorded."""
        return self._v_vector is not None

    def get_is_fixed_v(self) -> bool:
        # Match upstream: when not explicitly set, default depends on whether
        # a VVector exists.
        if self._is_fixed_v is None:
            return self._v_vector is not None
        return self._is_fixed_v

    def set_is_fixed_v(self, value: bool) -> None:
        self._is_fixed_v = bool(value)

    # ---------- vertical metrics ----------

    def get_cap_height(self) -> float:
        return self._cap_height

    def set_cap_height(self, value: float) -> None:
        self._cap_height = float(value)

    def get_x_height(self) -> float:
        return self._x_height

    def set_x_height(self, value: float) -> None:
        self._x_height = float(value)

    def get_ascender(self) -> float:
        return self._ascender

    def set_ascender(self, value: float) -> None:
        self._ascender = float(value)

    def get_descender(self) -> float:
        return self._descender

    def set_descender(self, value: float) -> None:
        self._descender = float(value)

    # ---------- underline ----------

    def get_underline_position(self) -> float:
        return self._underline_position

    def set_underline_position(self, value: float) -> None:
        self._underline_position = float(value)

    def get_underline_thickness(self) -> float:
        return self._underline_thickness

    def set_underline_thickness(self, value: float) -> None:
        self._underline_thickness = float(value)

    # ---------- italic / fixed pitch / charwidth ----------

    def get_italic_angle(self) -> float:
        return self._italic_angle

    def set_italic_angle(self, value: float) -> None:
        self._italic_angle = float(value)

    def get_char_width(self) -> tuple[float, float] | None:
        return self._char_width

    def set_char_width(self, value: tuple[float, float] | list[float] | None) -> None:
        self._char_width = (
            None if value is None else (float(value[0]), float(value[1]))
        )

    def has_char_width(self) -> bool:
        """``True`` when a ``CharWidth`` directive has been recorded."""
        return self._char_width is not None

    def get_is_fixed_pitch(self) -> bool:
        return self._is_fixed_pitch

    def set_fixed_pitch(self, value: bool) -> None:
        self._is_fixed_pitch = bool(value)

    # ---------- StdHW / StdVW ----------

    def get_standard_horizontal_width(self) -> float:
        return self._standard_horizontal_width

    def set_standard_horizontal_width(self, value: float) -> None:
        self._standard_horizontal_width = float(value)

    def get_standard_vertical_width(self) -> float:
        return self._standard_vertical_width

    def set_standard_vertical_width(self, value: float) -> None:
        self._standard_vertical_width = float(value)

    # ---------- char metrics ----------

    def get_char_metrics(self) -> list[CharMetric]:
        return list(self._char_metrics)

    def set_char_metrics(self, metrics: list[CharMetric]) -> None:
        self._char_metrics = list(metrics)
        self._char_metrics_map = {
            metric.get_name(): metric
            for metric in self._char_metrics
            if metric.get_name()
        }

    def add_char_metric(self, metric: CharMetric) -> None:
        self._char_metrics.append(metric)
        if metric.get_name():
            self._char_metrics_map[metric.get_name()] = metric

    # ---------- track kern ----------

    def get_track_kern(self) -> list[TrackKern]:
        return list(self._track_kern)

    def add_track_kern(self, kern: TrackKern) -> None:
        self._track_kern.append(kern)

    # ---------- composites ----------

    def get_composites(self) -> list[Composite]:
        return list(self._composites)

    def add_composite(self, composite: Composite) -> None:
        self._composites.append(composite)

    # ---------- kern pairs ----------

    def get_kern_pairs(self) -> list[KernPair]:
        return list(self._kern_pairs)

    def add_kern_pair(self, kern_pair: KernPair) -> None:
        self._kern_pairs.append(kern_pair)

    def get_kern_pairs0(self) -> list[KernPair]:
        return list(self._kern_pairs0)

    def add_kern_pair0(self, kern_pair: KernPair) -> None:
        self._kern_pairs0.append(kern_pair)

    def get_kern_pairs1(self) -> list[KernPair]:
        return list(self._kern_pairs1)

    def add_kern_pair1(self, kern_pair: KernPair) -> None:
        self._kern_pairs1.append(kern_pair)

    def get_total_kern_pair_count(self) -> int:
        """Total number of kern pairs across all three lists.

        Sum of :meth:`get_kern_pairs`, :meth:`get_kern_pairs0`, and
        :meth:`get_kern_pairs1` lengths. Convenience helper not present
        upstream; useful for parity diagnostics where the writing
        direction of a kern pair is not under test.
        """
        return (
            len(self._kern_pairs)
            + len(self._kern_pairs0)
            + len(self._kern_pairs1)
        )
