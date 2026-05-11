from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pd_function_type0 import PDFunctionType0


class Rinterpol:
    """N-dimensional sample-table interpolation helper.

    Mirrors the private inner class ``PDFunctionType0.Rinterpol`` (Java
    lines 252-373). Exposed publicly here so callers can drive
    interpolation manually for testing or batch evaluation; in normal use
    the parent function calls into the same arithmetic via
    :meth:`pypdfbox.pdmodel.common.function.pd_function_type0.PDFunctionType0._interpolate_linear`.

    The algorithm is described as bilinear / trilinear / ... interpolation
    over the integer-grid samples surrounding the (possibly fractional)
    input coordinates. ``input_prev[i]`` and ``input_next[i]`` are the
    floor/ceil grid indices along axis ``i`` and ``input[i]`` is the
    fractional coordinate. The result has one float per output dimension.
    """

    def __init__(
        self,
        function: PDFunctionType0,
        input: list[float],  # noqa: A002 - upstream parameter name
        input_prev: list[int],
        input_next: list[int],
    ) -> None:
        self._function: PDFunctionType0 = function
        self._in: list[float] = input
        self._in_prev: list[int] = input_prev
        self._in_next: list[int] = input_next
        self._number_of_input_values: int = len(input)
        self._number_of_output_values: int = (
            function.get_number_of_output_parameters()
        )

    # ---------- entry point ----------

    def rinterpolate(self) -> list[float]:
        """Drive the recursive interpolation. Mirrors upstream
        ``rinterpolate()`` (Java line 284).
        """
        return self._rinterpol([0] * self._number_of_input_values, 0)

    # ---------- recursive descent ----------

    def _rinterpol(self, coord: list[int], step: int) -> list[float]:
        """Recursive linear-interpolation helper. Mirrors upstream
        ``rinterpol(int[], int)`` (Java line 299).
        """
        result_sample: list[float] = [0.0] * self._number_of_output_values
        if step == len(self._in) - 1:
            # Leaf step — interpolate between two adjacent grid samples.
            if self._in_prev[step] == self._in_next[step]:
                coord[step] = self._in_prev[step]
                tmp_sample = self._function.get_samples()[
                    self._calc_sample_index(coord)
                ]
                for i in range(self._number_of_output_values):
                    result_sample[i] = float(tmp_sample[i])
                return result_sample
            coord[step] = self._in_prev[step]
            sample1 = self._function.get_samples()[
                self._calc_sample_index(coord)
            ]
            coord[step] = self._in_next[step]
            sample2 = self._function.get_samples()[
                self._calc_sample_index(coord)
            ]
            for i in range(self._number_of_output_values):
                result_sample[i] = self._function.interpolate(
                    self._in[step],
                    float(self._in_prev[step]),
                    float(self._in_next[step]),
                    float(sample1[i]),
                    float(sample2[i]),
                )
            return result_sample
        # Branch step — recurse on the next axis.
        if self._in_prev[step] == self._in_next[step]:
            coord[step] = self._in_prev[step]
            return self._rinterpol(coord, step + 1)
        coord[step] = self._in_prev[step]
        sample1f = self._rinterpol(coord, step + 1)
        coord[step] = self._in_next[step]
        sample2f = self._rinterpol(coord, step + 1)
        for i in range(self._number_of_output_values):
            result_sample[i] = self._function.interpolate(
                self._in[step],
                float(self._in_prev[step]),
                float(self._in_next[step]),
                sample1f[i],
                sample2f[i],
            )
        return result_sample

    # ---------- sample-index arithmetic ----------

    def calc_sample_index(self, vector: list[int]) -> int:
        """Compute the flat sample index from an N-D coordinate.

        Mirrors upstream ``calcSampleIndex(int[])`` (Java line 351).
        """
        size_values = self._function.get_size().to_float_array()
        index = 0
        size_product = 1
        dimension = len(vector)
        for i in range(dimension - 2, -1, -1):
            size_product *= int(size_values[i])
        for i in range(dimension - 1, -1, -1):
            index += size_product * vector[i]
            if i - 1 >= 0:
                size_product //= int(size_values[i - 1])
        return index

    # Underscore-prefixed alias for in-module callers.
    _calc_sample_index = calc_sample_index

    def get_samples(self) -> list[list[int]]:
        """Mirror of upstream's ``getSamples`` accessor."""
        return self._function.get_samples()


__all__ = ["Rinterpol"]
