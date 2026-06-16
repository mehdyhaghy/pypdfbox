import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.graphics.color.PDCalGray;
import org.apache.pdfbox.pdmodel.graphics.color.PDCalRGB;
import org.apache.pdfbox.pdmodel.graphics.color.PDGamma;
import org.apache.pdfbox.pdmodel.graphics.color.PDTristimulus;

/**
 * Differential fuzz probe for the CIE calibrated colour-space ACCESSOR surface
 * of {@code PDCalRGB} / {@code PDCalGray}, Apache PDFBox 3.0.7 (wave 1538,
 * agent B).
 *
 * <p>Where the wave-1512 {@code ColorSpaceFuzzProbe} drives
 * {@code PDColorSpace.create(COSBase)} construction leniency at a high level,
 * and {@code CalColorProbe} pins the well-formed {@code toRGB} CIE math, this
 * probe drills into the dictionary-accessor surface for the array forms
 * {@code [/CalRGB <<...>>]} / {@code [/CalGray <<...>>]} with malformed
 * {@code /WhitePoint}, {@code /BlackPoint}, {@code /Gamma} and (CalRGB)
 * {@code /Matrix}: missing, wrong-length, non-numeric, zero/negative,
 * indirect-ish, empty.
 *
 * <p>Every case keeps a dictionary present in slot 1 so BOTH sides construct
 * successfully (upstream's base ctor NPEs when slot 1 is not a dictionary — that
 * permissive-create divergence is already pinned by the wave-1512 corpus, so it
 * is out of scope here).
 *
 * <p>Each case is projected to a structural digest line:
 * <pre>
 *   CASE &lt;name&gt; nc=&lt;n&gt; gamma=&lt;...|ERR&gt; matrix=&lt;len:v,v,..|ERR|NA&gt; \
 *       wp=&lt;x,y,z|ERR&gt; bp=&lt;x,y,z|ERR&gt; init=&lt;a,..|ERR&gt; rgb=&lt;r;g;b|ERR|CMM&gt;
 * </pre>
 *
 * <p>{@code rgb} is {@code toRGB} of a sample. To stay on byte-exact ground we
 * only emit a real {@code rgb=} digest for the NON-unit-white-point cases (the
 * documented PDFBOX-2553 pass-through branch returns the input components
 * verbatim, identical on both sides modulo the &lt;=1/255 float-vs-double x.5
 * rounding artifact). Unit-white-point cases route the final XYZ-&gt;sRGB step
 * through the JVM AWT CMM, which pypdfbox replaces with an explicit IEC
 * 61966-2-1 D65 matrix — that divergence is already pinned by
 * {@code test_cal_color_oracle.py}, so this probe emits {@code rgb=CMM} (a
 * marker, not compared) for them.
 *
 * <p>Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; CalColorSpaceFuzzProbe
 */
public final class CalColorSpaceFuzzProbe {

    static PrintStream out;

    static COSName n(String s) {
        return COSName.getPDFName(s);
    }

    static int clamp255(float v) {
        long r = Math.round((double) v * 255.0);
        if (r < 0) {
            return 0;
        }
        if (r > 255) {
            return 255;
        }
        return (int) r;
    }

    static COSArray arr(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase b : items) {
            a.add(b);
        }
        return a;
    }

    static COSArray floats(double... vals) {
        COSArray a = new COSArray();
        for (double v : vals) {
            a.add(new COSFloat((float) v));
        }
        return a;
    }

    static String f3(float v) {
        return String.format(Locale.ROOT, "%.3f", v);
    }

    // Build a /CalGray or /CalRGB outer array given an inner dictionary.
    static COSArray cal(COSName head, COSDictionary d) {
        return arr(head, d);
    }

    static void emitRGB(String name, COSDictionary d, boolean unitWP, float[] sample) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        PDCalRGB cs;
        try {
            cs = new PDCalRGB(cal(COSName.CALRGB, d));
        } catch (Throwable t) {
            out.println(sb.append("ctor=ERR").toString());
            return;
        }
        sb.append("nc=").append(cs.getNumberOfComponents());
        // gamma -> PDGamma.getR/G/B (built atomically: a partial read leaves no
        // partial text, mirroring the Python sibling's atomic projection).
        try {
            PDGamma g = cs.getGamma();
            String triple = f3(g.getR()) + ',' + f3(g.getG()) + ',' + f3(g.getB());
            sb.append(" gamma=").append(triple);
        } catch (Throwable t) {
            sb.append(" gamma=ERR");
        }
        // matrix
        try {
            float[] m = cs.getMatrix();
            StringBuilder mb = new StringBuilder();
            mb.append(m.length).append(':');
            for (int i = 0; i < m.length; i++) {
                if (i > 0) {
                    mb.append(',');
                }
                mb.append(f3(m[i]));
            }
            sb.append(" matrix=").append(mb);
        } catch (Throwable t) {
            sb.append(" matrix=ERR");
        }
        appendWpBpInit(sb, cs.getWhitepoint(), cs.getBlackPoint(),
                () -> cs.getInitialColor().getComponents());
        appendRgb(sb, unitWP, () -> cs.toRGB(sample));
        out.println(sb.toString());
    }

    static void emitGray(String name, COSDictionary d, boolean unitWP, float[] sample) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        PDCalGray cs;
        try {
            cs = new PDCalGray(cal(COSName.CALGRAY, d));
        } catch (Throwable t) {
            out.println(sb.append("ctor=ERR").toString());
            return;
        }
        sb.append("nc=").append(cs.getNumberOfComponents());
        // gamma -> single float
        try {
            sb.append(" gamma=").append(f3(cs.getGamma()));
        } catch (Throwable t) {
            sb.append(" gamma=ERR");
        }
        sb.append(" matrix=NA");
        appendWpBpInit(sb, cs.getWhitepoint(), cs.getBlackPoint(),
                () -> cs.getInitialColor().getComponents());
        appendRgb(sb, unitWP, () -> cs.toRGB(sample));
        out.println(sb.toString());
    }

    interface FloatArr {
        float[] get() throws Exception;
    }

    static void appendWpBpInit(StringBuilder sb, PDTristimulus wp,
            PDTristimulus bp, FloatArr init) {
        // Each digest field is built atomically (a partial read on a short /
        // non-numeric array leaves no partial text), mirroring the Python
        // sibling's atomic projection.
        try {
            String t3 = f3(wp.getX()) + ',' + f3(wp.getY()) + ',' + f3(wp.getZ());
            sb.append(" wp=").append(t3);
        } catch (Throwable t) {
            sb.append(" wp=ERR");
        }
        try {
            String t3 = f3(bp.getX()) + ',' + f3(bp.getY()) + ',' + f3(bp.getZ());
            sb.append(" bp=").append(t3);
        } catch (Throwable t) {
            sb.append(" bp=ERR");
        }
        try {
            float[] c = init.get();
            StringBuilder ib = new StringBuilder();
            for (int i = 0; i < c.length; i++) {
                if (i > 0) {
                    ib.append(',');
                }
                ib.append(f3(c[i]));
            }
            sb.append(" init=").append(ib);
        } catch (Throwable t) {
            sb.append(" init=ERR");
        }
    }

    static void appendRgb(StringBuilder sb, boolean unitWP, FloatArr toRGB) {
        if (unitWP) {
            // XYZ->sRGB CMM divergence already pinned by test_cal_color_oracle.
            sb.append(" rgb=CMM");
            return;
        }
        try {
            float[] rgb = toRGB.get();
            sb.append(" rgb=").append(clamp255(rgb[0])).append(';')
              .append(clamp255(rgb[1])).append(';').append(clamp255(rgb[2]));
        } catch (Throwable t) {
            sb.append(" rgb=ERR");
        }
    }

    // Convenience: PDColor.getComponents wrapper so the lambda compiles.
    // (PDCalRGB/PDCalGray expose getInitialColor().getComponents().)

    static COSDictionary d(COSArray wp, COSArray bp, COSBase gamma, COSArray matrix) {
        COSDictionary dd = new COSDictionary();
        if (wp != null) {
            dd.setItem(COSName.WHITE_POINT, wp);
        }
        if (bp != null) {
            dd.setItem(COSName.BLACK_POINT, bp);
        }
        if (gamma != null) {
            dd.setItem(COSName.GAMMA, gamma);
        }
        if (matrix != null) {
            dd.setItem(COSName.MATRIX, matrix);
        }
        return dd;
    }

    static final double[] UNIT = {1, 1, 1};
    static final double[] D65 = {0.9505, 1.0, 1.089};

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        float[] s3 = {0.4f, 0.6f, 0.8f};
        float[] s1 = {0.4f};

        // ===================== CalRGB =====================
        // empty dict: WhitePoint defaults (1,1,1) -> unit -> CMM path; matrix
        // identity; gamma (1,1,1); bp (0,0,0).
        emitRGB("rgb_empty_dict", d(null, null, null, null), true, s3);
        // unit whitepoint, explicit gamma/matrix.
        emitRGB("rgb_unit_full",
                d(floats(UNIT), floats(0, 0, 0),
                        floats(1.8, 2.2, 2.4),
                        floats(0.4124, 0.2126, 0.0193,
                               0.3576, 0.7152, 0.1192,
                               0.1805, 0.0722, 0.9505)),
                true, s3);
        // D65 (non-unit) whitepoint -> pass-through rgb (byte-exact).
        emitRGB("rgb_d65_full",
                d(floats(D65), floats(0, 0, 0),
                        floats(1.8, 2.2, 2.4),
                        floats(0.4124, 0.2126, 0.0193,
                               0.3576, 0.7152, 0.1192,
                               0.1805, 0.0722, 0.9505)),
                false, s3);
        // D65, missing gamma -> default (1,1,1); pass-through.
        emitRGB("rgb_d65_no_gamma",
                d(floats(D65), null, null, null), false, s3);
        // D65, missing matrix -> identity default; pass-through.
        emitRGB("rgb_d65_no_matrix",
                d(floats(D65), null, floats(1, 1, 1), null), false, s3);
        // D65, gamma wrong length (2 elems) -> getB() OOB -> ERR in gamma proj;
        // pass-through rgb unaffected (non-unit wp returns verbatim).
        emitRGB("rgb_d65_gamma_short",
                d(floats(D65), null, floats(2.0, 2.0), null), false, s3);
        // D65, gamma 4 elems -> getR/G/B read first three, extras ignored.
        emitRGB("rgb_d65_gamma_long",
                d(floats(D65), null, floats(1.5, 1.6, 1.7, 1.8), null),
                false, s3);
        // D65, gamma non-numeric -> getR cast ClassCastException -> ERR.
        emitRGB("rgb_d65_gamma_nonnum",
                d(floats(D65), null, arr(n("a"), n("b"), n("c")), null),
                false, s3);
        // D65, gamma not an array (single number) -> getCOSArray null ->
        // default (1,1,1).
        emitRGB("rgb_d65_gamma_scalar",
                d(floats(D65), null, new COSFloat(2.2f), null), false, s3);
        // D65, matrix short (4 elems) -> getMatrix returns the 4-elem array
        // verbatim (no length guard upstream).
        emitRGB("rgb_d65_matrix_short",
                d(floats(D65), null, floats(1, 1, 1), floats(1, 0, 0, 1)),
                false, s3);
        // D65, matrix not an array (scalar) -> getCOSArray null -> identity.
        COSDictionary matrixScalar = d(floats(D65), null, floats(1, 1, 1), null);
        matrixScalar.setItem(COSName.MATRIX, new COSFloat(5.0f));
        emitRGB("rgb_d65_matrix_scalar", matrixScalar, false, s3);
        // D65, whitepoint short (2 elems) -> getZ OOB -> wp=ERR.
        emitRGB("rgb_wp_short",
                d(floats(1, 1), null, null, null), false, s3);
        // D65, whitepoint non-numeric -> wp=ERR.
        emitRGB("rgb_wp_nonnum",
                d(arr(n("x"), n("y"), n("z")), null, null, null), false, s3);
        // whitepoint negative -> non-unit -> pass-through.
        emitRGB("rgb_wp_negative",
                d(floats(-1, -1, -1), null, null, null), false, s3);
        // whitepoint zeros -> non-unit -> pass-through.
        emitRGB("rgb_wp_zeros",
                d(floats(0, 0, 0), null, null, null), false, s3);
        // blackpoint short -> bp=ERR (not used by toRGB).
        emitRGB("rgb_bp_short",
                d(floats(D65), floats(0, 0), null, null), false, s3);
        // blackpoint long (5) -> getX/Y/Z read first three.
        emitRGB("rgb_bp_long",
                d(floats(D65), floats(0.1, 0.2, 0.3, 0.4, 0.5), null, null),
                false, s3);
        // whitepoint long (4) -> getX/Y/Z first three; here (1,1,1,5) -> unit.
        emitRGB("rgb_wp_long_unit",
                d(floats(1, 1, 1, 5), null, null, null), true, s3);
        // gamma empty array -> getR OOB -> ERR.
        emitRGB("rgb_gamma_empty",
                d(floats(D65), null, new COSArray(), null), false, s3);
        // matrix empty array -> getMatrix len 0.
        emitRGB("rgb_matrix_empty",
                d(floats(D65), null, floats(1, 1, 1), new COSArray()),
                false, s3);

        // ===================== CalGray =====================
        emitGray("gray_empty_dict", d(null, null, null, null), true, s1);
        emitGray("gray_unit_g22",
                d(floats(UNIT), floats(0, 0, 0), new COSFloat(2.2f), null),
                true, s1);
        emitGray("gray_d65_g22",
                d(floats(D65), floats(0, 0, 0), new COSFloat(2.2f), null),
                false, s1);
        emitGray("gray_d65_no_gamma",
                d(floats(D65), null, null, null), false, s1);
        // gamma as array (not a scalar) -> getFloat falls back to default 1.0.
        emitGray("gray_d65_gamma_array",
                d(floats(D65), null, floats(2.2, 2.2, 2.2), null), false, s1);
        // gamma integer (COSInteger) -> getFloat coerces.
        emitGray("gray_d65_gamma_int",
                d(floats(D65), null, COSInteger.get(3), null), false, s1);
        // gamma name (non-numeric) -> getFloat default 1.0.
        emitGray("gray_d65_gamma_name",
                d(floats(D65), null, n("foo"), null), false, s1);
        // gamma string -> getFloat default 1.0.
        emitGray("gray_d65_gamma_string",
                d(floats(D65), null, new COSString("2.2"), null), false, s1);
        emitGray("gray_wp_short",
                d(floats(1, 1), null, null, null), false, s1);
        emitGray("gray_wp_nonnum",
                d(arr(n("x"), n("y"), n("z")), null, null, null), false, s1);
        emitGray("gray_wp_zeros",
                d(floats(0, 0, 0), null, null, null), false, s1);
        emitGray("gray_wp_negative",
                d(floats(-1, -1, -1), null, null, null), false, s1);
        emitGray("gray_bp_short",
                d(floats(D65), floats(0, 0), null, null), false, s1);
        emitGray("gray_wp_long_unit",
                d(floats(1, 1, 1, 9), null, null, null), true, s1);
        // gamma negative on D65 -> pass-through (gamma unused on this branch).
        emitGray("gray_d65_gamma_neg",
                d(floats(D65), null, new COSFloat(-2.0f), null), false, s1);
    }
}
