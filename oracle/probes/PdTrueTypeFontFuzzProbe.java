import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDTrueTypeFont;
import org.apache.pdfbox.pdmodel.font.encoding.Encoding;

/**
 * Live oracle probe for {@link PDTrueTypeFont} encoding-selection +
 * code-&gt;glyph mapping + width handling on malformed / edge-case simple
 * TrueType font dictionaries (PDF 32000-1 §9.6.6.4, §9.7.4.3).
 *
 * Distinct from the adjacent font oracles:
 *   - SymbolicTtfProbe drives only the SYMBOLIC code-&gt;GID fallback chain
 *     (no /Encoding) + render fingerprint.
 *   - SimpleFontWidthsProbe drives the dictionary /Widths array on a Type1.
 *   - FontEncodingProbe drives the standalone Encoding classes.
 * This probe ties the three PDTrueTypeFont facets together over a matrix of
 * malformed dicts: the resolved {@link PDSimpleFont#getEncoding()} CLASS (the
 * symbolic-vs-non-symbolic + /Encoding-absent / name / dict-with-/Differences
 * selection), the {@link PDTrueTypeFont#codeToGID(int)} result, and the
 * {@link PDFont#getWidth(int)} / {@link PDFont#getWidthFromFont(int)} pair —
 * across: symbolic flag set vs clear, /Encoding absent / WinAnsi name /
 * MacRoman name / dict-with-/Differences, a non-symbolic font carrying only a
 * (3,0) cmap, /Widths present / absent / mismatched with /FirstChar//LastChar,
 * a missing /FontDescriptor, and a missing embedded /FontFile2.
 *
 * The PDFs are synthesised on the Python side (fontTools) and passed by path;
 * the probe reflects PDFBox's behaviour on each, emitting (UTF-8, tab-delimited,
 * deterministic order, one font per page in resource-name order):
 *
 *   FONT \t pageIndex \t fontKey \t baseFont \t isSymbolic \t encodingClass \t embedded \t damaged
 *   CODE \t pageIndex \t fontKey \t code \t getWidth \t getWidthFromFont \t codeToGID \t glyphName
 *
 * encodingClass is getEncoding().getClass().getSimpleName() (or "null").
 * Widths "%.4f" (Locale.ROOT, -0.0 collapsed). Any divergence is a single line.
 */
public final class PdTrueTypeFontFuzzProbe {

    // Codes spanning: low/control, the A..D mapped glyph window, a code past
    // the mapped window, the symbolic 0xF000 PUA-base region, and 0xFF.
    private static final int[] CODES = {
        0x00, 0x01, 0x20, 0x41, 0x42, 0x43, 0x44, 0x45, 0x60, 0x80, 0xA0, 0xFF
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        // args: one or more PDF paths; every page of every doc is walked.
        for (String path : args) {
            try (PDDocument doc = Loader.loadPDF(new File(path))) {
                int pageIndex = 0;
                for (PDPage page : doc.getPages()) {
                    PDResources res = page.getResources();
                    if (res != null) {
                        for (org.apache.pdfbox.cos.COSName name : res.getFontNames()) {
                            PDFont font;
                            try {
                                font = res.getFont(name);
                            } catch (Exception e) {
                                continue;
                            }
                            if (!(font instanceof PDTrueTypeFont)) {
                                continue;
                            }
                            emit(out, pageIndex, name.getName(), (PDTrueTypeFont) font);
                        }
                    }
                    pageIndex++;
                }
            }
        }
    }

    private static void emit(PrintStream out, int pageIndex, String key, PDTrueTypeFont font)
            throws Exception {
        boolean symbolic;
        try {
            symbolic = font.isSymbolic();
        } catch (Exception e) {
            symbolic = false;
        }
        String encClass;
        try {
            Encoding enc = font.getEncoding();
            encClass = enc != null ? enc.getClass().getSimpleName() : "null";
        } catch (Exception e) {
            encClass = "ENC_ERR";
        }
        boolean embedded;
        try {
            embedded = font.isEmbedded();
        } catch (Exception e) {
            embedded = false;
        }
        boolean damaged;
        try {
            damaged = font.isDamaged();
        } catch (Exception e) {
            damaged = false;
        }
        out.printf(
                "FONT\t%d\t%s\t%s\t%s\t%s\t%s\t%s%n",
                pageIndex, key, String.valueOf(font.getName()),
                symbolic ? "true" : "false", encClass,
                embedded ? "true" : "false", damaged ? "true" : "false");
        for (int code : CODES) {
            String width;
            try {
                width = fmt(font.getWidth(code));
            } catch (Exception e) {
                width = "WIDTH_ERR";
            }
            String widthFromFont;
            try {
                widthFromFont = fmt(font.getWidthFromFont(code));
            } catch (Exception e) {
                widthFromFont = "WFF_ERR";
            }
            String gid;
            try {
                gid = Integer.toString(font.codeToGID(code));
            } catch (Exception e) {
                gid = "GID_ERR";
            }
            String glyphName;
            try {
                Encoding enc = font.getEncoding();
                String n = enc != null ? enc.getName(code) : null;
                glyphName = n != null ? n : "null";
            } catch (Exception e) {
                glyphName = "NAME_ERR";
            }
            out.printf(
                    "CODE\t%d\t%s\t%d\t%s\t%s\t%s\t%s%n",
                    pageIndex, key, code, width, widthFromFont, gid, glyphName);
        }
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f; // collapse -0.0 to 0.0
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
