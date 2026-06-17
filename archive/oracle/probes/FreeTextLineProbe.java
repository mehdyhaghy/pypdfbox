import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFreeText;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLine;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;

/**
 * Live oracle probe for the FreeText (callout) + Line (caption) annotation
 * specifics: /DA, /Q, /CL callout, /LE line endings, /IT intent, /L line
 * coords, /LL leader length, /Cap caption, /CP caption position. Plus the
 * generated /AP /N appearance op-sequence + BBox per type.
 *
 * Two modes (mirrors AnnotAppear2Probe):
 *
 *   java ... FreeTextLineProbe write out.pdf
 *       Build a page with (a) a FreeText callout annotation
 *       (/DA, /Q 1, /CL, /LE /OpenArrow, /IT /FreeTextCallout) and (b) a
 *       Line annotation (/L, /LE [/Diamond /ClosedArrow], /LL 10,
 *       /Cap true, /CP /Top), call constructAppearances(doc) on each, save.
 *
 *   java ... FreeTextLineProbe read out.pdf
 *       Re-open and emit, per annotation in /Annots order, accessor lines
 *       then the /AP /N appearance fingerprint:
 *         ANNOT <subtype>
 *         <accessor lines: KEY value>
 *         BBOX <x0>,<y0>,<x1>,<y1>     (canonical floats; or "none"/NOAP)
 *         OP:<name>                     one line per operator token
 *         END
 *
 *   Operator-only fingerprint: operands are coordinate-/float-format
 *   dependent so we compare the operator KEYWORD sequence + canonical /BBox.
 */
public final class FreeTextLineProbe {
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

            // --- FreeText callout ---
            PDAnnotationFreeText freeText = new PDAnnotationFreeText();
            freeText.setRectangle(new PDRectangle(200, 600, 200, 100));
            freeText.setContents("callout text");
            freeText.setColor(rgb(1, 1, 0));
            freeText.setDefaultAppearance("/Helv 12 Tf 0 0 1 rg");
            freeText.setQ(1); // 1 = centered (PDVariableText.QUADDING_CENTERED)
            freeText.setIntent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT);
            // 3-point knee callout: knee at (150,560), elbow (180,610),
            // text-box corner (200,650).
            freeText.setCallout(new float[] {150, 560, 180, 610, 200, 650});
            freeText.setLineEndingStyle(PDAnnotationLine.LE_OPEN_ARROW);
            freeText.setDefaultStyleString("font: Helvetica 12pt; color: #0000FF");
            freeText.constructAppearances(doc);
            page.getAnnotations().add(freeText);

            // --- Line with diamond start, closed-arrow end, caption ---
            PDAnnotationLine line = new PDAnnotationLine();
            line.setRectangle(new PDRectangle(50, 200, 300, 200));
            line.setLine(new float[] {60, 250, 340, 350});
            line.setStartPointEndingStyle(PDAnnotationLine.LE_DIAMOND);
            line.setEndPointEndingStyle(PDAnnotationLine.LE_CLOSED_ARROW);
            line.setLeaderLineLength(10);
            line.setCaption(true);
            line.setCaptionPositioning("Top");
            line.setContents("measured");
            line.setColor(rgb(1, 0, 0));
            line.setInteriorColor(rgb(0, 1, 0));
            line.constructAppearances(doc);
            page.getAnnotations().add(line);

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
        if (annot instanceof PDAnnotationFreeText) {
            emitFreeText(sb, (PDAnnotationFreeText) annot);
        } else if (annot instanceof PDAnnotationLine) {
            emitLine(sb, (PDAnnotationLine) annot);
        }
        emitAppearance(sb, annot);
        sb.append("END\n");
    }

    private static void emitFreeText(StringBuilder sb, PDAnnotationFreeText ft) {
        sb.append("DA ").append(str(ft.getDefaultAppearance())).append('\n');
        sb.append("Q ").append(ft.getQ()).append('\n');
        sb.append("IT ").append(str(ft.getIntent())).append('\n');
        sb.append("LE ").append(str(ft.getLineEndingStyle())).append('\n');
        sb.append("DS ").append(str(ft.getDefaultStyleString())).append('\n');
        float[] cl = ft.getCallout();
        sb.append("CL ").append(floats(cl)).append('\n');
    }

    private static void emitLine(StringBuilder sb, PDAnnotationLine ln) {
        sb.append("L ").append(floats(ln.getLine())).append('\n');
        sb.append("LE_START ").append(str(ln.getStartPointEndingStyle())).append('\n');
        sb.append("LE_END ").append(str(ln.getEndPointEndingStyle())).append('\n');
        sb.append("LL ").append(canonFloat(ln.getLeaderLineLength())).append('\n');
        sb.append("CAP ").append(ln.hasCaption()).append('\n');
        sb.append("CP ").append(str(ln.getCaptionPositioning())).append('\n');
    }

    private static void emitAppearance(StringBuilder sb, PDAnnotation annot) throws Exception {
        PDAppearanceStream stream = normalStream(annot);
        if (stream == null) {
            sb.append("NOAP\n");
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
    }

    private static String str(String s) {
        return s == null ? "null" : s;
    }

    private static String floats(float[] arr) {
        if (arr == null || arr.length == 0) {
            return "null";
        }
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < arr.length; i++) {
            if (i > 0) {
                b.append(',');
            }
            b.append(canonFloat(arr[i]));
        }
        return b.toString();
    }

    /**
     * Locale-independent canonical float rendering: round half-to-even to 3
     * decimals, strip trailing zeros / trailing dot, normalise -0.
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

    // Keep COSArray / COSBase / COSName imported for future probe edits.
    @SuppressWarnings("unused")
    private static final Class<?>[] KEEP = {COSArray.class, COSBase.class, COSName.class};
}
