import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;
import org.apache.fontbox.type1.Type1Font;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.cos.COSName;

/**
 * Live oracle probe: for each embedded Type 1 font (PDType1Font backed by a
 * /FontFile program) in a PDF, reach the FontBox Type1Font via getType1Font()
 * and emit its name, font matrix, encoding (code -&gt; glyph name) and the
 * per-glyph width / hasGlyph for the font's own charstring names.
 *
 * Usage: java -cp pdfbox-app.jar:build Type1FontProbe input.pdf
 *
 * Canonical line format (UTF-8, deterministic ordering):
 *   FONT &lt;baseFontKey&gt;
 *   NAME &lt;type1FontName&gt;
 *   MATRIX a b c d e f          (six numbers, Java toString of the doubles)
 *   ENC &lt;code&gt; &lt;glyphName&gt;     (one line per mapped code 0..255, ascending)
 *   GLYPH &lt;name&gt; &lt;hasGlyph&gt; &lt;width&gt;  (one line per charstring name, sorted)
 */
public final class Type1FontProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int fontIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res == null) {
                    continue;
                }
                for (COSName name : res.getFontNames()) {
                    PDFont font = res.getFont(name);
                    if (!(font instanceof PDType1Font)) {
                        continue;
                    }
                    PDType1Font t1Pd = (PDType1Font) font;
                    Type1Font t1 = t1Pd.getType1Font();
                    if (t1 == null) {
                        continue;
                    }
                    emit(out, fontIndex++, t1);
                }
            }
        }
    }

    private static void emit(PrintStream out, int idx, Type1Font t1) throws Exception {
        out.println("FONT " + idx);
        out.println("NAME " + t1.getName());

        List<Number> m = t1.getFontMatrix();
        StringBuilder mb = new StringBuilder("MATRIX");
        for (Number n : m) {
            mb.append(' ').append(canonNumber(n.doubleValue()));
        }
        out.println(mb.toString());

        // Encoding: code -> glyph name for codes 0..255 that map to a name.
        org.apache.fontbox.encoding.Encoding enc = t1.getEncoding();
        TreeMap<Integer, String> codes = new TreeMap<Integer, String>();
        if (enc != null) {
            for (int code = 0; code < 256; code++) {
                String gn = enc.getName(code);
                if (gn != null && !gn.equals(".notdef")) {
                    codes.put(code, gn);
                }
            }
        }
        for (Map.Entry<Integer, String> e : codes.entrySet()) {
            out.println("ENC " + e.getKey() + " " + e.getValue());
        }

        // Glyph widths / hasGlyph for the font's own charstring names.
        TreeSet<String> names = new TreeSet<String>(t1.getCharStringsDict().keySet());
        for (String gn : names) {
            boolean has = t1.hasGlyph(gn);
            float w = t1.getWidth(gn);
            out.println("GLYPH " + gn + " " + has + " " + canonNumber(w));
        }
    }

    // Canonicalise a numeric value so Java and Python render it identically:
    // integral values as plain integers, otherwise a trimmed decimal.
    private static String canonNumber(double v) {
        if (v == Math.rint(v) && !Double.isInfinite(v)) {
            return Long.toString((long) v);
        }
        String s = Double.toString(v);
        return s;
    }
}
