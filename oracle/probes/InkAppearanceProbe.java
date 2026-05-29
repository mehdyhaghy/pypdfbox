import java.io.File;
import java.io.PrintStream;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationInk;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary;

/**
 * Live oracle probe for INK annotation appearance generation — the
 * OPERAND-LEVEL /AP /N content (not just operator keywords).
 *
 * Drives PDInkAppearanceHandler.generateNormalAppearance() (invoked via
 * PDAnnotationInk.constructAppearances(doc)) and emits the FULL token stream —
 * every operand number/name canonicalised to 3 decimals — so a mis-placed
 * stroke vertex (m/l), a wrong /C stroke colour (RG), a wrong /BS border width
 * (w), a missing per-path "S" (stroke), or a wrongly-rewritten /Rect or /BBox
 * is caught byte-for-byte.
 *
 * Two modes:
 *
 *   java ... InkAppearanceProbe write out.pdf
 *       Build a page with an Ink annotation whose /InkList holds TWO stroked
 *       paths (path 0 = 3 points, path 1 = 2 points), stroke colour orange,
 *       border width 4, and call constructAppearances(doc); save.
 *
 *   java ... InkAppearanceProbe read out.pdf
 *       Re-open and emit, per annotation (in /Annots order):
 *
 *         ANNOT <subtype>
 *         RECT <x0>,<y0>,<x1>,<y1>      annotation /Rect (canonical floats)
 *         BBOX <x0>,<y0>,<x1>,<y1>      form-XObject /BBox
 *         TOK <canonical token>          one per content-stream token
 *         END
 *
 *   A TOK line is either an operator keyword (e.g. "m", "RG", "w", "S"),
 *   a canonical number ("60", "510", "0.8"), or a name ("/GS0").  This makes
 *   the comparison value-based and locale-independent.
 */
public final class InkAppearanceProbe {
    public static void main(String[] args) throws Exception {
        String mode = args[0];
        File file = new File(args[1]);
        if ("write".equals(mode)) {
            write(file);
        } else {
            read(file);
        }
    }

    private static PDColor rgb(float r, float g, float b) {
        return new PDColor(new float[] {r, g, b}, PDDeviceRGB.INSTANCE);
    }

    private static void write(File file) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.A4);
            doc.addPage(page);

            // --- Ink: two stroked paths, stroke orange, border width 4 ---
            PDAnnotationInk ink = new PDAnnotationInk();
            ink.setRectangle(new PDRectangle(50, 500, 200, 200));
            ink.setInkList(new float[][] {
                {60, 510, 120, 640, 230, 560},
                {80, 520, 240, 690},
            });
            ink.setColor(rgb(1, 0.5f, 0));
            PDBorderStyleDictionary bs = new PDBorderStyleDictionary();
            bs.setWidth(4);
            ink.setBorderStyle(bs);
            ink.constructAppearances(doc);
            page.getAnnotations().add(ink);

            doc.save(file);
        }
    }

    private static void read(File file) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(file)) {
            for (PDPage page : doc.getPages()) {
                for (PDAnnotation annot : page.getAnnotations()) {
                    emit(sb, annot);
                }
            }
        }
        out.print(sb);
    }

    private static void emit(StringBuilder sb, PDAnnotation annot) throws Exception {
        String subtype = annot.getSubtype();
        sb.append("ANNOT ").append(subtype == null ? "?" : subtype).append('\n');
        sb.append("RECT ").append(rectStr(annot.getRectangle())).append('\n');

        PDAppearanceStream stream = normalStream(annot);
        if (stream == null) {
            sb.append("NOAP\nEND\n");
            return;
        }
        sb.append("BBOX ").append(rectStr(stream.getBBox())).append('\n');

        PDFStreamParser parser = new PDFStreamParser(stream);
        List<Object> tokens = parser.parse();
        for (Object tok : tokens) {
            sb.append("TOK ").append(canonToken(tok)).append('\n');
        }
        sb.append("END\n");
    }

    private static String canonToken(Object tok) {
        if (tok instanceof Operator) {
            return ((Operator) tok).getName();
        }
        if (tok instanceof COSNumber) {
            return canon(((COSNumber) tok).floatValue());
        }
        if (tok instanceof COSName) {
            return "/" + ((COSName) tok).getName();
        }
        if (tok instanceof COSBase) {
            return tok.getClass().getSimpleName();
        }
        return String.valueOf(tok);
    }

    private static String rectStr(PDRectangle r) {
        if (r == null) {
            return "none";
        }
        return canon(r.getLowerLeftX()) + ","
                + canon(r.getLowerLeftY()) + ","
                + canon(r.getUpperRightX()) + ","
                + canon(r.getUpperRightY());
    }

    // Round half-even to 3 decimals; strip trailing zeros / dot; normalise -0.
    private static String canon(double value) {
        BigDecimal bd = new BigDecimal(Double.toString(value))
                .setScale(3, RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if (s.equals("-0") || s.isEmpty()) {
            s = "0";
        }
        return s;
    }

    private static PDAppearanceStream normalStream(PDAnnotation annot) {
        PDAppearanceDictionary ap = annot.getAppearance();
        if (ap == null) {
            return null;
        }
        PDAppearanceEntry normal = ap.getNormalAppearance();
        if (normal == null || normal.isSubDictionary()) {
            return null;
        }
        return normal.getAppearanceStream();
    }
}
