import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.graphics.color.PDCalGray;
import org.apache.pdfbox.pdmodel.graphics.color.PDCalRGB;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;

/**
 * Live oracle probe for the CIE-based {@code CalRGB} and {@code CalGray}
 * colour-space {@code toRGB} conversions (PDF 32000-1 §8.6.5.2/§8.6.5.3).
 *
 * <p>Builds a {@code PDCalRGB} ({@code /WhitePoint} + {@code /Gamma} +
 * {@code /Matrix}) and a {@code PDCalGray} ({@code /WhitePoint} + {@code /Gamma})
 * from in-memory COS objects and emits {@code "csname comp... -> r g b"} lines
 * (RGB 0-255 ints, {@code round(component*255)} clamped to {@code [0,255]}) for
 * a battery of input tuples so the Python side reconstructs the matching
 * pypdfbox spaces and the same inputs.
 *
 * <p>PDFBox's {@code toRGB} only runs the CIE pipeline (gamma decode -> matrix
 * -> XYZ, then the AWT CMM {@code CIEXYZ.toRGB}) when {@code isWhitePoint()} is
 * true, i.e. the {@code /WhitePoint} is exactly the unit tristimulus
 * {@code (1,1,1)} (a documented PDFBOX-2553 hack). For any other white point it
 * skips calibration and returns the input components verbatim. The probe
 * exercises BOTH branches: the unit-white-point calibrated path and a
 * D65-ish-white-point pass-through path.
 *
 * <p>Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; CalColorProbe
 */
public final class CalColorProbe {

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

    static void emit(String name, float[] comps, PDColorSpace cs) throws Exception {
        float[] rgb = cs.toRGB(comps);
        StringBuilder sb = new StringBuilder();
        sb.append(name);
        for (float c : comps) {
            sb.append(' ').append(fmt(c));
        }
        sb.append(" -> ");
        sb.append(clamp255(rgb[0])).append(' ');
        sb.append(clamp255(rgb[1])).append(' ');
        sb.append(clamp255(rgb[2]));
        out.println(sb.toString());
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

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        float[] unit = new float[] {1.0f, 1.0f, 1.0f};
        float[] d65 = new float[] {0.9505f, 1.0f, 1.089f};

        // ---- CalRGB, unit white point -> calibrated CIE pipeline runs ----
        // Gamma (1.8, 2.2, 2.4), a sRGB-ish primaries matrix (column-major
        // [Xa Ya Za  Xb Yb Zb  Xc Yc Zc]).
        float[] gamma = new float[] {1.8f, 2.2f, 2.4f};
        float[] matrix = new float[] {
            0.4124f, 0.2126f, 0.0193f,
            0.3576f, 0.7152f, 0.1192f,
            0.1805f, 0.0722f, 0.9505f
        };
        PDCalRGB rgbUnit = calRGB(unit, gamma, matrix);
        float[][] rgbInputs = new float[][] {
            {0.0f, 0.0f, 0.0f},
            {1.0f, 1.0f, 1.0f},
            {0.5f, 0.5f, 0.5f},
            {1.0f, 0.0f, 0.0f},
            {0.0f, 1.0f, 0.0f},
            {0.0f, 0.0f, 1.0f},
            {0.5f, 0.0f, 0.0f},
            {0.0f, 0.5f, 0.0f},
            {0.0f, 0.0f, 0.5f},
            {0.3f, 0.6f, 0.9f},
            {0.25f, 0.5f, 0.75f}
        };
        for (float[] c : rgbInputs) {
            emit("CalRgbUnit", c, rgbUnit);
        }

        // ---- CalRGB, identity matrix, gamma 2.2, unit white point ----
        float[] identity = new float[] {1, 0, 0, 0, 1, 0, 0, 0, 1};
        PDCalRGB rgbIdent = calRGB(unit, new float[] {2.2f, 2.2f, 2.2f}, identity);
        for (float[] c : rgbInputs) {
            emit("CalRgbIdent", c, rgbIdent);
        }

        // ---- CalRGB, D65 white point -> calibration SKIPPED (verbatim) ----
        PDCalRGB rgbD65 = calRGB(d65, gamma, matrix);
        for (float[] c : rgbInputs) {
            emit("CalRgbD65", c, rgbD65);
        }

        // ---- CalGray, unit white point -> calibrated path runs ----
        float[] grayInputs = new float[] {0.0f, 0.25f, 0.5f, 0.75f, 1.0f};
        PDCalGray grayUnit22 = calGray(unit, 2.2f);
        for (float g : grayInputs) {
            emit("CalGrayUnit22", new float[] {g}, grayUnit22);
        }
        PDCalGray grayUnit10 = calGray(unit, 1.0f);
        for (float g : grayInputs) {
            emit("CalGrayUnit10", new float[] {g}, grayUnit10);
        }

        // ---- CalGray, D65 white point -> calibration SKIPPED (verbatim) ----
        PDCalGray grayD65 = calGray(d65, 2.2f);
        for (float g : grayInputs) {
            emit("CalGrayD65", new float[] {g}, grayD65);
        }
    }
}
