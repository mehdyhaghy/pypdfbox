import java.io.OutputStream;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.graphics.color.PDLab;
import org.apache.pdfbox.pdmodel.graphics.color.PDTristimulus;

/**
 * Differential fuzz probe for {@code PDLab} (CIE L*a*b* colour space),
 * Apache PDFBox 3.0.7 (wave 1538, agent A).
 *
 * Complements {@code ColorSpaceFuzzProbe} (which only touches a couple of /Lab
 * construction corners) and {@code LabClampProbe} (which pins toRGB over the
 * input domain for two well-formed spaces) by driving the *malformed dictionary*
 * surface of the array form {@code [/Lab << /WhitePoint .. /BlackPoint .. /Range .. >>]}:
 * missing dict, missing/short/non-numeric /WhitePoint, missing/short/reversed
 * /Range, /BlackPoint variants, indirect refs, and toRGB at L* extremes and the
 * a-star / b-star corners.
 *
 * For each case the probe constructs {@code new PDLab(array)} and emits one CASE
 * line projecting every accessor (or the error class when an accessor throws),
 * in the form: ctor, name, nc, wp (whitepoint), bp (blackpoint), rng (range),
 * init (initial colour), then several rgb tags for toRGB at representative points.
 *
 * Floats are formatted "%.4f" (white/black point, range, init) so the float32
 * vs float64 question is visible; toRGB results are rounded to 0-255 ints. The
 * pypdfbox sibling rebuilds the identical corpus and asserts line-for-line, with
 * the documented XYZ-&gt;sRGB CMM divergence pinned both-sides.
 */
public final class LabColorSpaceFuzzProbe {

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

    static COSDictionary labDict(COSBase whitePoint, COSBase blackPoint, COSBase range) {
        COSDictionary d = new COSDictionary();
        if (whitePoint != null) {
            d.setItem(COSName.WHITE_POINT, whitePoint);
        }
        if (blackPoint != null) {
            d.setItem(COSName.BLACK_POINT, blackPoint);
        }
        if (range != null) {
            d.setItem(COSName.RANGE, range);
        }
        return d;
    }

    static COSArray labArray(COSBase dict) {
        COSArray a = new COSArray();
        a.add(COSName.LAB);
        if (dict != null) {
            a.add(dict);
        }
        return a;
    }

    static void appendTri(StringBuilder sb, String tag, PDTristimulus t) {
        sb.append(' ').append(tag).append('=');
        try {
            sb.append(String.format(Locale.ROOT, "%.4f,%.4f,%.4f",
                    t.getX(), t.getY(), t.getZ()));
        } catch (Throwable th) {
            sb.append("ERR");
        }
    }

    // Emit toRGB for a list of triples, space-prefixed "rgb=<tag>:r;g;b".
    static void appendRgb(StringBuilder sb, PDLab cs, String tag, float[] triple) {
        sb.append(" rgb=").append(tag).append(':');
        try {
            float[] rgb = cs.toRGB(triple);
            sb.append(clamp255(rgb[0])).append(';')
              .append(clamp255(rgb[1])).append(';').append(clamp255(rgb[2]));
        } catch (Throwable th) {
            sb.append("ERR");
        }
    }

    static void emit(String name, COSBase labArray) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        PDLab cs;
        try {
            cs = new PDLab((COSArray) labArray);
        } catch (Throwable t) {
            out.println(sb.append("ctor=ERR:").append(t.getClass().getSimpleName())
                    .toString());
            return;
        }
        sb.append("ctor=ok");

        try {
            sb.append(" name=").append(cs.getName());
        } catch (Throwable t) {
            sb.append(" name=ERR");
        }

        try {
            sb.append(" nc=").append(cs.getNumberOfComponents());
        } catch (Throwable t) {
            sb.append(" nc=ERR");
        }

        appendTri(sb, "wp", safeWhite(cs));
        appendTri(sb, "bp", safeBlack(cs));

        sb.append(" rng=");
        try {
            float aMin = cs.getARange().getMin();
            float aMax = cs.getARange().getMax();
            float bMin = cs.getBRange().getMin();
            float bMax = cs.getBRange().getMax();
            sb.append(String.format(Locale.ROOT, "%.4f,%.4f,%.4f,%.4f",
                    aMin, aMax, bMin, bMax));
        } catch (Throwable t) {
            sb.append("ERR");
        }

        sb.append(" init=");
        try {
            float[] init = cs.getInitialColor().getComponents();
            for (int i = 0; i < init.length; i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append(String.format(Locale.ROOT, "%.4f", init[i]));
            }
        } catch (Throwable t) {
            sb.append("ERR");
        }

        // toRGB at representative points: black L=0, white L=100, mid, and
        // a*/b* extremes.
        appendRgb(sb, cs, "L0", new float[] {0f, 0f, 0f});
        appendRgb(sb, cs, "L100", new float[] {100f, 0f, 0f});
        appendRgb(sb, cs, "mid", new float[] {50f, 0f, 0f});
        appendRgb(sb, cs, "aPos", new float[] {50f, 90f, 0f});
        appendRgb(sb, cs, "aNeg", new float[] {50f, -90f, 0f});
        appendRgb(sb, cs, "bPos", new float[] {50f, 0f, 90f});
        appendRgb(sb, cs, "bNeg", new float[] {50f, 0f, -90f});
        appendRgb(sb, cs, "short", new float[] {50f, 0f});

        out.println(sb.toString());
    }

    static PDTristimulus safeWhite(PDLab cs) {
        return cs.getWhitepoint();
    }

    static PDTristimulus safeBlack(PDLab cs) {
        return cs.getBlackPoint();
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        double[] d50 = new double[] {0.9642, 1.0, 0.8249};
        double[] d50bp = new double[] {0.0, 0.0, 0.0};
        double[] defRange = new double[] {-100, 100, -100, 100};
        double[] customRange = new double[] {-128, 127, -128, 127};

        // ===== baseline well-formed =====
        emit("wellformed",
                labArray(labDict(floats(d50), floats(d50bp), floats(customRange))));
        emit("wellformed_defrange",
                labArray(labDict(floats(d50), null, floats(defRange))));
        emit("only_whitepoint",
                labArray(labDict(floats(d50), null, null)));

        // ===== missing dict / empty array =====
        emit("no_dict", labArray(null));
        emit("empty_dict", labArray(new COSDictionary()));

        // ===== /WhitePoint variants =====
        emit("wp_missing",
                labArray(labDict(null, null, floats(defRange))));
        emit("wp_short2",
                labArray(labDict(floats(1, 1), null, null)));
        emit("wp_long4",
                labArray(labDict(floats(1, 1, 1, 1), null, null)));
        emit("wp_zeros",
                labArray(labDict(floats(0, 0, 0), null, null)));
        emit("wp_unit",
                labArray(labDict(floats(1, 1, 1), null, null)));
        emit("wp_empty",
                labArray(labDict(new COSArray(), null, null)));
        emit("wp_not_array",
                labArray(labDict(new COSString("nope"), null, null)));
        emit("wp_ints",
                labArray(labDict(arr(COSInteger.get(1), COSInteger.get(1),
                        COSInteger.get(1)), null, null)));

        // ===== /BlackPoint variants =====
        emit("bp_present",
                labArray(labDict(floats(d50), floats(0.1, 0.1, 0.1), null)));
        emit("bp_short",
                labArray(labDict(floats(d50), floats(0.1, 0.1), null)));
        emit("bp_long",
                labArray(labDict(floats(d50), floats(0.1, 0.1, 0.1, 0.1), null)));
        emit("bp_empty",
                labArray(labDict(floats(d50), new COSArray(), null)));
        emit("bp_not_array",
                labArray(labDict(floats(d50), COSInteger.get(5), null)));

        // ===== /Range variants =====
        emit("range_missing",
                labArray(labDict(floats(d50), null, null)));
        emit("range_short2",
                labArray(labDict(floats(d50), null, floats(-50, 50))));
        emit("range_long6",
                labArray(labDict(floats(d50), null,
                        floats(-50, 50, -50, 50, -50, 50))));
        emit("range_reversed",
                labArray(labDict(floats(d50), null, floats(100, -100, 100, -100))));
        emit("range_empty",
                labArray(labDict(floats(d50), null, new COSArray())));
        emit("range_zeros",
                labArray(labDict(floats(d50), null, floats(0, 0, 0, 0))));
        emit("range_not_array",
                labArray(labDict(floats(d50), null, new COSString("r"))));
        emit("range_ints",
                labArray(labDict(floats(d50), null,
                        arr(COSInteger.get(-100), COSInteger.get(100),
                            COSInteger.get(-100), COSInteger.get(100)))));
        emit("range_asym",
                labArray(labDict(floats(d50), null, floats(-50, 60, -70, 40))));
        emit("range_pos_only",
                labArray(labDict(floats(d50), null, floats(0, 100, 0, 100))));

        // ===== null / COSNull entries =====
        emit("wp_cosnull",
                labArray(labDict(COSNull.NULL, null, null)));
        emit("range_cosnull",
                labArray(labDict(floats(d50), null, COSNull.NULL)));

        // ===== nested stream where array expected =====
        COSStream st = new COSStream();
        OutputStream os = st.createOutputStream();
        os.write(new byte[] {0, 1, 2});
        os.close();
        emit("wp_stream", labArray(labDict(st, null, null)));
    }
}
