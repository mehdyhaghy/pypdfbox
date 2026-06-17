import java.io.File;
import java.io.PrintStream;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;

/**
 * Live oracle probe for the PDF subset-tag invariant on /BaseFont (and the
 * descriptor's /FontName) of pypdfbox-produced subset TrueType embeddings.
 *
 * Per PDF 32000-1 §9.6.4 a font whose embedded program is a subset is named
 * "{6 uppercase ASCII letters}+{PostScript name}", and PDF 32000-1 §9.8.2
 * requires the font dict's /BaseFont and the descriptor's /FontName to match
 * including the prefix. Apache PDFBox 3.0.7 builds subset embeddings whose
 * tag is deterministic over the surviving glyph set
 * (TrueTypeEmbedder.getTag(gidToCid)). This probe is the oracle that
 * pypdfbox's saved subset PDFs honour the same invariants:
 *
 * <pre>
 *   java -cp <pdfbox-app.jar>:<build> TtfSubsetTagProbe input.pdf
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order):
 *   FONT  \t pageIndex \t resourceName \t baseFont \t subType \t isEmbedded
 *   TAG   \t pageIndex \t resourceName \t prefix \t shapeOk \t fontNameMatch
 *      prefix:     the 6 characters preceding '+', or NONE.
 *      shapeOk:    "true" when baseFont matches ^[A-Z]{6}\+.+ exactly.
 *      fontNameMatch: "true" when /FontDescriptor /FontName == /BaseFont
 *                     (PDF 32000-1 §9.8.2). "NA" when no descriptor.
 *   LOAD  \t pageIndex \t resourceName \t loadOk
 *      "true" when PDFBox's PDFont reified without throwing — exercises
 *      PDFBox's tolerance for the tag pypdfbox wrote.
 *
 * Never mutates the document; closes via try-with-resources.
 */
public final class TtfSubsetTagProbe {
    private static final Pattern PREFIX_RE = Pattern.compile("^([A-Z]{6})\\+(.+)$");

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res != null) {
                    for (COSName name : res.getFontNames()) {
                        emitFont(out, pageIndex, name, res);
                    }
                }
                pageIndex++;
            }
        }
    }

    private static void emitFont(PrintStream out, int pageIndex, COSName name,
            PDResources res) {
        String key = name.getName();
        PDFont font;
        try {
            font = res.getFont(name);
        } catch (Exception e) {
            out.printf("LOAD\t%d\t%s\tfalse%n", pageIndex, key);
            return;
        }
        if (font == null) {
            out.printf("LOAD\t%d\t%s\tnull%n", pageIndex, key);
            return;
        }

        String baseFont = String.valueOf(font.getName());
        boolean embedded;
        try {
            embedded = font.isEmbedded();
        } catch (Exception e) {
            embedded = false;
        }
        out.printf("FONT\t%d\t%s\t%s\t%s\t%b%n",
                pageIndex, key, baseFont, font.getSubType(), embedded);

        Matcher m = PREFIX_RE.matcher(baseFont);
        String prefix;
        boolean shapeOk;
        if (m.matches()) {
            prefix = m.group(1);
            shapeOk = true;
        } else {
            prefix = "NONE";
            shapeOk = false;
        }

        String fontNameMatch;
        PDFontDescriptor fd = font.getFontDescriptor();
        if (fd == null) {
            fontNameMatch = "NA";
        } else {
            String fn = fd.getFontName();
            fontNameMatch = String.valueOf(baseFont.equals(fn));
        }

        out.printf("TAG\t%d\t%s\t%s\t%b\t%s%n",
                pageIndex, key, prefix, shapeOk, fontNameMatch);
        out.printf("LOAD\t%d\t%s\ttrue%n", pageIndex, key);
    }
}
