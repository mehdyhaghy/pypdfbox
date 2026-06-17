import java.io.PrintStream;
import org.apache.pdfbox.pdmodel.font.encoding.GlyphList;

/**
 * Live oracle probe: emit Apache PDFBox's GlyphList.toUnicode(glyphName) for a
 * battery of glyph names, against either the Adobe Glyph List (AGL) or the Zapf
 * Dingbats glyph list.
 *
 * In PDFBox 3.0.x the glyph list lives at
 * org.apache.pdfbox.pdmodel.font.encoding.GlyphList (the FontBox encoding
 * package was folded into pdmodel.font.encoding); getAdobeGlyphList() and
 * getZapfDingbats() are the two singleton accessors.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> GlyphListProbe <list> <name>...
 *   <list>   "adobe" (AGL) or "zapf" (Zapf Dingbats)
 *   <name>   one or more PostScript glyph names to resolve
 *
 * Output (UTF-8, stdout): one canonical line per input name:
 *   <name> -> U+XXXX[ U+YYYY ...]
 *   <name> -> NULL              when toUnicode returns null
 *
 * Code points are rendered as uppercase hex, zero-padded to at least four
 * digits (U+0041), space-separated for multi-code-point (ligature) sequences.
 * Supplementary-plane scalars are emitted as a single U+XXXXX value (the Java
 * String is iterated by code point, not UTF-16 char, so surrogate pairs render
 * as one value).
 */
public final class GlyphListProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        GlyphList list;
        if ("zapf".equals(args[0])) {
            list = GlyphList.getZapfDingbats();
        } else if ("adobe".equals(args[0])) {
            list = GlyphList.getAdobeGlyphList();
        } else {
            throw new IllegalArgumentException("unknown list: " + args[0]);
        }
        for (int i = 1; i < args.length; i++) {
            String name = args[i];
            String unicode = list.toUnicode(name);
            out.printf("%s -> %s%n", name, format(unicode));
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
