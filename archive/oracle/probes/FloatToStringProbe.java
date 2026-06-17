/**
 * Live oracle probe: raw Java {@code Float.toString} over a sweep of edge
 * values, the algorithm pypdfbox's {@code format_float32} must reproduce
 * byte-for-byte for finite floats.
 *
 * {@code Float.toString} (Java's FloatingDecimal) switches to scientific
 * E-notation when the magnitude is {@code >= 1e7} or {@code < 1e-3}, and inside
 * that window uses plain decimal with at least one fractional digit. The
 * mantissa is the shortest decimal string that round-trips to the float.
 *
 * Each line: "label=<Float.toString(value)>". The values are chosen to pin the
 * 1e7 boundary, the 1e-3 boundary, negatives, subnormals, Float.MAX_VALUE,
 * exact powers of ten, full-mantissa values, and signed zero. The Matrix /
 * Vector toString cases at the bottom exercise the same renderer through
 * org.apache.pdfbox.util.
 */
public final class FloatToStringProbe
{
    private static void p(String label, float v)
    {
        System.out.println(label + "=" + Float.toString(v));
    }

    public static void main(String[] args)
    {
        // --- 1e7 upper boundary (>= 1e7 switches to E-notation) ---
        p("just_below_1e7", 9999999.0f);
        p("at_1e7", 1.0e7f);
        p("just_above_1e7", 1.0000001e7f);
        p("ten_million_one", 10000001.0f);

        // --- 1e-3 lower boundary (< 1e-3 switches to E-notation) ---
        p("at_1e_3", 0.001f);
        p("just_below_1e_3", 9.999999e-4f);
        p("just_above_1e_3", 0.0010001f);

        // --- exact powers of ten spanning the window edges ---
        p("pow_1e6", 1.0e6f);
        p("pow_1e7", 1.0e7f);
        p("pow_1e8", 1.0e8f);
        p("pow_1e_2", 1.0e-2f);
        p("pow_1e_3", 1.0e-3f);
        p("pow_1e_4", 1.0e-4f);
        p("pow_1e10", 1.0e10f);
        p("pow_1e_10", 1.0e-10f);
        p("pow_1e20", 1.0e20f);
        p("pow_1e_20", 1.0e-20f);

        // --- negatives ---
        p("neg_4p2e10", -4.2e10f);
        p("neg_1e8", -1.0e8f);
        p("neg_1p23e_4", -1.23e-4f);
        p("neg_small", -7.5e-5f);

        // --- full-mantissa values needing many digits ---
        p("one_third", 1.0f / 3.0f);
        p("pi", (float) Math.PI);
        p("big_full", 1.2345678e9f);
        p("small_full", 1.2345678e-5f);
        p("e_mantissa", 1.23e-4f);

        // --- subnormals ---
        p("min_value", Float.MIN_VALUE);          // 1.4E-45
        p("subnormal_2", 2.8e-45f);
        p("min_normal", Float.MIN_NORMAL);        // 1.17549435E-38

        // --- Float.MAX_VALUE ---
        p("max_value", Float.MAX_VALUE);          // 3.4028235E38
        p("neg_max_value", -Float.MAX_VALUE);

        // --- signed zero ---
        p("pos_zero", 0.0f);
        p("neg_zero", -0.0f);

        // --- inside-window plain decimals (must NOT regress) ---
        p("one", 1.0f);
        p("hundred", 100.0f);
        p("one_million", 1000000.0f);
        p("frac", 0.5f);
        p("rot_cos", 0.9950042f);

        // --- Matrix / Vector toString rendering through util.* ---
        org.apache.pdfbox.util.Matrix big =
            new org.apache.pdfbox.util.Matrix(1.0e8f, 0f, 0f, 1.0e-4f, 0f, 0f);
        System.out.println("matrix_big=" + big.toString());
        org.apache.pdfbox.util.Vector vbig =
            new org.apache.pdfbox.util.Vector(1.0e8f, 1.4e-45f);
        System.out.println("vector_big=" + vbig.toString());
    }
}
