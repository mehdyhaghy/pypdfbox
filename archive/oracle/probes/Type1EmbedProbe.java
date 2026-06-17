import java.io.File;
import java.io.PrintStream;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;
import org.apache.fontbox.type1.Type1Font;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType1Font;

/**
 * Live oracle probe: confirm Apache PDFBox can READ a Type 1 font that
 * pypdfbox embedded (classic /FontFile program). For each PDType1Font on
 * each page, emit:
 *   - the PDF-level base font name, /FirstChar, /LastChar,
 *   - the per-code advance widths from PDFont.getWidth(code) (the /Widths
 *     array pypdfbox wrote),
 *   - the parsed FontBox Type1Font name + encoding (code -&gt; glyph name)
 *     + per-glyph width, reached through PDType1Font.getType1Font().
 *
 * This is the inverse of Type1FontProbe (which reads a PDFBox-built fixture):
 * here the input PDF is produced by pypdfbox, so a non-empty, parseable
 * emission proves PDFBox accepts pypdfbox's embedded Type 1 output.
 *
 * Usage: java -cp pdfbox-app.jar:build Type1EmbedProbe input.pdf
 *
 * Canonical line format (UTF-8, deterministic ordering):
 *   FONT &lt;index&gt; &lt;resourceName&gt;
 *   BASEFONT &lt;pdBaseFont&gt;
 *   RANGE &lt;firstChar&gt; &lt;lastChar&gt;
 *   PDW &lt;code&gt; &lt;width&gt;          (one per code first..last, getWidth(code))
 *   T1NAME &lt;type1FontName&gt;
 *   ENC &lt;code&gt; &lt;glyphName&gt;       (one per mapped code 0..255, ascending)
 *   GLYPH &lt;name&gt; &lt;hasGlyph&gt; &lt;width&gt;   (one per charstring name, sorted)
 */
public final class Type1EmbedProbe {
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
                    emit(out, fontIndex++, name.getName(), (PDType1Font) font);
                }
            }
        }
    }

    private static void emit(PrintStream out, int idx, String resName, PDType1Font font)
            throws Exception {
        out.println("FONT " + idx + " " + resName);
        out.println("BASEFONT " + font.getName());

        int first = font.getCOSObject().getInt(COSName.FIRST_CHAR, -1);
        int last = font.getCOSObject().getInt(COSName.LAST_CHAR, -1);
        out.println("RANGE " + first + " " + last);
        if (first >= 0 && last >= first) {
            for (int code = first; code <= last; code++) {
                String w;
                try {
                    w = canonNumber(font.getWidth(code));
                } catch (Exception e) {
                    w = "ERR";
                }
                out.println("PDW " + code + " " + w);
            }
        }

        Type1Font t1 = font.getType1Font();
        if (t1 == null) {
            out.println("T1NAME <null>");
            return;
        }
        out.println("T1NAME " + t1.getName());

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

        TreeSet<String> names = new TreeSet<String>(t1.getCharStringsDict().keySet());
        for (String gn : names) {
            boolean has = t1.hasGlyph(gn);
            float w = t1.getWidth(gn);
            out.println("GLYPH " + gn + " " + has + " " + canonNumber(w));
        }
    }

    private static String canonNumber(double v) {
        if (v == Math.rint(v) && !Double.isInfinite(v)) {
            return Long.toString((long) v);
        }
        return Double.toString(v);
    }
}
