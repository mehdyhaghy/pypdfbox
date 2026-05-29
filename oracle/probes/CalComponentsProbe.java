import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.graphics.color.PDCalGray;
import org.apache.pdfbox.pdmodel.graphics.color.PDCalRGB;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;

/**
 * Live oracle probe for the {@code PDCalRGB} / {@code PDCalGray}
 * <em>component-count + initial-color + single-value {@code toRGB}</em>
 * surface (PDF 32000-1 §8.6.5.2/§8.6.5.3).
 *
 * <p>Complements {@code CalColorProbe} (which only exercises the {@code toRGB}
 * conversion battery) by also emitting the exact, deterministic parts of the
 * surface that should be byte-identical on both sides:
 *
 * <ul>
 *   <li>{@code COMP <name> <n>} — {@code getNumberOfComponents()}
 *       (CalRGB = 3, CalGray = 1).</li>
 *   <li>{@code INIT <name> c0 [c1 c2]} — {@code getInitialColor()
 *       .getComponents()} (the documented black initial colour).</li>
 *   <li>{@code RGB <name> comp... -> r g b} — single-value {@code toRGB} for a
 *       battery of inputs, RGB as 0-255 ints ({@code round(component*255)}
 *       clamped to {@code [0,255]}).</li>
 * </ul>
 *
 * <p>The {@code toRGB} rows on the unit-white-point (calibrated) spaces carry
 * the documented XYZ->sRGB CMM divergence (PDFBox AWT CMM / D50 PCS vs
 * pypdfbox's explicit IEC 61966-2-1 D65 matrix); the Python side absorbs that
 * with a tolerance. The {@code COMP} / {@code INIT} rows and the
 * identity-matrix pure-primary {@code toRGB} rows are exact.
 *
 * <p>Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; CalComponentsProbe
 */
public final class CalComponentsProbe {

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

    static PDCalRGB calRGB(float[] whitePoint, float[] gamma, float[] matrix) {
        COSArray arr = new COSArray();
        arr.add(COSName.CALRGB);
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.WHITE_POINT, floats(whitePoint));
        d.setItem(COSName.GAMMA, floats(gamma));
        d.setItem(COSName.MATRIX, floats(matrix));
        arr.add(d);
        return new PDCalRGB(arr);
    }

    static PDCalGray calGray(float[] whitePoint, float gamma) {
        COSArray arr = new COSArray();
        arr.add(COSName.CALGRAY);
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.WHITE_POINT, floats(whitePoint));
        d.setItem(COSName.GAMMA, new COSFloat(gamma));
        arr.add(d);
        return new PDCalGray(arr);
    }

    static void emitComp(String name, int n) {
        out.println("COMP " + name + " " + n);
    }

    static void emitInit(String name, PDColor color) {
        StringBuilder sb = new StringBuilder("INIT ").append(name);
        for (float c : color.getComponents()) {
            sb.append(' ').append(fmt(c));
        }
        out.println(sb.toString());
    }

    static void emitRgb(String name, float[] comps, float[] rgb) {
        StringBuilder sb = new StringBuilder("RGB ").append(name);
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

        float[] unit = new float[] {1.0f, 1.0f, 1.0f};
        float[] d65 = new float[] {0.9505f, 1.0f, 1.089f};
        float[] gamma = new float[] {1.8f, 2.2f, 2.4f};
        float[] identity = new float[] {1, 0, 0, 0, 1, 0, 0, 0, 1};
        float[] matrix = new float[] {
            0.4124f, 0.2126f, 0.0193f,
            0.3576f, 0.7152f, 0.1192f,
            0.1805f, 0.0722f, 0.9505f
        };

        PDCalRGB rgbUnit = calRGB(unit, gamma, matrix);
        PDCalRGB rgbIdent = calRGB(unit, new float[] {2.2f, 2.2f, 2.2f}, identity);
        PDCalRGB rgbD65 = calRGB(d65, gamma, matrix);
        PDCalGray grayUnit22 = calGray(unit, 2.2f);
        PDCalGray grayUnit10 = calGray(unit, 1.0f);
        PDCalGray grayD65 = calGray(d65, 2.2f);

        // ---- component counts (exact) ----
        emitComp("CalRgb", rgbUnit.getNumberOfComponents());
        emitComp("CalGray", grayUnit22.getNumberOfComponents());

        // ---- initial colours (exact: black) ----
        emitInit("CalRgb", rgbUnit.getInitialColor());
        emitInit("CalGray", grayUnit22.getInitialColor());

        // ---- single-value toRGB battery ----
        float[][] rgbInputs = new float[][] {
            {0.0f, 0.0f, 0.0f},
            {1.0f, 1.0f, 1.0f},
            {0.5f, 0.5f, 0.5f},
            {1.0f, 0.0f, 0.0f},
            {0.0f, 1.0f, 0.0f},
            {0.0f, 0.0f, 1.0f},
            {0.2f, 0.4f, 0.8f}
        };
        for (float[] c : rgbInputs) {
            emitRgb("CalRgbUnit", c, rgbUnit.toRGB(c));
        }
        for (float[] c : rgbInputs) {
            emitRgb("CalRgbIdent", c, rgbIdent.toRGB(c));
        }
        for (float[] c : rgbInputs) {
            emitRgb("CalRgbD65", c, rgbD65.toRGB(c));
        }

        float[] grayInputs = new float[] {0.0f, 0.2f, 0.5f, 0.8f, 1.0f};
        for (float g : grayInputs) {
            emitRgb("CalGrayUnit22", new float[] {g}, grayUnit22.toRGB(new float[] {g}));
        }
        for (float g : grayInputs) {
            emitRgb("CalGrayUnit10", new float[] {g}, grayUnit10.toRGB(new float[] {g}));
        }
        for (float g : grayInputs) {
            emitRgb("CalGrayD65", new float[] {g}, grayD65.toRGB(new float[] {g}));
        }
    }
}
