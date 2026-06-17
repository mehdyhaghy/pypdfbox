import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.cff.CFFType1Font;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType1CFont;
import org.apache.pdfbox.pdmodel.font.encoding.Encoding;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for the embedded simple Type1C (CFF /FontFile3 /Subtype
 * /Type1C) font surface of {@link PDType1CFont}.
 *
 * For every embedded {@code PDType1CFont} on every page it emits, per font:
 *   FONT  &lt;page&gt; &lt;resourceKey&gt; &lt;baseFont&gt; &lt;encodingName&gt;
 *   MATRIX a b c d e f                (getFontMatrix, six canonical doubles)
 * and per byte code 0..255:
 *   ROW &lt;code&gt; &lt;codeToName&gt; &lt;nameToGID&gt; &lt;getWidth&gt; &lt;getWidthFromFont&gt; &lt;hasGlyphCode&gt; &lt;hasGlyphName&gt;
 *
 * The GID is resolved through the embedded CFFType1Font's nameToGID, exactly
 * the lookup pypdfbox's PDType1CFont.code_to_gid performs (charset index).
 *
 * Usage: java -cp pdfbox-app.jar:build Type1CSimpleFontProbe input.pdf
 */
public final class Type1CSimpleFontProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res == null) {
                    pageIndex++;
                    continue;
                }
                for (COSName name : res.getFontNames()) {
                    PDFont font = res.getFont(name);
                    if (!(font instanceof PDType1CFont)) {
                        continue;
                    }
                    PDType1CFont t1c = (PDType1CFont) font;
                    if (!t1c.isEmbedded()) {
                        continue;
                    }
                    emit(out, pageIndex, name.getName(), t1c);
                }
                pageIndex++;
            }
        }
    }

    private static void emit(PrintStream out, int pageIndex, String key, PDType1CFont t1c)
            throws Exception {
        Encoding enc = t1c.getEncoding();
        String encName = enc == null ? "null" : enc.getClass().getSimpleName();
        out.println("FONT\t" + pageIndex + "\t" + key + "\t" + t1c.getName() + "\t" + encName);

        Matrix m = t1c.getFontMatrix();
        out.println("MATRIX\t"
                + canon(m.getScaleX()) + "\t" + canon(m.getShearY()) + "\t"
                + canon(m.getShearX()) + "\t" + canon(m.getScaleY()) + "\t"
                + canon(m.getTranslateX()) + "\t" + canon(m.getTranslateY()));

        // getStringWidth over the font's own charstring names that map back to
        // a single code point — a deterministic differential for the
        // glyph-list -> CFF advance summation. We use a fixed uppercase +
        // lowercase Latin run present in every Times subset in the fixtures.
        out.println("STRWIDTH\t" + canon(t1c.getStringWidth("ABCabc")));

        CFFType1Font cff = t1c.getCFFType1Font();
        for (int code = 0; code < 256; code++) {
            String gn = t1c.codeToName(code);
            int gid = (cff != null && gn != null) ? cff.nameToGID(gn) : 0;
            float width = t1c.getWidth(code);
            float fromFont = t1c.getWidthFromFont(code);
            boolean hasCode = t1c.hasGlyph(code);
            boolean hasName = gn != null && t1c.hasGlyph(gn);
            out.println("ROW\t" + code + "\t" + (gn == null ? "null" : gn) + "\t" + gid
                    + "\t" + canon(width) + "\t" + canon(fromFont)
                    + "\t" + hasCode + "\t" + hasName);
        }
    }

    // Canonicalise a numeric value so Java and Python render it identically:
    // round to 4 d.p. then trim to match Python's "%.4f".
    private static String canon(double v) {
        return String.format(java.util.Locale.ROOT, "%.4f", v);
    }
}
