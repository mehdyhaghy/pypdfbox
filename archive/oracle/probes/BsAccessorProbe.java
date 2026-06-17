import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.graphics.PDLineDashPattern;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary;

/**
 * Live oracle probe for the PDBorderStyleDictionary (/BS) TYPED ACCESSOR
 * DEFAULTS — the exact getWidth() / getStyle() / getDashStyle() behaviour
 * Apache PDFBox 3.0.7 exposes when each key is present vs. absent.
 *
 * This is narrower and more default-focused than BorderStyleProbe (which
 * round-trips a built fixture): here every interesting branch of the three
 * getters is exercised in isolation on a hand-built COSDictionary, so a
 * divergence in a single default value is pinpointed.
 *
 * Facts probed (PDF 32000-1 §12.5.4 / Table 166):
 *   getWidth():
 *     - empty dict (no /W)           -> default 1 (getFloat(W, 1f))
 *     - /W 0                          -> 0 (no border)
 *     - /W 2.5                        -> 2.5
 *     - /W as a COSName (Adobe quirk) -> 0 (contradicts spec; PDFBox returns 0)
 *   getStyle():
 *     - empty dict (no /S)            -> "S"  (getNameAsString(S, "S"))
 *     - /S /D                         -> "D"
 *   getDashStyle():
 *     - empty dict (no /D)            -> NON-NULL, seeds [3] into the dict,
 *                                        and the dict NOW carries /D = [3]
 *                                        (mutating accessor — upstream quirk)
 *     - /D [4 2]                      -> [4.0, 2.0]
 *
 * Output: UTF-8, one "key=value" line per fact, LF-terminated.
 *
 * Usage:  java -cp <pdfbox-app.jar>:<build> BsAccessorProbe facts
 */
public final class BsAccessorProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 1 || !"facts".equals(args[0])) {
            throw new IllegalArgumentException("usage: BsAccessorProbe facts");
        }
        StringBuilder sb = new StringBuilder();

        // ---- getWidth() ----
        sb.append("width_empty=").append(canon(empty().getWidth())).append('\n');

        PDBorderStyleDictionary w0 = empty();
        w0.setWidth(0f);
        sb.append("width_zero=").append(canon(w0.getWidth())).append('\n');

        PDBorderStyleDictionary w25 = empty();
        w25.getCOSObject().setItem(COSName.W, new COSFloat(2.5f));
        sb.append("width_2p5=").append(canon(w25.getWidth())).append('\n');

        PDBorderStyleDictionary wname = empty();
        wname.getCOSObject().setItem(COSName.W, COSName.getPDFName("Foo"));
        sb.append("width_name=").append(canon(wname.getWidth())).append('\n');

        // ---- getStyle() ----
        sb.append("style_empty=").append(empty().getStyle()).append('\n');

        PDBorderStyleDictionary sd = empty();
        sd.setStyle(PDBorderStyleDictionary.STYLE_DASHED);
        sb.append("style_dashed=").append(sd.getStyle()).append('\n');

        // ---- getDashStyle() ----
        PDBorderStyleDictionary dEmpty = empty();
        PDLineDashPattern p = dEmpty.getDashStyle();
        sb.append("dash_empty_null=").append(p == null).append('\n');
        sb.append("dash_empty_arr=").append(floats(p == null ? null : p.getDashArray())).append('\n');
        // Mutating side effect: /D is now seeded with [3].
        COSArray seeded = dEmpty.getCOSObject().getCOSArray(COSName.D);
        sb.append("dash_empty_seeded=").append(seeded == null ? "none" : floats(seeded.toFloatArray())).append('\n');

        PDBorderStyleDictionary dPresent = empty();
        COSArray arr = new COSArray();
        arr.add(COSInteger.get(4));
        arr.add(COSInteger.get(2));
        dPresent.getCOSObject().setItem(COSName.D, arr);
        sb.append("dash_present_arr=").append(floats(dPresent.getDashStyle().getDashArray())).append('\n');

        out.print(sb);
    }

    private static PDBorderStyleDictionary empty() {
        return new PDBorderStyleDictionary(new COSDictionary());
    }

    private static String floats(float[] a) {
        if (a == null || a.length == 0) {
            return "none";
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < a.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(canon(a[i]));
        }
        return sb.toString();
    }

    /** Round half-even to 3 decimals, strip trailing zeros/dot, normalise -0. */
    private static String canon(double value) {
        java.math.BigDecimal bd = new java.math.BigDecimal(value)
                .setScale(3, java.math.RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if ("-0".equals(s) || s.isEmpty()) {
            s = "0";
        }
        return s;
    }
}
