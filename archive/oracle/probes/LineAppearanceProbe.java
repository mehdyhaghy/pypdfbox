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
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary;

/**
 * Live oracle probe for LINE annotation appearance generation — the
 * OPERAND-LEVEL /AP /N content (not just operator keywords).
 *
 * Drives PDLineAppearanceHandler.generateNormalAppearance() (invoked via
 * PDAnnotationLine.constructAppearances(doc)) and emits the FULL token stream —
 * every operand number/name canonicalised to 3 decimals — so the rotation CTM
 * (cm), leader-line m/l sub-paths, the line body, the start/end line-ending
 * shapes drawn by drawStyle() (OpenArrow/ClosedArrow/Diamond/Circle/Square/
 * Butt/Slash via q cm ... Q), the /C stroke (RG) + /IC interior fill (rg) and
 * the rewritten /Rect / /BBox are all caught byte-for-byte.
 *
 * Several Line variants are written (one per page); because all share subtype
 * "Line" the records are keyed by their /Annots ordinal index (LINE0, LINE1…):
 *
 *   0: plain line, no endings, no leader lines, stroke orange, width 3
 *   1: OpenArrow start / ClosedArrow end (angled + short, interior fill), w 2
 *   2: Diamond start / Circle end (non-angled, interior fill), w 4
 *   3: leader lines (LL/LLE/LLO) + Square start / Butt end, w 2
 *   4: caption (/Cap true + /Contents) Inline, Square start / Square end, w 2
 *   5: caption Top positioning + /CO offsets, OpenArrow / OpenArrow, w 2
 *   6: Slash start / RClosedArrow end (angled), interior fill, w 3
 *
 * Modes:
 *
 *   java ... LineAppearanceProbe write out.pdf
 *   java ... LineAppearanceProbe read out.pdf
 *       Re-open and emit, per annotation (in /Annots order):
 *         ANNOT LINE<idx>
 *         RECT <x0>,<y0>,<x1>,<y1>      annotation /Rect (canonical floats)
 *         BBOX <x0>,<y0>,<x1>,<y1>      form-XObject /BBox
 *         TOK <canonical token>          one per content-stream token
 *         END
 *
 *   A TOK line is either an operator keyword (e.g. "m", "RG", "cm", "S"),
 *   a canonical number, or a name ("/GS0").  Comparison is value-based and
 *   locale-independent.
 */
public final class LineAppearanceProbe {
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

    private static PDBorderStyleDictionary border(float width) {
        PDBorderStyleDictionary bs = new PDBorderStyleDictionary();
        bs.setWidth(width);
        return bs;
    }

    private static void write(File file) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            // 0: plain line, no endings, stroke orange, width 3
            PDPage p0 = new PDPage(PDRectangle.A4);
            doc.addPage(p0);
            PDAnnotationLine a0 = new PDAnnotationLine();
            a0.setRectangle(new PDRectangle(50, 500, 200, 120));
            a0.setLine(new float[] {60, 520, 240, 600});
            a0.setColor(rgb(1, 0.5f, 0));
            a0.setBorderStyle(border(3));
            a0.constructAppearances(doc);
            p0.getAnnotations().add(a0);

            // 1: OpenArrow / ClosedArrow (angled + short), interior fill, w 2
            PDPage p1 = new PDPage(PDRectangle.A4);
            doc.addPage(p1);
            PDAnnotationLine a1 = new PDAnnotationLine();
            a1.setRectangle(new PDRectangle(50, 350, 200, 120));
            a1.setLine(new float[] {60, 360, 240, 440});
            a1.setColor(rgb(0, 0, 1));
            a1.setInteriorColor(rgb(1, 1, 0));
            a1.setStartPointEndingStyle(PDAnnotationLine.LE_OPEN_ARROW);
            a1.setEndPointEndingStyle(PDAnnotationLine.LE_CLOSED_ARROW);
            a1.setBorderStyle(border(2));
            a1.constructAppearances(doc);
            p1.getAnnotations().add(a1);

            // 2: Diamond / Circle (non-angled, short, interior fill), w 4
            PDPage p2 = new PDPage(PDRectangle.A4);
            doc.addPage(p2);
            PDAnnotationLine a2 = new PDAnnotationLine();
            a2.setRectangle(new PDRectangle(50, 200, 200, 120));
            a2.setLine(new float[] {60, 210, 240, 290});
            a2.setColor(rgb(1, 0, 1));
            a2.setInteriorColor(rgb(0, 1, 1));
            a2.setStartPointEndingStyle(PDAnnotationLine.LE_DIAMOND);
            a2.setEndPointEndingStyle(PDAnnotationLine.LE_CIRCLE);
            a2.setBorderStyle(border(4));
            a2.constructAppearances(doc);
            p2.getAnnotations().add(a2);

            // 3: leader lines (LL/LLE/LLO) + Square start / Butt end, w 2
            PDPage p3 = new PDPage(PDRectangle.A4);
            doc.addPage(p3);
            PDAnnotationLine a3 = new PDAnnotationLine();
            a3.setRectangle(new PDRectangle(50, 500, 200, 120));
            a3.setLine(new float[] {60, 520, 240, 600});
            a3.setColor(rgb(0, 0.5f, 0));
            a3.setLeaderLineLength(20);
            a3.setLeaderLineExtensionLength(8);
            a3.setLeaderLineOffsetLength(5);
            a3.setStartPointEndingStyle(PDAnnotationLine.LE_SQUARE);
            a3.setEndPointEndingStyle(PDAnnotationLine.LE_BUTT);
            a3.setInteriorColor(rgb(0.8f, 0.8f, 0.8f));
            a3.setBorderStyle(border(2));
            a3.constructAppearances(doc);
            p3.getAnnotations().add(a3);

            // 4: caption Inline + /Contents, Square / Square, w 2
            PDPage p4 = new PDPage(PDRectangle.A4);
            doc.addPage(p4);
            PDAnnotationLine a4 = new PDAnnotationLine();
            a4.setRectangle(new PDRectangle(50, 350, 200, 120));
            a4.setLine(new float[] {60, 360, 300, 360});
            a4.setColor(rgb(0, 0, 0));
            a4.setInteriorColor(rgb(0.5f, 0.5f, 0.5f));
            a4.setStartPointEndingStyle(PDAnnotationLine.LE_SQUARE);
            a4.setEndPointEndingStyle(PDAnnotationLine.LE_SQUARE);
            a4.setCaption(true);
            a4.setContents("Hello");
            a4.setBorderStyle(border(2));
            a4.constructAppearances(doc);
            p4.getAnnotations().add(a4);

            // 5: caption Top + /CO offsets, OpenArrow / OpenArrow, w 2
            PDPage p5 = new PDPage(PDRectangle.A4);
            doc.addPage(p5);
            PDAnnotationLine a5 = new PDAnnotationLine();
            a5.setRectangle(new PDRectangle(50, 200, 200, 120));
            a5.setLine(new float[] {60, 210, 300, 210});
            a5.setColor(rgb(0, 0, 0));
            a5.setStartPointEndingStyle(PDAnnotationLine.LE_OPEN_ARROW);
            a5.setEndPointEndingStyle(PDAnnotationLine.LE_OPEN_ARROW);
            a5.setCaption(true);
            a5.setCaptionPositioning("Top");
            a5.setContents("Length");
            a5.setCaptionHorizontalOffset(3);
            a5.setCaptionVerticalOffset(7);
            a5.setBorderStyle(border(2));
            a5.constructAppearances(doc);
            p5.getAnnotations().add(a5);

            // 6: Slash / RClosedArrow (angled), interior fill, w 3
            PDPage p6 = new PDPage(PDRectangle.A4);
            doc.addPage(p6);
            PDAnnotationLine a6 = new PDAnnotationLine();
            a6.setRectangle(new PDRectangle(50, 60, 200, 120));
            a6.setLine(new float[] {60, 70, 240, 150});
            a6.setColor(rgb(0.2f, 0.4f, 0.6f));
            a6.setInteriorColor(rgb(1, 0, 0));
            a6.setStartPointEndingStyle(PDAnnotationLine.LE_SLASH);
            a6.setEndPointEndingStyle(PDAnnotationLine.LE_R_CLOSED_ARROW);
            a6.setBorderStyle(border(3));
            a6.constructAppearances(doc);
            p6.getAnnotations().add(a6);

            doc.save(file);
        }
    }

    private static void read(File file) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(file)) {
            int idx = 0;
            for (PDPage page : doc.getPages()) {
                for (PDAnnotation annot : page.getAnnotations()) {
                    emit(sb, annot, idx++);
                }
            }
        }
        out.print(sb);
    }

    private static void emit(StringBuilder sb, PDAnnotation annot, int idx) throws Exception {
        sb.append("ANNOT LINE").append(idx).append('\n');
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
