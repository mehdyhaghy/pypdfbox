import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDCIDFont;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;
import org.apache.pdfbox.util.Vector;

/**
 * Live oracle probe: emit Apache PDFBox's vertical-writing-mode metrics for
 * every Type0 font on every page of a PDF.
 *
 * For each Type0 font we emit:
 *   FONT  <page> <key> <baseFont> <isVertical>
 * and, for a fixed set of input codes:
 *   CODE  <page> <key> <code> <cid> <posVecX> <posVecY> <dispX> <dispY> <vY>
 * where
 *   posVec  = PDType0Font.getPositionVector(code)          (em, scaled -1/1000)
 *   disp    = PDType0Font.getDisplacement(code)            (em)
 *   vY      = PDCIDFont.getVerticalDisplacementVectorY(code) (1/1000 em)
 *
 * Floats are normalised to 6 decimals so the Python side can match exactly.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> VerticalFontProbe input.pdf
 */
public final class VerticalFontProbe {

    // Codes probed for every font. Mix of low CIDs (covered by /W2),
    // CID 0 (.notdef), and high CIDs that fall back to /DW2 defaults.
    private static final int[] CODES = {0, 1, 2, 3, 5, 10, 100, 60000, 65535};

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res != null) {
                    for (COSName name : res.getFontNames()) {
                        PDFont font;
                        try {
                            font = res.getFont(name);
                        } catch (Exception e) {
                            continue;
                        }
                        if (!(font instanceof PDType0Font)) {
                            continue;
                        }
                        PDType0Font t0 = (PDType0Font) font;
                        PDCIDFont cid = t0.getDescendantFont();
                        out.println(
                            "FONT\t" + pageIndex + "\t" + name.getName() + "\t"
                            + t0.getName() + "\t" + (t0.isVertical() ? "true" : "false"));
                        for (int code : CODES) {
                            int cidValue = t0.codeToCID(code);
                            Vector pos = t0.getPositionVector(code);
                            Vector disp = t0.getDisplacement(code);
                            float vY = cid != null
                                ? cid.getVerticalDisplacementVectorY(code) : 0f;
                            out.println(
                                "CODE\t" + pageIndex + "\t" + name.getName() + "\t"
                                + code + "\t" + cidValue + "\t"
                                + f(pos.getX()) + "\t" + f(pos.getY()) + "\t"
                                + f(disp.getX()) + "\t" + f(disp.getY()) + "\t"
                                + f(vY));
                        }
                    }
                }
                pageIndex++;
            }
        }
    }

    private static String f(float v) {
        // Normalise -0.0 to 0.0 and fix to 6 decimals (locale-independent).
        if (v == 0.0f) {
            v = 0.0f;
        }
        return String.format(Locale.ROOT, "%.6f", v);
    }
}
