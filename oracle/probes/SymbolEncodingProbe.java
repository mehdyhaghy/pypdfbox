import java.io.PrintStream;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.pdmodel.font.encoding.Encoding;

/**
 * Live oracle probe for the built-in Symbol / ZapfDingbats encoding path on a
 * non-embedded Standard-14 font.
 *
 * A Symbol or ZapfDingbats font carries NO /Encoding entry and NO /ToUnicode
 * stream; PDFBox resolves a code to a glyph name via the font-specific built-in
 * encoding ({@code SymbolEncoding} / {@code ZapfDingbatsEncoding}), then maps
 * the name to Unicode through the matching glyph list (the Adobe Glyph List for
 * Symbol, the Zapf list for ZapfDingbats). This probe pins both halves of that
 * chain — the per-code glyph NAME and the per-code {@code toUnicode} result —
 * which the width-only Std14MetricsProbe never exercised.
 *
 * For each of the two fonts, built via
 * {@code new PDType1Font(Standard14Fonts.FontName.X)}, it emits to stdout
 * (UTF-8):
 *
 *   FONT\t&lt;baseFont&gt;\t&lt;encClass&gt;
 *     &lt;encClass&gt; = simple class name of font.getEncoding(), or "null".
 *   N\t&lt;code&gt;\t&lt;glyphName&gt;            for codes 0..255
 *     &lt;glyphName&gt; = font.getEncoding().getName(code) (".notdef" when no
 *     encoding resolves); pins code -&gt; glyph-name.
 *   U\t&lt;code&gt;\t&lt;U+XXXX[ U+YYYY...]&gt;   for codes 0..255
 *     space-separated hex code points of font.toUnicode(code) via
 *     String.codePoints(); "(none)" when null/empty. Pins code -&gt; unicode.
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; SymbolEncodingProbe
 */
public final class SymbolEncodingProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        PDType1Font[] fonts = {
            new PDType1Font(Standard14Fonts.FontName.SYMBOL),
            new PDType1Font(Standard14Fonts.FontName.ZAPF_DINGBATS),
        };
        for (PDType1Font font : fonts) {
            Encoding enc = font.getEncoding();
            out.printf("FONT\t%s\t%s%n",
                    font.getName(),
                    enc == null ? "null" : enc.getClass().getSimpleName());
            for (int code = 0; code <= 255; code++) {
                String name = enc == null ? ".notdef" : enc.getName(code);
                out.printf("N\t%d\t%s%n", code, name);
            }
            for (int code = 0; code <= 255; code++) {
                String uni;
                try {
                    uni = font.toUnicode(code);
                } catch (Exception e) {
                    uni = null;
                }
                out.printf("U\t%d\t%s%n", code, fmtUnicode(uni));
            }
        }
    }

    private static String fmtUnicode(String uni) {
        if (uni == null || uni.isEmpty()) {
            return "(none)";
        }
        StringBuilder sb = new StringBuilder();
        boolean first = true;
        int[] cps = uni.codePoints().toArray();
        for (int cp : cps) {
            if (!first) {
                sb.append(' ');
            }
            sb.append(String.format("U+%04X", cp));
            first = false;
        }
        return sb.toString();
    }
}
