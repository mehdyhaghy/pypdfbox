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
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLine;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolygon;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolyline;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary;

/**
 * Live oracle probe for POLYGON / POLYLINE annotation appearance generation —
 * the OPERAND-LEVEL /AP /N content (not just operator keywords).
 *
 * Distinct from AnnotAppearGenProbe (which compares only operator NAMES + an
 * integer-rounded BBox): this probe drives
 * PDPolygonAppearanceHandler.generateNormalAppearance() and
 * PDPolylineAppearanceHandler.generateNormalAppearance() and emits the FULL
 * token stream — every operand number/name canonicalised to 3 decimals — so a
 * mis-placed vertex (m/l), a wrong /C stroke (RG), wrong /IC fill (rg), wrong
 * /BS width (w), or a wrong PolyLine /LE line-ending sub-path is caught.
 *
 * Two modes:
 *
 *   java ... PolyAppearanceProbe write out.pdf
 *       Build a page with:
 *         - a Polygon (3 vertices, stroke black, interior light-grey, width 3)
 *         - a PolyLine (3 vertices, stroke magenta, interior cyan,
 *           start OpenArrow / end Diamond endings, width 2)
 *       call constructAppearances(doc) on each, save.
 *
 *   java ... PolyAppearanceProbe read out.pdf
 *       Re-open and emit, per annotation (in /Annots order):
 *
 *         ANNOT <subtype>
 *         RECT <x0>,<y0>,<x1>,<y1>      annotation /Rect (canonical floats)
 *         BBOX <x0>,<y0>,<x1>,<y1>      form-XObject /BBox
 *         TOK <canonical token>          one per content-stream token
 *         END
 *
 *   A TOK line is either an operator keyword (e.g. "m", "RG", "w", "S", "B"),
 *   a canonical number ("60", "510", "0.8"), or a name ("/GS0").  This makes
 *   the comparison value-based and locale-independent.
 */
public final class PolyAppearanceProbe {
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

            // --- Polygon: stroke black, interior light-grey, border width 3 ---
            PDAnnotationPolygon polygon = new PDAnnotationPolygon();
            polygon.setRectangle(new PDRectangle(50, 500, 200, 200));
            polygon.setVertices(new float[] {60, 510, 240, 520, 150, 680});
            polygon.setColor(rgb(0, 0, 0));
            polygon.setInteriorColor(rgb(0.8f, 0.8f, 0.8f));
            PDBorderStyleDictionary polyBs = new PDBorderStyleDictionary();
            polyBs.setWidth(3);
            polygon.setBorderStyle(polyBs);
            polygon.constructAppearances(doc);
            page.getAnnotations().add(polygon);

            // --- PolyLine: stroke magenta, interior cyan, open-arrow / diamond ---
            PDAnnotationPolyline polyline = new PDAnnotationPolyline();
            polyline.setRectangle(new PDRectangle(300, 500, 200, 200));
            polyline.setVertices(new float[] {310, 510, 490, 560, 360, 680});
            polyline.setColor(rgb(1, 0, 1));
            polyline.setInteriorColor(rgb(0, 1, 1));
            polyline.setStartPointEndingStyle(PDAnnotationLine.LE_OPEN_ARROW);
            polyline.setEndPointEndingStyle(PDAnnotationLine.LE_DIAMOND);
            PDBorderStyleDictionary plBs = new PDBorderStyleDictionary();
            plBs.setWidth(2);
            polyline.setBorderStyle(plBs);
            polyline.constructAppearances(doc);
            page.getAnnotations().add(polyline);

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
