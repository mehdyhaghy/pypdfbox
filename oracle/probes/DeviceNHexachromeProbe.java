import java.io.OutputStream;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceN;

/**
 * Live oracle probe for a HIGH-COLORANT (N&ge;5) DeviceN colour space — a
 * hexachrome space with six named colorants and only a tint transform (no
 * {@code /Attributes}), exercising the tint-transform -&gt; alternate -&gt; RGB
 * path at full arity.
 *
 * Array form:
 *   [/DeviceN [/Cyan /Magenta /Yellow /Black /Orange /Green] /DeviceCMYK
 *    &lt;type-4 tint&gt;]
 *
 * The Type-4 tint transform maps the 6 tints (c m y k o g) onto a 4-channel
 * CMYK value by:
 *   C = c + 0.7*g
 *   M = m + 0.5*o
 *   Y = y + 0.9*o + 0.6*g
 *   K = k
 * (each clamped to [0,1] by the function /Range), exercising real
 * cross-channel mixing so several inputs differ. Written in pure stack
 * Type-4 PostScript (no named-variable {@code def}, which PDFBox rejects).
 *
 * Emitted lines (Python reproduces verbatim):
 *
 *   COLORANTS &lt;n0&gt; ... &lt;n5&gt;            getColorantNames
 *   NUMCOMPONENTS &lt;n&gt;                  getNumberOfComponents
 *   NCHANNEL &lt;true|false&gt;             isNChannel
 *   ALTERNATE &lt;name&gt;                  getAlternateColorSpace().getName
 *   INITIAL &lt;c0&gt; ... &lt;c5&gt;             getInitialColor().getComponents
 *   TORGB &lt;c0&gt;.. -&gt; &lt;r&gt; &lt;g&gt; &lt;b&gt;       toRGB (0-255 ints, round(c*255) clamped)
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; DeviceNHexachromeProbe
 */
public final class DeviceNHexachromeProbe {

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

    static COSStream type4(float[] domain, float[] range, String ps) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 4);
        COSArray dom = new COSArray();
        for (float v : domain) {
            dom.add(new org.apache.pdfbox.cos.COSFloat(v));
        }
        s.setItem(COSName.DOMAIN, dom);
        COSArray rng = new COSArray();
        for (float v : range) {
            rng.add(new org.apache.pdfbox.cos.COSFloat(v));
        }
        s.setItem(COSName.RANGE, rng);
        OutputStream os = s.createOutputStream();
        os.write(ps.getBytes("US-ASCII"));
        os.close();
        return s;
    }

    static void emit(float[] comps, PDDeviceN cs) throws Exception {
        float[] rgb = cs.toRGB(comps);
        StringBuilder sb = new StringBuilder();
        sb.append("TORGB");
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

        // Six named colorants (hexachrome: CMYK + Orange + Green).
        COSArray names = new COSArray();
        names.add(COSName.getPDFName("Cyan"));
        names.add(COSName.getPDFName("Magenta"));
        names.add(COSName.getPDFName("Yellow"));
        names.add(COSName.getPDFName("Black"));
        names.add(COSName.getPDFName("Orange"));
        names.add(COSName.getPDFName("Green"));

        // Domain: 6 channels [0,1]; range: 4 CMYK channels [0,1].
        float[] domain = {0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1};
        float[] range = {0, 1, 0, 1, 0, 1, 0, 1};
        // Stack order on entry bottom..top: c m y k o g (g = index 0).
        // Pure-stack PostScript (PDFBox's Type-4 engine has no named-var
        // /def). C = c + 0.7g ; M = m + 0.5o ; Y = y + 0.9o + 0.6g ; K = k.
        // /Range clamps each output to [0,1].
        String ps =
            "{ "
            + "5 index 1 index 0.7 mul add "            // C
            + "5 index 3 index 0.5 mul add "            // M
            + "5 index 4 index 0.9 mul add 3 index 0.6 mul add " // Y
            + "5 index "                                // K
            + "}";
        COSStream tint = type4(domain, range, ps);

        COSArray arr = new COSArray();
        arr.add(COSName.DEVICEN);
        arr.add(names);
        arr.add(COSName.DEVICECMYK);
        arr.add(tint);
        PDDeviceN devicen = new PDDeviceN(arr);

        StringBuilder cn = new StringBuilder("COLORANTS");
        for (String n : devicen.getColorantNames()) {
            cn.append(' ').append(n);
        }
        out.println(cn.toString());

        out.println("NUMCOMPONENTS " + devicen.getNumberOfComponents());
        out.println("NCHANNEL " + devicen.isNChannel());
        out.println("ALTERNATE " + devicen.getAlternateColorSpace().getName());

        PDColor initial = devicen.getInitialColor();
        StringBuilder ic = new StringBuilder("INITIAL");
        for (float v : initial.getComponents()) {
            ic.append(' ').append(fmt(v));
        }
        out.println(ic.toString());

        List<float[]> tints = new ArrayList<>();
        tints.add(new float[] {0, 0, 0, 0, 0, 0});
        tints.add(new float[] {1, 1, 1, 1, 1, 1});
        tints.add(new float[] {1, 0, 0, 0, 0, 0});
        tints.add(new float[] {0, 0, 0, 0, 1, 0});
        tints.add(new float[] {0, 0, 0, 0, 0, 1});
        tints.add(new float[] {0.2f, 0.4f, 0.6f, 0.1f, 0.8f, 0.3f});
        tints.add(new float[] {0.5f, 0.5f, 0.5f, 0, 0.5f, 0.5f});
        for (float[] t : tints) {
            emit(t, devicen);
        }
    }
}
