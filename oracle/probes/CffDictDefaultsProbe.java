import java.io.File;
import java.io.PrintStream;
import java.util.List;
import java.util.Map;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.CFFParser;
import org.apache.fontbox.cff.CFFType1Font;
import org.apache.fontbox.util.BoundingBox;

/**
 * Live oracle probe for CFF Top/Private DICT operator <em>defaults</em>
 * and the {@code /FontMatrix}.
 *
 * <p>Per Adobe Technote #5176 Tables 9 &amp; 23 several DICT operators
 * carry implicit defaults applied when the operator is absent:
 *
 * <ul>
 *   <li>Top DICT {@code /FontMatrix} default {@code [0.001 0 0 0.001 0 0]}</li>
 *   <li>Top DICT {@code /CharstringType} default {@code 2}</li>
 *   <li>Private DICT {@code /defaultWidthX} default {@code 0}</li>
 *   <li>Private DICT {@code /nominalWidthX} default {@code 0}</li>
 *   <li>Private DICT {@code /BlueValues} / {@code /StdHW} / {@code /StdVW}
 *       — no default (absent ⇒ {@code <null>} in the raw Private DICT map)</li>
 * </ul>
 *
 * The differential target is the boundary between the resolved getter
 * ({@code CFFFont.getFontMatrix()}, which materialises the default) and
 * the raw DICT map ({@code CFFFont.getTopDict().get(key)} /
 * {@code CFFType1Font.getPrivateDict().get(key)}, which carries the
 * operator only when it was present in the byte stream).
 *
 * <pre>
 *   java -cp ... CffDictDefaultsProbe &lt;input.cff&gt;
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order):
 *
 *   NAME       \t &lt;CFFFont.getName()&gt;
 *   FONTMATRIX \t &lt;6 space-joined getFontMatrix() values&gt;
 *   FM_RAW     \t &lt;getTopDict().get("FontMatrix") or "&lt;null&gt;"&gt;
 *   FONTBBOX   \t &lt;llx lly urx ury from getFontBBox()&gt; | "&lt;ioexception&gt;"
 *   BBOX_RAW   \t &lt;getTopDict().get("FontBBox") or "&lt;null&gt;"&gt;
 *   TOP        \t CharstringType \t &lt;value or "&lt;null&gt;"&gt;
 *   PRIV       \t &lt;key&gt; \t &lt;value or "&lt;null&gt;"&gt;
 *       For each of: defaultWidthX, nominalWidthX, BlueValues, StdHW, StdVW.
 */
public final class CffDictDefaultsProbe {

    private static final String[] PRIV_KEYS = {
            "defaultWidthX", "nominalWidthX", "BlueValues", "StdHW", "StdVW"
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 1) {
            out.println("usage: CffDictDefaultsProbe <input.cff>");
            return;
        }
        byte[] data = java.nio.file.Files.readAllBytes(new File(args[0]).toPath());
        List<CFFFont> fonts = new CFFParser().parse(data, new CffByteSource(data));
        if (fonts.isEmpty()) {
            out.println("NAME\t<empty>");
            return;
        }
        CFFFont font = fonts.get(0);
        out.printf("NAME\t%s%n", String.valueOf(font.getName()));

        List<Number> fm = font.getFontMatrix();
        StringBuilder fmStr = new StringBuilder();
        for (int i = 0; i < fm.size(); i++) {
            if (i > 0) {
                fmStr.append(' ');
            }
            fmStr.append(fmtNum(fm.get(i)));
        }
        out.printf("FONTMATRIX\t%s%n", fmStr);

        Map<String, Object> topDict = font.getTopDict();
        out.printf("FM_RAW\t%s%n", fmtRaw(topDict.get("FontMatrix")));

        try {
            BoundingBox bbox = font.getFontBBox();
            out.printf("FONTBBOX\t%s %s %s %s%n",
                    fmtNum(bbox.getLowerLeftX()), fmtNum(bbox.getLowerLeftY()),
                    fmtNum(bbox.getUpperRightX()), fmtNum(bbox.getUpperRightY()));
        } catch (java.io.IOException e) {
            out.println("FONTBBOX\t<ioexception>");
        }
        out.printf("BBOX_RAW\t%s%n", fmtRaw(topDict.get("FontBBox")));

        out.printf("TOP\tCharstringType\t%s%n", fmtRaw(topDict.get("CharstringType")));

        if (font instanceof CFFType1Font) {
            Map<String, Object> priv = ((CFFType1Font) font).getPrivateDict();
            for (String key : PRIV_KEYS) {
                out.printf("PRIV\t%s\t%s%n", key, fmtRaw(priv.get(key)));
            }
        } else {
            for (String key : PRIV_KEYS) {
                out.printf("PRIV\t%s\t<nopriv>%n", key);
            }
        }
    }

    /** Render a Number the way our Python str(float|int) round-trips. */
    private static String fmtNum(Number n) {
        double d = n.doubleValue();
        if (d == Math.rint(d) && !Double.isInfinite(d)) {
            return Long.toString((long) d);
        }
        return Double.toString(d);
    }

    /** Render a raw DICT value (possibly a List<Number>) deterministically. */
    private static String fmtRaw(Object value) {
        if (value == null) {
            return "<null>";
        }
        if (value instanceof List) {
            List<?> list = (List<?>) value;
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) {
                    sb.append(' ');
                }
                Object item = list.get(i);
                sb.append(item instanceof Number ? fmtNum((Number) item)
                        : String.valueOf(item));
            }
            return sb.toString();
        }
        if (value instanceof Number) {
            return fmtNum((Number) value);
        }
        return String.valueOf(value);
    }

    /** Minimal ByteSource backing the embedded CFF program. */
    private static final class CffByteSource implements CFFParser.ByteSource {
        private final byte[] bytes;

        CffByteSource(byte[] bytes) {
            this.bytes = bytes;
        }

        @Override
        public byte[] getBytes() {
            return bytes;
        }
    }
}
