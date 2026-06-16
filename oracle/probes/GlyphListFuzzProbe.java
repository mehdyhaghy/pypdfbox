import java.io.PrintStream;
import org.apache.pdfbox.pdmodel.font.encoding.Encoding;
import org.apache.pdfbox.pdmodel.font.encoding.GlyphList;
import org.apache.pdfbox.pdmodel.font.encoding.MacRomanEncoding;
import org.apache.pdfbox.pdmodel.font.encoding.StandardEncoding;
import org.apache.pdfbox.pdmodel.font.encoding.SymbolEncoding;
import org.apache.pdfbox.pdmodel.font.encoding.WinAnsiEncoding;
import org.apache.pdfbox.pdmodel.font.encoding.ZapfDingbatsEncoding;

/**
 * Live oracle probe: differential-fuzz the Adobe Glyph List
 * {@code toUnicode(name)} synthesis edge cases AND the five built-in
 * code -> glyph-name encoding tables, in one run.
 *
 * Distinct from {@code GlyphListProbe} (single-list name battery, no encoding
 * tables) and {@code SymbolEncodingProbe} (Standard-14 font path): this probe
 * combines a harder glyph-name battery (odd-length / non-hex / case-mixed
 * uniXXXX, surrogate boundaries U+D7FF/U+E000, multi-dot suffixes, a leading
 * dot, very long names, dingbat aNN names against the AGL) with a sweep of the
 * five built-in encodings' {@code getName(code)} over boundary codes.
 *
 * In PDFBox 3.0.x the encoding classes live at
 * {@code org.apache.pdfbox.pdmodel.font.encoding.*}; the five predefined
 * encodings are exposed as {@code INSTANCE} singletons. The glyph list is the
 * AGL singleton {@code GlyphList.getAdobeGlyphList()}.
 *
 * Output (UTF-8, stdout), stable line order:
 *
 *   G\t&lt;name&gt;\t&lt;U+XXXX[ U+YYYY...] | NULL&gt;
 *     one line per glyph name in the battery; the canonical toUnicode result
 *     rendered as space-separated uppercase >=4-hex code points, or NULL.
 *     The empty-string name is emitted with a literal "(empty)" token so the
 *     line stays parseable.
 *
 *   E\t&lt;encId&gt;\t&lt;code&gt;\t&lt;glyphName&gt;
 *     one line per (encoding, code) pair over the boundary code sweep;
 *     &lt;glyphName&gt; = encoding.getName(code) (".notdef" when unmapped).
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; GlyphListFuzzProbe
 */
public final class GlyphListFuzzProbe {

    private static final String[] NAMES = {
        // -- known AGL names (sanity anchors) --------------------------------
        "A", "space", "Euro", "bullet",
        // -- uniXXXX synthesis: valid (length 7, 4 hex) ----------------------
        "uni0041", "uni20AC", "uniFFFF", "uni0000",
        // -- uniXXXX case sensitivity (lower vs upper hex) -------------------
        "uniabcd", "uniABCD", "uniDeAd",
        // -- uniXXXX wrong length -> NULL ------------------------------------
        "uni041", "uni00041", "uni0041AB",
        // -- uniXXXX non-hex digit -> NULL -----------------------------------
        "uniGGGG", "uniXY12", "uni00G1",
        // -- uXXXX synthesis: valid (length 5, 4 hex) ------------------------
        "u0041", "u20AC", "uFFFF",
        // -- uXXXX wrong length -> NULL (4/5/6/7 hex) ------------------------
        "u041", "u00041", "u041234", "u0412345",
        // -- u case + non-hex -> NULL ----------------------------------------
        "uabcd", "uGGGG",
        // -- surrogate / disallowed-area boundaries --------------------------
        "uniD7FF", "uniD800", "uniDFFF", "uniE000", "uD800", "uDFFF",
        // -- multi-code-point uni run upstream does NOT synthesize -> NULL ----
        "uni00410042",
        // -- dotted suffix stripping (foo.suffix -> foo) ---------------------
        "a.sc", "one.oldstyle", "A.sc", "uni0041.sc", "g123.alt",
        // -- multi-dot and leading-dot suffix edge cases ---------------------
        "a.sc.alt", ".notdef", ".notdef.alt",
        // -- ligature names (multi-code-point AGL values) --------------------
        "ff", "ffi", "fi", "fl", "ffl",
        // -- gNN / cidNN / dingbat aNN names (no AGL entry, no synthesis) -----
        "g65", "cid65", "a10",
        // -- whitespace, very long, and unknown names ------------------------
        "  ", "averylongglyphnamethatisdefinitelynotinanyadobeglyphlistatall",
        "notaglyph", "fi_lig", "",
    };

    private static final int[] CODES = {0, 32, 127, 128, 160, 255};

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        GlyphList agl = GlyphList.getAdobeGlyphList();
        for (String name : NAMES) {
            String unicode = agl.toUnicode(name);
            String key = name.isEmpty() ? "(empty)" : name;
            out.printf("G\t%s\t%s%n", key, format(unicode));
        }

        Encoding[] encodings = {
            StandardEncoding.INSTANCE,
            WinAnsiEncoding.INSTANCE,
            MacRomanEncoding.INSTANCE,
            SymbolEncoding.INSTANCE,
            ZapfDingbatsEncoding.INSTANCE,
        };
        String[] ids = {"Standard", "WinAnsi", "MacRoman", "Symbol", "ZapfDingbats"};
        for (int e = 0; e < encodings.length; e++) {
            for (int code : CODES) {
                out.printf("E\t%s\t%d\t%s%n", ids[e], code, encodings[e].getName(code));
            }
        }
    }

    private static String format(String unicode) {
        if (unicode == null) {
            return "NULL";
        }
        StringBuilder sb = new StringBuilder();
        int i = 0;
        while (i < unicode.length()) {
            int cp = unicode.codePointAt(i);
            if (sb.length() > 0) {
                sb.append(' ');
            }
            sb.append(String.format("U+%04X", cp));
            i += Character.charCount(cp);
        }
        return sb.toString();
    }
}
