"""Port of ``org.apache.pdfbox.jbig2.image.FilterType`` and ``Filter``.

These are the resampling-kernel definitions used by the JBIG2 scaling pipeline
(:mod:`pypdfbox.jbig2.image.resizer`). :class:`FilterType` mirrors the upstream
``enum`` (same member order, same ``Triangle`` default); :class:`Filter` is the
abstract base with the ``cardinal`` / ``support`` / ``blur`` attributes and one
nested concrete subclass per kernel, exactly as upstream nests them as static
inner classes of ``Filter``.

Every kernel's ``f(x)`` is ported verbatim; the polynomial coefficient tables in
:class:`Bessel` are copied byte-for-byte. ``Math.*`` maps to :mod:`math`.
"""

from __future__ import annotations

import math
from enum import Enum


class FilterType(Enum):
    """Mirror ``org.apache.pdfbox.jbig2.image.FilterType`` (member order kept)."""

    BESSEL = "Bessel"
    BLACKMAN = "Blackman"
    BOX = "Box"
    CATROM = "Catrom"
    CUBIC = "Cubic"
    GAUSSIAN = "Gaussian"
    HAMMING = "Hamming"
    HANNING = "Hanning"
    HERMITE = "Hermite"
    LANCZOS = "Lanczos"
    MITCHELL = "Mitchell"
    POINT = "Point"
    QUADRATIC = "Quadratic"
    SINC = "Sinc"
    TRIANGLE = "Triangle"

    # The upstream enum holds a mutable static default initialised to Triangle.
    # Exposed via the get/set classmethods below so the static-default surface
    # matches upstream.
    @classmethod
    def set_default_filter_type(cls, default_filter: FilterType) -> None:
        """Mirror ``FilterType.setDefaultFilterType``."""
        cls._default_filter = default_filter

    @classmethod
    def get_default_filter_type(cls) -> FilterType:
        """Mirror ``FilterType.getDefaultFilterType``."""
        return cls._default_filter


FilterType._default_filter = FilterType.TRIANGLE  # type: ignore[attr-defined]


class Filter:
    """Abstract resampling kernel. Mirrors ``org.apache.pdfbox.jbig2.image.Filter``.

    ``cardinal`` — does ``func(x) == (x == 0)`` for integer x?
    ``support``  — radius of the non-zero portion.
    ``blur``     — blur factor (1 = normal).
    """

    def __init__(
        self, cardinal: bool = True, support: float = 1.0, blur: float = 1.0
    ) -> None:
        self.cardinal = cardinal
        self.support = support
        self.blur = blur

    # --- factory / name helpers --------------------------------------------

    @staticmethod
    def name_by_type(type_: FilterType) -> str:
        """Mirror ``Filter.nameByType``."""
        if type_ is None:
            raise ValueError("type must not be null")
        return type_.value

    @staticmethod
    def type_by_name(name: str) -> FilterType:
        """Mirror ``Filter.typeByName`` (``FilterType.valueOf``)."""
        if name is None:
            raise ValueError("name must not be null")
        for member in FilterType:
            if member.value == name:
                return member
        raise ValueError(f"No enum constant FilterType.{name}")

    @staticmethod
    def by_type(type_: FilterType) -> Filter:
        """Mirror ``Filter.byType``."""
        impl = _BY_TYPE.get(type_)
        if impl is None:
            raise ValueError("No filter for given type.")
        return impl()

    # --- kernel API ---------------------------------------------------------

    def f_windowed(self, x: float) -> float:
        """Mirror ``Filter.fWindowed``."""
        return 0.0 if x < -self.support or x > self.support else self.f(x)

    def f(self, x: float) -> float:
        """The continuous filter function. Overridden by each kernel."""
        raise NotImplementedError

    def get_name(self) -> str:
        """Mirror ``Filter.getName`` — the simple class name."""
        return type(self).__name__

    def get_support(self) -> float:
        return self.support

    def set_support(self, support: float) -> None:
        self.support = support

    def get_blur(self) -> float:
        return self.blur

    def set_blur(self, blur: float) -> None:
        self.blur = blur


class Bessel(Filter):
    def __init__(self) -> None:
        super().__init__(False, 3.2383, 1.0)

    def _j1(self, x: float) -> float:
        p_one = [
            0.581199354001606143928050809e21,
            -0.6672106568924916298020941484e20,
            0.2316433580634002297931815435e19,
            -0.3588817569910106050743641413e17,
            0.2908795263834775409737601689e15,
            -0.1322983480332126453125473247e13,
            0.3413234182301700539091292655e10,
            -0.4695753530642995859767162166e7,
            0.270112271089232341485679099e4,
        ]
        q_one = [
            0.11623987080032122878585294e22,
            0.1185770712190320999837113348e20,
            0.6092061398917521746105196863e17,
            0.2081661221307607351240184229e15,
            0.5243710262167649715406728642e12,
            0.1013863514358673989967045588e10,
            0.1501793594998585505921097578e7,
            0.1606931573481487801970916749e4,
            0.1e1,
        ]
        p = p_one[8]
        q = q_one[8]
        for i in range(7, -1, -1):
            p = p * x * x + p_one[i]
            q = q * x * x + q_one[i]
        return p / q

    def _p1(self, x: float) -> float:
        p_one = [
            0.352246649133679798341724373e5,
            0.62758845247161281269005675e5,
            0.313539631109159574238669888e5,
            0.49854832060594338434500455e4,
            0.2111529182853962382105718e3,
            0.12571716929145341558495e1,
        ]
        q_one = [
            0.352246649133679798068390431e5,
            0.626943469593560511888833731e5,
            0.312404063819041039923015703e5,
            0.4930396490181088979386097e4,
            0.2030775189134759322293574e3,
            0.1e1,
        ]
        p = p_one[5]
        q = q_one[5]
        for i in range(4, -1, -1):
            p = p * (8.0 / x) * (8.0 / x) + p_one[i]
            q = q * (8.0 / x) * (8.0 / x) + q_one[i]
        return p / q

    def _q1(self, x: float) -> float:
        p_one = [
            0.3511751914303552822533318e3,
            0.7210391804904475039280863e3,
            0.4259873011654442389886993e3,
            0.831898957673850827325226e2,
            0.45681716295512267064405e1,
            0.3532840052740123642735e-1,
        ]
        q_one = [
            0.74917374171809127714519505e4,
            0.154141773392650970499848051e5,
            0.91522317015169922705904727e4,
            0.18111867005523513506724158e4,
            0.1038187585462133728776636e3,
            0.1e1,
        ]
        p = p_one[5]
        q = q_one[5]
        for i in range(4, -1, -1):
            p = p * (8.0 / x) * (8.0 / x) + p_one[i]
            q = q * (8.0 / x) * (8.0 / x) + q_one[i]
        return p / q

    def _bessel_order_one(self, x: float) -> float:
        if x == 0.0:
            return 0.0
        p = x
        if x < 0.0:
            x = -x
        if x < 8.0:
            return p * self._j1(x)
        q = math.sqrt(2.0 / (math.pi * x)) * (
            self._p1(x) * (1.0 / math.sqrt(2.0) * (math.sin(x) - math.cos(x)))
            - 8.0 / x * self._q1(x)
            * (-1.0 / math.sqrt(2.0) * (math.sin(x) + math.cos(x)))
        )
        if p < 0.0:
            q = -q
        return q

    def f(self, x: float) -> float:
        if x == 0.0:
            return math.pi / 4.0
        return self._bessel_order_one(math.pi * x) / (2.0 * x)


class Blackman(Filter):
    def f(self, x: float) -> float:
        return (
            0.42
            + 0.50 * math.cos(math.pi * x)
            + 0.08 * math.cos(2.0 * math.pi * x)
        )


class Box(Filter):
    def __init__(self, supp: float = 0.5) -> None:
        super().__init__(True, supp, 1.0)

    def f(self, x: float) -> float:
        if -0.5 <= x < 0.5:
            return 1.0
        return 0.0


class Point(Box):
    def __init__(self) -> None:
        super().__init__(0)

    def f_windowed(self, x: float) -> float:
        # don't apply windowing as we have a radius of zero.
        return super().f(x)


class Catrom(Filter):
    def __init__(self) -> None:
        super().__init__(True, 2.0, 1.0)

    def f(self, x: float) -> float:
        if x < 0:
            x = -x
        if x < 1.0:
            return 0.5 * (2.0 + x * x * (-5.0 + x * 3.0))
        if x < 2.0:
            return 0.5 * (4.0 + x * (-8.0 + x * (5.0 - x)))
        return 0.0


class Cubic(Filter):
    def __init__(self) -> None:
        super().__init__(False, 2.0, 1.0)

    def f(self, x: float) -> float:
        if x < 0:
            x = -x
        if x < 1.0:
            return 0.5 * x * x * x - x * x + 2.0 / 3.0
        if x < 2.0:
            x = 2.0 - x
            return 1.0 / 6.0 * x * x * x
        return 0.0


class Gaussian(Filter):
    def __init__(self) -> None:
        super().__init__(False, 1.25, 1.0)

    def f(self, x: float) -> float:
        return math.exp(-2.0 * x * x) * math.sqrt(2.0 / math.pi)


class Hamming(Filter):
    def f(self, x: float) -> float:
        return 0.54 + 0.46 * math.cos(math.pi * x)


class Hanning(Filter):
    def f(self, x: float) -> float:
        return 0.5 + 0.5 * math.cos(math.pi * x)


class Hermite(Filter):
    def f(self, x: float) -> float:
        if x < 0:
            x = -x
        if x < 1.0:
            return (2.0 * x - 3.0) * x * x + 1.0
        return 0.0


class Lanczos(Filter):
    def __init__(self) -> None:
        super().__init__(True, 3.0, 1.0)

    def f(self, x: float) -> float:
        if x < 0:
            x = -x
        if x < 3.0:
            # Upstream casts the product to float (single precision) before
            # returning; reproduce that truncation so the discrete weights match.
            return _to_float32(self._sinc(x) * self._sinc(x / 3.0))
        return 0.0

    def _sinc(self, value: float) -> float:
        if value != 0.0:
            value = value * math.pi
            return math.sin(value) / value
        return 1.0


class Mitchell(Filter):
    def __init__(self) -> None:
        super().__init__(False, 2.0, 1.0)

    def f(self, x: float) -> float:
        b = 1.0 / 3.0
        c = 1.0 / 3.0
        if x < 0:
            x = -x
        if x < 1.0:
            x = (
                (12.0 - 9.0 * b - 6.0 * c) * (x * x * x)
                + (-18.0 + 12.0 * b + 6.0 * c) * x * x
                + (6.0 - 2.0 * b)
            )
            return x / 6.0
        if x < 2.0:
            x = (
                (-1.0 * b - 6.0 * c) * (x * x * x)
                + (6.0 * b + 30.0 * c) * x * x
                + (-12.0 * b - 48.0 * c) * x
                + (8.0 * b + 24.0 * c)
            )
            return x / 6.0
        return 0.0


class Quadratic(Filter):
    def __init__(self) -> None:
        super().__init__(False, 1.5, 1.0)

    def f(self, x: float) -> float:
        if x < 0:
            x = -x
        if x < 0.5:
            return 0.75 - x * x
        if x < 1.5:
            x -= 1.5
            return 0.5 * x * x
        return 0.0


class Sinc(Filter):
    def __init__(self) -> None:
        super().__init__(True, 4.0, 1.0)

    def f(self, x: float) -> float:
        x *= math.pi
        if x != 0.0:
            return math.sin(x) / x
        return 1.0


class Triangle(Filter):
    def f(self, x: float) -> float:
        if x < 0.0:
            x = -x
        if x < 1.0:
            return 1.0 - x
        return 0.0


_BY_TYPE: dict[FilterType, type[Filter]] = {
    FilterType.BESSEL: Bessel,
    FilterType.BLACKMAN: Blackman,
    FilterType.BOX: Box,
    FilterType.CATROM: Catrom,
    FilterType.CUBIC: Cubic,
    FilterType.GAUSSIAN: Gaussian,
    FilterType.HAMMING: Hamming,
    FilterType.HANNING: Hanning,
    FilterType.HERMITE: Hermite,
    FilterType.LANCZOS: Lanczos,
    FilterType.MITCHELL: Mitchell,
    FilterType.POINT: Point,
    FilterType.QUADRATIC: Quadratic,
    FilterType.SINC: Sinc,
    FilterType.TRIANGLE: Triangle,
}


def _to_float32(value: float) -> float:
    """Truncate a double to single precision, mirroring Java's ``(float)`` cast."""
    import struct

    return struct.unpack("f", struct.pack("f", value))[0]
