import java.io.OutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDSeparation;

/**
 * Live oracle probe for the SPECIAL Separation colorant-name surface
 * (PDF 32000-1 &sect;8.6.6.4): a Separation colour space whose colorant name
 * is {@code /All} (paints every device colorant &mdash; used for registration
 * marks) or {@code /None} (never marks the page &mdash; a no-op). Neither name
 * changes the {@code toRGB} routing in PDFBox: {@code PDSeparation.toRGB}
 * always runs the tint transform and forwards to the alternate colour space.
 * The name only matters at render time, not for {@code toRGB} / the colour
 * model surface.
 *
 * Emits, per built space:
 *   {@code NAME colorant=<name> ncomp=<n> initial=<c0,c1,...>}
 *   {@code NAME tint <t> -> r g b}   (RGB 0-255 ints, round(c*255) clamped)
 *
 * The colorant name and the initial-colour components are exact-match
 * surfaces; the {@code tint -> rgb} lines go through the tint transform +
 * (for CMYK alternates) the JVM CMM, so the Python side classifies them by
 * the alternate colour-management model exactly like the sibling tests.
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; SeparationAllNoneProbe
 */
public final class SeparationAllNoneProbe {

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

    static void describe(String tag, PDSeparation sep) throws Exception {
        StringBuilder sb = new StringBuilder();
        sb.append(tag);
        sb.append(" colorant=").append(sep.getColorantName());
        sb.append(" ncomp=").append(sep.getNumberOfComponents());
        PDColor init = sep.getInitialColor();
        float[] comps = init.getComponents();
        sb.append(" initial=");
        for (int i = 0; i < comps.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(fmt(comps[i]));
        }
        out.println(sb.toString());
    }

    static void tint(String tag, PDSeparation sep, float t) throws Exception {
        float[] rgb = sep.toRGB(new float[] {t});
        out.println(tag + " tint " + fmt(t) + " -> "
                + clamp255(rgb[0]) + " " + clamp255(rgb[1]) + " "
                + clamp255(rgb[2]));
    }

    static COSDictionary type2(float[] c0, float[] c1, float n) {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        COSArray domain = new COSArray();
        domain.add(new COSFloat(0));
        domain.add(new COSFloat(1));
        d.setItem(COSName.DOMAIN, domain);
        COSArray a0 = new COSArray();
        for (float v : c0) {
            a0.add(new COSFloat(v));
        }
        d.setItem(COSName.C0, a0);
        COSArray a1 = new COSArray();
        for (float v : c1) {
            a1.add(new COSFloat(v));
        }
        d.setItem(COSName.C1, a1);
        d.setItem(COSName.N, new COSFloat(n));
        return d;
    }

    static COSStream type4(float[] domain, float[] range, String ps)
            throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 4);
        COSArray dom = new COSArray();
        for (float v : domain) {
            dom.add(new COSFloat(v));
        }
        s.setItem(COSName.DOMAIN, dom);
        COSArray rng = new COSArray();
        for (float v : range) {
            rng.add(new COSFloat(v));
        }
        s.setItem(COSName.RANGE, rng);
        OutputStream os = s.createOutputStream();
        os.write(ps.getBytes("US-ASCII"));
        os.close();
        return s;
    }

    static PDSeparation sep(String colorant, COSName alternate, Object tint)
            throws Exception {
        COSArray arr = new COSArray();
        arr.add(COSName.SEPARATION);
        arr.add(COSName.getPDFName(colorant));
        arr.add(alternate);
        if (tint instanceof COSDictionary) {
            arr.add((COSDictionary) tint);
        } else {
            arr.add((COSStream) tint);
        }
        return new PDSeparation(arr);
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        float[] tints = new float[] {0.0f, 0.25f, 0.5f, 0.75f, 1.0f};

        // ---------- /All -> DeviceCMYK : tint t -> (t,t,t,t) ----------
        // /All paints every colorant. At t=1 the tint maps to full CMYK
        // (registration black); at t=0 to white.
        PDSeparation allCmyk = sep("All", COSName.DEVICECMYK,
                type2(new float[] {0, 0, 0, 0},
                      new float[] {1, 1, 1, 1}, 1.0f));
        describe("AllCmyk", allCmyk);
        for (float t : tints) {
            tint("AllCmyk", allCmyk, t);
        }

        // ---------- /All -> DeviceGray : tint t -> gray 1-t (exact tier) ----
        PDSeparation allGray = sep("All", COSName.DEVICEGRAY,
                type4(new float[] {0, 1}, new float[] {0, 1},
                      "{ 1 exch sub }"));
        describe("AllGray", allGray);
        for (float t : tints) {
            tint("AllGray", allGray, t);
        }

        // ---------- /None -> DeviceCMYK : tint t -> (0,0,0,t) ----------
        // /None never marks the page at render time, but toRGB still runs the
        // tint transform unchanged.
        PDSeparation noneCmyk = sep("None", COSName.DEVICECMYK,
                type2(new float[] {0, 0, 0, 0},
                      new float[] {0, 0, 0, 1}, 1.0f));
        describe("NoneCmyk", noneCmyk);
        for (float t : tints) {
            tint("NoneCmyk", noneCmyk, t);
        }

        // ---------- /None -> DeviceGray : tint t -> gray 1-t (exact tier) ---
        PDSeparation noneGray = sep("None", COSName.DEVICEGRAY,
                type4(new float[] {0, 1}, new float[] {0, 1},
                      "{ 1 exch sub }"));
        describe("NoneGray", noneGray);
        for (float t : tints) {
            tint("NoneGray", noneGray, t);
        }

        // ---------- default ctor: empty colorant, initial color ----------
        PDSeparation empty = new PDSeparation();
        describe("Empty", empty);
    }
}
