import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.graphics.color.PDIndexed;

/**
 * Live oracle probe for {@link PDIndexed#toRGB} index rounding and clamping on
 * a pure DeviceRGB base (no CMM in play — the palette bytes pass straight
 * through {@code DeviceRGB.toRGB}, so the only behaviour exercised is the
 * {@code Math.round}/clamp on the incoming tint value).
 *
 * <p>Upstream {@code PDIndexed.toRGB} (PDIndexed.java line 182) does:
 * <pre>
 *   int index = Math.round(value[0]);   // Java round-half-UP on a float
 *   index = Math.max(index, 0);
 *   index = Math.min(index, actualMaxIndex);
 * </pre>
 * {@code Math.round(float)} == {@code (int) Math.floor(a + 0.5f)} — half values
 * round toward positive infinity, NOT round-half-to-even. So {@code 0.5f -> 1},
 * {@code 2.5f -> 3}. Python's {@code round()} is banker's rounding
 * ({@code round(0.5) == 0}, {@code round(2.5) == 2}), so a naive port diverges
 * on every half-integer tint value.
 *
 * <p>Emits {@code "value -> r g b"} lines (RGB 0-255 ints, palette bytes verbatim).
 * The value token is the exact float literal so the Python side can rebuild it.
 */
public final class IndexedRoundProbe {

    static PrintStream out;

    static PDIndexed indexed(byte[] palette, int hival) throws Exception {
        COSArray arr = new COSArray();
        arr.add(COSName.INDEXED);
        arr.add(COSName.DEVICERGB);
        arr.add(COSInteger.get(hival));
        arr.add(new COSString(palette));
        return new PDIndexed(arr);
    }

    static void emit(PDIndexed cs, float value) {
        float[] rgb = cs.toRGB(new float[] {value});
        int r = Math.round(rgb[0] * 255f);
        int g = Math.round(rgb[1] * 255f);
        int b = Math.round(rgb[2] * 255f);
        out.println(value + " -> " + r + " " + g + " " + b);
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // 4-entry palette, hival = 3.
        byte[] palette = new byte[] {
            (byte) 0, (byte) 0, (byte) 0,        // 0 black
            (byte) 255, (byte) 0, (byte) 0,      // 1 red
            (byte) 0, (byte) 255, (byte) 0,      // 2 green
            (byte) 0, (byte) 0, (byte) 255       // 3 blue
        };
        PDIndexed idx = indexed(palette, 3);

        float[] values = new float[] {
            -1.0f, -0.5f, 0.0f, 0.4f, 0.5f, 0.6f,
            1.0f, 1.4f, 1.5f, 1.6f,
            2.0f, 2.4f, 2.5f, 2.6f,
            3.0f, 3.4f, 3.5f, 3.6f,
            4.0f, 5.0f, 100.0f
        };
        for (float v : values) {
            emit(idx, v);
        }
    }
}
