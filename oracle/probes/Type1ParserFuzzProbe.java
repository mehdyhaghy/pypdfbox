import java.nio.file.Files;
import org.apache.fontbox.type1.Type1Font;

/**
 * Live oracle probe for the lenient Type 1 (.pfb) parse contract under
 * malformed input (wave 1507 differential font-parser fuzz; sibling of
 * CffParserFuzzProbe / TtfParserFuzzProbe).
 *
 * Reads raw (possibly corrupt) .pfb bytes from a file, parses them with Apache
 * FontBox's {@link Type1Font#createWithPFB(byte[])} — the entry point
 * pypdfbox's {@code Type1Font.create_with_pfb(bytes)} default maps to — and
 * prints a stable projection of the OUTCOME rather than raw bytes:
 *
 *   ok=true
 *   name=&lt;PostScript name&gt;
 *   fontName=&lt;FontName&gt;
 *   nGlyphs=&lt;int&gt;
 *   subrs=&lt;int&gt;
 *   wA=&lt;advance width of glyph "A"&gt;
 *   enc65=&lt;encoding glyph name for code 65, or "?"&gt;
 *
 * or the sole line
 *
 *   ok=false
 *
 * on any throw from {@code createWithPFB}. The pypdfbox side reproduces this
 * fingerprint exactly so the parity assertion is a single string compare.
 *
 * Usage:
 *   java -cp ... Type1ParserFuzzProbe font.pfb
 */
public final class Type1ParserFuzzProbe {
    private static final String PROBE_GLYPH = "A";
    private static final int PROBE_CODE = 65;

    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(new java.io.File(args[0]).toPath());

        StringBuilder sb = new StringBuilder();
        try {
            Type1Font t1 = Type1Font.createWithPFB(bytes);
            sb.append("ok=true\n");
            sb.append("name=").append(t1.getName()).append('\n');
            sb.append("fontName=").append(t1.getFontName()).append('\n');
            sb.append("nGlyphs=").append(t1.getCharStringsDict().size()).append('\n');
            sb.append("subrs=").append(t1.getSubrsArray().size()).append('\n');
            sb.append("wA=").append(width(t1)).append('\n');
            sb.append("enc65=").append(enc(t1)).append('\n');
        } catch (Throwable t) {
            System.out.print("ok=false\n");
            return;
        }
        System.out.print(sb);
    }

    private static String width(Type1Font t1) {
        try {
            return canonNumber(t1.getWidth(PROBE_GLYPH));
        } catch (Throwable t) {
            return "-1";
        }
    }

    private static String enc(Type1Font t1) {
        try {
            org.apache.fontbox.encoding.Encoding e = t1.getEncoding();
            if (e == null) {
                return "?";
            }
            String gn = e.getName(PROBE_CODE);
            return gn == null ? "?" : gn;
        } catch (Throwable t) {
            return "?";
        }
    }

    private static String canonNumber(double v) {
        if (v == Math.rint(v) && !Double.isInfinite(v)) {
            return Long.toString((long) v);
        }
        return Double.toString(v);
    }
}
