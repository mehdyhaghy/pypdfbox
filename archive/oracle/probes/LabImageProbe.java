import java.awt.image.BufferedImage;
import java.awt.image.DataBuffer;
import java.awt.image.Raster;
import java.awt.image.WritableRaster;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDLab;

/**
 * Live oracle probe for the {@code Lab} colour space (PDF 32000-1 §8.6.5.4).
 *
 * <p>Exercises three surfaces of {@link PDLab} on a {@code [/Lab << /WhitePoint
 * [...] /Range [amin amax bmin bmax] >>]} space:
 *
 * <ol>
 *   <li>{@code getNumberOfComponents()} and {@code getInitialColor()} — the
 *       structural surface.</li>
 *   <li>{@code toRGB(float[])} — the single L*a*b* triple → sRGB conversion
 *       (Lab to XYZ with the dictionary {@code /WhitePoint}, then the AWT CMM
 *       XYZ to sRGB step). A battery over D50 and D65 white points and a grid of
 *       L, a, b inputs.</li>
 *   <li>{@code toRGBImage(WritableRaster)} — the raster path. A 3-band,
 *       8-bit interleaved raster is built and converted; the resulting
 *       {@code TYPE_INT_RGB} pixels are emitted so the Python side can gate the
 *       grid with the MAD/MAXDIFF fingerprint.</li>
 * </ol>
 *
 * <p>Output is line-oriented (UTF-8):
 * <pre>
 *   STRUCT &lt;name&gt; &lt;numComponents&gt; ic &lt;c0&gt; &lt;c1&gt; &lt;c2&gt;
 *   RGB &lt;name&gt; L a b -&gt; r g b           (RGB ints 0..255, round(comp*255))
 *   IMG &lt;name&gt; &lt;width&gt; &lt;height&gt;
 *   PX &lt;name&gt; r g b r g b ...            (row-major, one line per image)
 * </pre>
 *
 * <p>Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; LabImageProbe
 */
public final class LabImageProbe {

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

    static void emitStruct(String name, PDLab cs) {
        PDColor ic = cs.getInitialColor();
        float[] c = ic.getComponents();
        StringBuilder sb = new StringBuilder();
        sb.append("STRUCT ").append(name).append(' ');
        sb.append(cs.getNumberOfComponents()).append(" ic");
        for (float v : c) {
            sb.append(' ').append(fmt(v));
        }
        out.println(sb.toString());
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

    static void emitImage(String name, PDLab cs, int width, int height, byte[] samples)
            throws Exception {
        WritableRaster raster = Raster.createInterleavedRaster(
                DataBuffer.TYPE_BYTE, width, height, 3, null);
        int[] pixel = new int[3];
        int idx = 0;
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                pixel[0] = samples[idx++] & 0xFF;
                pixel[1] = samples[idx++] & 0xFF;
                pixel[2] = samples[idx++] & 0xFF;
                raster.setPixel(x, y, pixel);
            }
        }
        BufferedImage img = cs.toRGBImage(raster);
        out.println("IMG " + name + " " + width + " " + height);
        StringBuilder sb = new StringBuilder();
        sb.append("PX ").append(name);
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                int rgb = img.getRGB(x, y);
                sb.append(' ').append((rgb >> 16) & 0xFF);
                sb.append(' ').append((rgb >> 8) & 0xFF);
                sb.append(' ').append(rgb & 0xFF);
            }
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        float[] d50 = new float[] {0.9642f, 1.0f, 0.8249f};
        float[] d65 = new float[] {0.9505f, 1.0f, 1.089f};
        float[] defRange = new float[] {-100, 100, -100, 100};
        float[] asymRange = new float[] {-128, 127, -128, 127};

        PDLab labD50 = lab(d50, defRange);
        PDLab labD65 = lab(d65, defRange);
        PDLab labAsym = lab(d50, asymRange);

        // ---- structural surface ----
        emitStruct("LabD50", labD50);
        emitStruct("LabD65", labD65);
        emitStruct("LabAsym", labAsym);

        // ---- single-value toRGB battery ----
        float[][] inputs = new float[][] {
            {0.0f, 0.0f, 0.0f},
            {100.0f, 0.0f, 0.0f},
            {50.0f, 0.0f, 0.0f},
            {53.23f, 80.11f, 67.22f},   // sRGB red-ish
            {87.74f, -86.18f, 83.18f},  // sRGB green-ish
            {32.30f, 79.20f, -107.86f}, // sRGB blue-ish
            {25.0f, 60.0f, -60.0f},
            {90.0f, -30.0f, 70.0f},
            {75.0f, 20.0f, -40.0f},
            {40.0f, -50.0f, 30.0f},
        };
        for (float[] c : inputs) {
            emitRGB("LabD50", c, labD50);
        }
        for (float[] c : inputs) {
            emitRGB("LabD65", c, labD65);
        }

        // ---- raster path: a 16x16 L* ramp with mid a*/b* ----
        int w = 16;
        int h = 16;
        byte[] ramp = new byte[w * h * 3];
        int p = 0;
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int lByte = (int) Math.round(x * 255.0 / (w - 1));
                int aByte = (int) Math.round(y * 255.0 / (h - 1));
                int bByte = 128;
                ramp[p++] = (byte) lByte;
                ramp[p++] = (byte) aByte;
                ramp[p++] = (byte) bByte;
            }
        }
        emitImage("LabD50", labD50, w, h, ramp);
        emitImage("LabD65", labD65, w, h, ramp);
        emitImage("LabAsym", labAsym, w, h, ramp);
    }
}
