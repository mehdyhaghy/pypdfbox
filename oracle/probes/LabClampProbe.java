import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.graphics.color.PDLab;

/**
 * Live oracle probe for {@link PDLab#toRGB(float[])} input clamping
 * (PDF 32000-1 §8.6.5.4).
 *
 * <p>Drives {@code PDLab.toRGB} over a battery of L*a*b* triples whose
 * components sit at, below, and above the legal bounds:
 *
 * <ul>
 *   <li>L* is defined on [0, 100]; values below 0 or above 100 probe whether
 *       upstream clamps before the Lab → XYZ companding.</li>
 *   <li>a* / b* are bounded by the dictionary {@code /Range}
 *       ([amin amax bmin bmax], default [-100 100 -100 100]); out-of-range
 *       values probe whether upstream clamps each to its range slot.</li>
 * </ul>
 *
 * <p>The probe never clamps in Java itself — it forwards the raw triple to
 * {@code toRGB} and emits whatever PDFBox produces. The Python side then
 * asserts pypdfbox's {@code to_rgb} reproduces the same clamp-or-no-clamp
 * behaviour (the exact clamp arithmetic matches; the XYZ → sRGB CMM tail
 * uses the documented Lab tolerance tier).
 *
 * <p>Output is line-oriented (UTF-8):
 * <pre>
 *   RGB &lt;name&gt; L a b -&gt; r g b      (RGB ints 0..255, round(comp*255))
 * </pre>
 *
 * <p>Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; LabClampProbe
 */
public final class LabClampProbe {

    static PrintStream out;

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

    static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Integer.toString((int) v);
        }
        return Float.toString(v);
    }

    static COSArray floats(float... vals) {
        COSArray a = new COSArray();
        for (float v : vals) {
            a.add(new COSFloat(v));
        }
        return a;
    }

    static PDLab lab(float[] whitePoint, float[] range) {
        COSArray arr = new COSArray();
        arr.add(COSName.LAB);
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.WHITE_POINT, floats(whitePoint));
        if (range != null) {
            d.setItem(COSName.RANGE, floats(range));
        }
        arr.add(d);
        return new PDLab(arr);
    }

    static void emitRGB(String name, float[] comps, PDLab cs) throws Exception {
        float[] rgb = cs.toRGB(comps);
        StringBuilder sb = new StringBuilder();
        sb.append("RGB ").append(name);
        for (float c : comps) {
            sb.append(' ').append(fmt(c));
        }
        sb.append(" -> ");
        sb.append(clamp255(rgb[0])).append(' ');
        sb.append(clamp255(rgb[1])).append(' ');
        sb.append(clamp255(rgb[2]));
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        float[] d50 = new float[] {0.9642f, 1.0f, 0.8249f};
        float[] defRange = new float[] {-100, 100, -100, 100};
        float[] custom = new float[] {-50, 60, -70, 40};

        PDLab labDef = lab(d50, defRange);
        PDLab labCustom = lab(d50, custom);

        // ---- default-range clamping battery ----
        // L* at / below / above [0, 100]; a*/b* at / outside [-100, 100].
        float[][] defInputs = new float[][] {
            {-10.0f, 0.0f, 0.0f},        // L below 0
            {0.0f, 0.0f, 0.0f},          // L at lower bound
            {150.0f, 0.0f, 0.0f},        // L above 100
            {100.0f, 0.0f, 0.0f},        // L at upper bound
            {50.0f, 200.0f, 0.0f},       // a above amax
            {50.0f, -200.0f, 0.0f},      // a below amin
            {50.0f, 0.0f, 200.0f},       // b above bmax
            {50.0f, 0.0f, -200.0f},      // b below bmin
            {-5.0f, 150.0f, -150.0f},    // L below, a above, b below
            {120.0f, -130.0f, 130.0f},   // L above, a below, b above
            {100.0f, 100.0f, 100.0f},    // all at upper bounds
            {0.0f, -100.0f, -100.0f},    // all at lower bounds
        };
        for (float[] c : defInputs) {
            emitRGB("LabDef", c, labDef);
        }

        // ---- custom-range clamping battery ----
        // /Range [-50 60 -70 40]; probe a*/b* outside the custom slots.
        float[][] customInputs = new float[][] {
            {50.0f, 80.0f, 0.0f},        // a above amax(60)
            {50.0f, -80.0f, 0.0f},       // a below amin(-50)
            {50.0f, 0.0f, 60.0f},        // b above bmax(40)
            {50.0f, 0.0f, -90.0f},       // b below bmin(-70)
            {50.0f, 60.0f, 40.0f},       // a/b at upper bounds
            {50.0f, -50.0f, -70.0f},     // a/b at lower bounds
            {200.0f, 200.0f, -200.0f},   // L above, a above, b below
        };
        for (float[] c : customInputs) {
            emitRGB("LabCustom", c, labCustom);
        }
    }
}
