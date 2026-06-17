import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationHighlight;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquiggly;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationStrikeout;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationTextMarkup;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationUnderline;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;

/**
 * Live oracle probe for TEXT-MARKUP annotations (Highlight / Underline /
 * StrikeOut / Squiggly): the /QuadPoints array, the /C colour, and the
 * generated /AP /N appearance-stream operator sequence + BBox.
 *
 * Two modes:
 *
 *   java ... TextMarkupProbe write out.pdf
 *       Build a page with one of each text-markup subtype (Highlight,
 *       Underline, StrikeOut, Squiggly), each given a /Rect, a single
 *       /QuadPoints quad over a text region, and a /C colour, then call
 *       annotation.constructAppearances(doc) on each and save. This is the
 *       PDFBox-AUTHORED reference: RenderProbe rasterises it and the read mode
 *       fingerprints its generated /AP /N streams.
 *
 *   java ... TextMarkupProbe read out.pdf
 *       Re-open ANY text-markup PDF (PDFBox- or pypdfbox-authored) and emit the
 *       per-annotation fingerprint below.
 *
 * read mode emits, per annotation in page /Annots order:
 *
 *   ANNOT <subtype>
 *   QP <canonical floats, space-separated>          (or "QP none")
 *   C <canonical floats, space-separated>            (or "C none")
 *   BBOX <x0>,<y0>,<x1>,<y1>                          (or "BBOX none" / "NOAP")
 *   OP:<name>                                         one line per operator
 *   END
 *
 * The operands of each operator are coordinate-dependent and differ in float
 * formatting between implementations, so only the operator KEYWORD sequence is
 * fingerprinted; coordinates are normalised away. /QuadPoints and /C ARE
 * compared as canonical floats (these are accessor-level values, not generated
 * geometry, so they must match exactly). The rendered shapes are compared
 * separately via RenderProbe (16x16 luminance grid).
 */
public final class TextMarkupProbe {
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
            PDPage page = new PDPage(new PDRectangle(0, 0, 300, 400));
            doc.addPage(page);

            // One quad per subtype over a 200x15-pt text band. QuadPoints
            // order is the spec order: (x1 y1)(x2 y2)(x3 y3)(x4 y4) =
            // upper-left, upper-right, lower-left, lower-right.
            PDAnnotationHighlight highlight = new PDAnnotationHighlight();
            highlight.setRectangle(new PDRectangle(50, 295, 200, 25));
            highlight.setQuadPoints(new float[] {50, 315, 250, 315, 50, 300, 250, 300});
            highlight.setColor(rgb(1, 1, 0));
            highlight.constructAppearances(doc);
            page.getAnnotations().add(highlight);

            PDAnnotationUnderline underline = new PDAnnotationUnderline();
            underline.setRectangle(new PDRectangle(50, 245, 200, 25));
            underline.setQuadPoints(new float[] {50, 265, 250, 265, 50, 250, 250, 250});
            underline.setColor(rgb(1, 0, 0));
            underline.constructAppearances(doc);
            page.getAnnotations().add(underline);

            PDAnnotationStrikeout strikeout = new PDAnnotationStrikeout();
            strikeout.setRectangle(new PDRectangle(50, 195, 200, 25));
            strikeout.setQuadPoints(new float[] {50, 215, 250, 215, 50, 200, 250, 200});
            strikeout.setColor(rgb(0, 0, 1));
            strikeout.constructAppearances(doc);
            page.getAnnotations().add(strikeout);

            PDAnnotationSquiggly squiggly = new PDAnnotationSquiggly();
            squiggly.setRectangle(new PDRectangle(50, 145, 200, 25));
            squiggly.setQuadPoints(new float[] {50, 165, 250, 165, 50, 150, 250, 150});
            squiggly.setColor(rgb(0, 0.5f, 0));
            squiggly.constructAppearances(doc);
            page.getAnnotations().add(squiggly);

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

        // /QuadPoints (text-markup specific accessor).
        if (annot instanceof PDAnnotationTextMarkup) {
            float[] qp = ((PDAnnotationTextMarkup) annot).getQuadPoints();
            sb.append("QP ").append(floats(qp)).append('\n');
        } else {
            sb.append("QP none\n");
        }

        // /C colour, read off the raw COS dictionary so the float components
        // are compared regardless of colour-space wrapping.
        sb.append("C ").append(colorComponents(annot)).append('\n');

        PDAppearanceStream stream = normalStream(annot);
        if (stream == null) {
            sb.append("NOAP\n").append("END\n");
            return;
        }
        PDRectangle bbox = stream.getBBox();
        if (bbox == null) {
            sb.append("BBOX none\n");
        } else {
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

    private static String colorComponents(PDAnnotation annot) {
        COSBase base = annot.getCOSObject().getDictionaryObject(
                org.apache.pdfbox.cos.COSName.C);
        if (!(base instanceof COSArray)) {
            return "none";
        }
        COSArray arr = (COSArray) base;
        if (arr.size() == 0) {
            return "none";
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < arr.size(); i++) {
            if (i > 0) {
                sb.append(' ');
            }
            COSBase c = arr.getObject(i);
            float v = (c instanceof COSNumber) ? ((COSNumber) c).floatValue() : 0f;
            sb.append(canonFloat(v));
        }
        return sb.toString();
    }

    private static String floats(float[] values) {
        if (values == null) {
            return "none";
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < values.length; i++) {
            if (i > 0) {
                sb.append(' ');
            }
            sb.append(canonFloat(values[i]));
        }
        return sb.toString();
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
