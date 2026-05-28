import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType3CharProc;
import org.apache.pdfbox.pdmodel.font.PDType3Font;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for the Type 3 glyph char-proc metric operators (d0/d1).
 *
 * For every Type 3 font reachable from page 0's resources, this probe walks
 * each glyph procedure (a /CharProcs content stream) and emits the operand
 * effects of the leading ``d0 wx wy`` / ``d1 wx wy llx lly urx ury`` operator
 * exactly as Apache PDFBox 3.0.7 decodes them:
 *
 *   - PDType3CharProc.getWidth()    — the ``wx`` glyph-space advance op
 *   - PDType3CharProc.getGlyphBBox() — the ``d1`` bbox (null for ``d0``)
 *   - PDType3CharProc.getMatrix()    — the font's /FontMatrix applied to the
 *                                      char-proc (char procs have no matrix of
 *                                      their own)
 *
 * Output (UTF-8, to stdout), one line per emitted datum, tab-separated, so a
 * single divergence surfaces as one differing line:
 *
 *   PROCWIDTH <glyph-name> <%.6f wx>
 *   GLYPHBBOX <glyph-name> NONE                     (leading d0 — no bbox)
 *   GLYPHBBOX <glyph-name> <%.6f llx> <lly> <urx> <ury>   (leading d1)
 *   PROCMATRIX <glyph-name> <6 x %.6f>
 *
 * Glyphs are emitted in the sorted /CharProcs name order so both sides agree
 * on line order regardless of dictionary hashing.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Type3CharProcProbe input.pdf
 */
public final class Type3CharProcProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(0);
            PDResources res = page.getResources();
            if (res == null) {
                return;
            }
            for (COSName fontName : res.getFontNames()) {
                PDFont font = res.getFont(fontName);
                if (!(font instanceof PDType3Font)) {
                    continue;
                }
                PDType3Font t3 = (PDType3Font) font;
                java.util.List<String> names = new java.util.ArrayList<>();
                if (t3.getCharProcs() != null) {
                    for (COSName k : t3.getCharProcs().keySet()) {
                        names.add(k.getName());
                    }
                }
                java.util.Collections.sort(names);
                for (String gname : names) {
                    org.apache.pdfbox.cos.COSBase entry =
                            t3.getCharProcs().getDictionaryObject(COSName.getPDFName(gname));
                    if (!(entry instanceof org.apache.pdfbox.cos.COSStream)) {
                        continue;
                    }
                    PDType3CharProc proc = new PDType3CharProc(
                            t3, (org.apache.pdfbox.cos.COSStream) entry);
                    out.println("PROCWIDTH\t" + gname + "\t" + fmt(proc.getWidth()));

                    PDRectangle bbox = proc.getGlyphBBox();
                    if (bbox == null) {
                        out.println("GLYPHBBOX\t" + gname + "\tNONE");
                    } else {
                        out.println("GLYPHBBOX\t" + gname + "\t"
                                + fmt(bbox.getLowerLeftX()) + "\t"
                                + fmt(bbox.getLowerLeftY()) + "\t"
                                + fmt(bbox.getUpperRightX()) + "\t"
                                + fmt(bbox.getUpperRightY()));
                    }

                    Matrix m = proc.getMatrix();
                    out.println("PROCMATRIX\t" + gname + "\t"
                            + fmt(m.getScaleX()) + "\t" + fmt(m.getShearY()) + "\t"
                            + fmt(m.getShearX()) + "\t" + fmt(m.getScaleY()) + "\t"
                            + fmt(m.getTranslateX()) + "\t" + fmt(m.getTranslateY()));
                }
            }
        }
    }

    private static String fmt(double v) {
        return String.format(Locale.US, "%.6f", v);
    }
}
