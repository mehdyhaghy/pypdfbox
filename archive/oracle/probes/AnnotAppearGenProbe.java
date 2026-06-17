import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationCircle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationHighlight;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationInk;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLine;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolygon;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolyline;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquare;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary;

/**
 * Live oracle probe for NON-WIDGET annotation appearance GENERATION.
 *
 * Two modes:
 *
 *   java ... AnnotAppearGenProbe write out.pdf
 *       Build a page with a battery of markup annotations (Line, Square,
 *       Circle, Polygon, PolyLine, Ink, Highlight) — each given a rect,
 *       stroke color, interior color / border width / line endings where
 *       relevant — then call annotation.constructAppearances(doc) on each
 *       and save to out.pdf.
 *
 *   java ... AnnotAppearGenProbe read out.pdf
 *       Re-open the saved file and emit, per annotation (in page /Annots
 *       order), a coordinate-independent fingerprint of its /AP /N
 *       appearance stream:
 *
 *         ANNOT <subtype>
 *         BBOX <x0>,<y0>,<x1>,<y1>          (rounded to nearest int)
 *         OP:<name>                          one line per operator token
 *         END
 *
 *   Operator-only fingerprint: the operands (numbers/names) are coordinate
 *   dependent and differ in float formatting between implementations, so we
 *   compare the operator KEYWORD sequence plus the integer-rounded BBox.
 *   This catches a missing / wrong / extra drawing operator and a wrong
 *   bbox while normalising coordinate precision (the task's contract).
 */
public final class AnnotAppearGenProbe {
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

            // --- Line: stroke red, leader lines, open/closed arrow endings ---
            PDAnnotationLine line = new PDAnnotationLine();
            line.setRectangle(new PDRectangle(50, 50, 200, 200));
            line.setLine(new float[] {60, 60, 240, 240});
            line.setColor(rgb(1, 0, 0));
            line.setInteriorColor(rgb(0, 1, 0));
            line.setStartPointEndingStyle(PDAnnotationLine.LE_OPEN_ARROW);
            line.setEndPointEndingStyle(PDAnnotationLine.LE_CLOSED_ARROW);
            line.constructAppearances(doc);
            page.getAnnotations().add(line);

            // --- Square: stroke blue, interior yellow, border width 3 ---
            PDAnnotationSquare square = new PDAnnotationSquare();
            square.setRectangle(new PDRectangle(50, 300, 150, 150));
            square.setColor(rgb(0, 0, 1));
            square.setInteriorColor(rgb(1, 1, 0));
            PDBorderStyleDictionary squareBs = new PDBorderStyleDictionary();
            squareBs.setWidth(3);
            square.setBorderStyle(squareBs);
            square.constructAppearances(doc);
            page.getAnnotations().add(square);

            // --- Circle: stroke green, no interior, border width 2 ---
            PDAnnotationCircle circle = new PDAnnotationCircle();
            circle.setRectangle(new PDRectangle(250, 300, 150, 150));
            circle.setColor(rgb(0, 0.5f, 0));
            PDBorderStyleDictionary circleBs = new PDBorderStyleDictionary();
            circleBs.setWidth(2);
            circle.setBorderStyle(circleBs);
            circle.constructAppearances(doc);
            page.getAnnotations().add(circle);

            // --- Polygon: stroke black, interior light-grey ---
            PDAnnotationPolygon polygon = new PDAnnotationPolygon();
            polygon.setRectangle(new PDRectangle(50, 500, 200, 200));
            polygon.setVertices(new float[] {60, 510, 240, 520, 150, 680});
            polygon.setColor(rgb(0, 0, 0));
            polygon.setInteriorColor(rgb(0.8f, 0.8f, 0.8f));
            polygon.constructAppearances(doc);
            page.getAnnotations().add(polygon);

            // --- PolyLine: stroke magenta, open-arrow endings ---
            PDAnnotationPolyline polyline = new PDAnnotationPolyline();
            polyline.setRectangle(new PDRectangle(300, 500, 200, 200));
            polyline.setVertices(new float[] {310, 510, 490, 560, 360, 680});
            polyline.setColor(rgb(1, 0, 1));
            polyline.setStartPointEndingStyle(PDAnnotationLine.LE_OPEN_ARROW);
            polyline.setEndPointEndingStyle(PDAnnotationLine.LE_DIAMOND);
            polyline.setInteriorColor(rgb(0, 1, 1));
            polyline.constructAppearances(doc);
            page.getAnnotations().add(polyline);

            // --- Ink: stroke dark-red, two strokes ---
            PDAnnotationInk ink = new PDAnnotationInk();
            ink.setRectangle(new PDRectangle(50, 720, 200, 100));
            ink.setInkList(new float[][] {
                {60, 730, 100, 800, 140, 740},
                {160, 730, 200, 810, 240, 740},
            });
            ink.setColor(rgb(0.5f, 0, 0));
            ink.constructAppearances(doc);
            page.getAnnotations().add(ink);

            // --- Highlight: fill orange, one quad ---
            PDAnnotationHighlight highlight = new PDAnnotationHighlight();
            highlight.setRectangle(new PDRectangle(300, 720, 200, 60));
            highlight.setQuadPoints(new float[] {
                300, 770, 500, 770, 300, 730, 500, 730,
            });
            highlight.setColor(rgb(1, 0.6f, 0));
            highlight.constructAppearances(doc);
            page.getAnnotations().add(highlight);

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
        PDAppearanceStream stream = normalStream(annot);
        if (stream == null) {
            sb.append("NOAP\n").append("END\n");
            return;
        }
        PDRectangle bbox = stream.getBBox();
        if (bbox == null) {
            sb.append("BBOX none\n");
        } else {
            // Canonical, locale-independent float rendering so Java and
            // Python agree exactly without relying on either language's
            // half-rounding rule (Java rounds half up, Python rounds half
            // to even — comparing rounded ints would be a false mismatch).
            sb.append("BBOX ")
              .append(canonFloat(bbox.getLowerLeftX())).append(',')
              .append(canonFloat(bbox.getLowerLeftY())).append(',')
              .append(canonFloat(bbox.getUpperRightX())).append(',')
              .append(canonFloat(bbox.getUpperRightY())).append('\n');
        }
        PDFStreamParser parser = new PDFStreamParser(stream);
        List<Object> tokens = parser.parse();
        for (Object tok : tokens) {
            if (tok instanceof Operator) {
                sb.append("OP:").append(((Operator) tok).getName()).append('\n');
            }
        }
        sb.append("END\n");
    }

    /**
     * Locale-independent canonical float rendering: round to 3 decimals,
     * strip trailing zeros / trailing dot, normalise -0.
     */
    static String canonFloat(float f) {
        java.math.BigDecimal bd = new java.math.BigDecimal(Float.toString(f))
                .setScale(3, java.math.RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if (s.equals("-0")) {
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
