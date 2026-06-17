import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDTrueTypeFont;

/**
 * Live oracle probe for the **non-symbolic embedded simple TrueType** glyph
 * mapping surface of {@link PDTrueTypeFont} (PDF 32000-1 §9.6.6.4).
 *
 * <p>For a non-symbolic embedded simple TrueType font the {@code codeToGID}
 * chain is: {@code /Encoding} (with /Differences) maps the byte code to a
 * PostScript glyph name; that name is mapped to a Unicode via the Adobe Glyph
 * List and looked up in the (3,1) Win-Unicode cmap; failing that the name is
 * mapped to a Mac-Roman code and looked up in the (1,0) Mac-Roman cmap;
 * failing that the name is looked up directly in the font's {@code post}
 * table ({@code nameToGID}). This probe drives Apache PDFBox to emit, for
 * every simple {@link PDTrueTypeFont} on every page, per byte code 0..255:
 *
 * <pre>
 *   FONT \t pageIndex \t fontKey \t baseFont \t isSymbolic \t isEmbedded
 *   ROW  \t code \t codeToGID(code) \t getWidth(code) \t hasGlyph(code)
 * </pre>
 *
 * <p>Widths are normalized to 4 decimal places. The pypdfbox side reconstructs
 * the same lines from {@code PDTrueTypeFont.code_to_gid}, {@code get_width}, and
 * {@code has_glyph} and asserts line-for-line equality.
 */
public final class SimpleTtfMapProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res != null) {
                    emitPage(out, res, pageIndex);
                }
                pageIndex++;
            }
        }
    }

    private static void emitPage(PrintStream out, PDResources res, int pageIndex)
            throws Exception {
        for (COSName name : res.getFontNames()) {
            PDFont font;
            try {
                font = res.getFont(name);
            } catch (Exception e) {
                continue;
            }
            if (!(font instanceof PDTrueTypeFont)) {
                continue;
            }
            // Restrict to *embedded* simple TrueType fonts: a non-embedded
            // TrueType resolves codeToGID through a *substitute* font program
            // whose glyph order is environment-dependent (which system font the
            // mapper picked), so it is not a deterministic differential target.
            if (!font.isEmbedded()) {
                continue;
            }
            PDTrueTypeFont ttFont = (PDTrueTypeFont) font;
            boolean symbolic = false;
            if (font.getFontDescriptor() != null) {
                symbolic = font.getFontDescriptor().isSymbolic();
            }
            out.printf("FONT\t%d\t%s\t%s\t%b\t%b%n",
                    pageIndex, name.getName(), String.valueOf(font.getName()),
                    symbolic, font.isEmbedded());
            for (int code = 0; code < 256; code++) {
                int gid;
                try {
                    gid = ttFont.codeToGID(code);
                } catch (Exception e) {
                    gid = -1;
                }
                String width;
                try {
                    width = fmt(font.getWidth(code));
                } catch (Exception e) {
                    width = "ERR";
                }
                boolean has;
                try {
                    has = ttFont.hasGlyph(code);
                } catch (Exception e) {
                    has = false;
                }
                out.printf("ROW\t%d\t%d\t%s\t%b%n", code, gid, width, has);
            }
        }
    }

    private static String fmt(float v) {
        return String.format("%.4f", v);
    }
}
