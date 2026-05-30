import java.io.File;
import java.io.PrintStream;
import java.util.TreeSet;
import org.apache.fontbox.type1.Type1Font;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.encoding.Encoding;

/**
 * Live oracle probe for reading a simple Type 1 font that embeds its program
 * as a classic raw /FontFile (segmented PFA/PFB with /Length1//Length2/
 * /Length3). This is the PD-level read surface of {@link PDType1Font} — as
 * distinct from {@code Type1FontProbe}, which reaches the FontBox
 * {@code Type1Font} and dumps the program's own charstring table. Here we
 * exercise the methods a renderer/text-extractor actually calls on the
 * PDFont: {@code isEmbedded()}, the resolved {@code getEncoding()} (which for
 * a /FontFile font with no /Encoding dict comes from the program's built-in
 * encoding — {@code getEncodingFromFont}), {@code codeToName(code)},
 * {@code getWidth(code)}, and {@code hasGlyph(name)}.
 *
 * Usage: java -cp pdfbox-app.jar:build Type1FontFileReadProbe input.pdf
 *
 * Canonical line format (UTF-8, deterministic ordering):
 *   FONT &lt;baseFont&gt; &lt;subType&gt; &lt;embedded&gt; &lt;hasFontFile&gt; &lt;programName&gt;
 *   ENC &lt;encClass&gt;                     simple class name of getEncoding()
 *   CODE &lt;code&gt; &lt;glyphName&gt; &lt;width&gt;    for codes 0..255: encoding name +
 *                                        getWidth(code) via canonNumber
 *   HASGLYPH &lt;name&gt; &lt;true|false&gt;        for each charstring name, sorted
 */
public final class Type1FontFileReadProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
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
                    emit(out, (PDType1Font) font);
                }
            }
        }
    }

    private static void emit(PrintStream out, PDType1Font font) throws Exception {
        boolean embedded = font.isEmbedded();
        boolean hasFontFile =
                font.getFontDescriptor() != null
                        && font.getFontDescriptor().getFontFile() != null;
        Type1Font program = font.getType1Font();
        String programName = program == null ? "null" : program.getName();
        out.printf("FONT %s %s %s %s %s%n",
                font.getName(), font.getSubType(), embedded, hasFontFile, programName);

        Encoding enc = font.getEncoding();
        out.printf("ENC %s%n", enc == null ? "null" : enc.getClass().getSimpleName());

        for (int code = 0; code <= 255; code++) {
            String glyph = font.codeToName(code);
            float width = font.getWidth(code);
            out.printf("CODE %d %s %s%n", code, glyph, canonNumber(width));
        }

        if (program != null) {
            TreeSet<String> names = new TreeSet<String>(program.getCharStringsDict().keySet());
            for (String gn : names) {
                out.printf("HASGLYPH %s %s%n", gn, font.hasGlyph(gn));
            }
        }
    }

    /** Mirror the canonical number rendering used by other probes/tests. */
    private static String canonNumber(double value) {
        if (value == Math.rint(value) && !Double.isInfinite(value)) {
            return Long.toString((long) value);
        }
        return Double.toString(value);
    }
}
