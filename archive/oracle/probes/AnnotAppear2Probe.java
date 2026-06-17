import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationCaret;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFileAttachment;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFreeText;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPopup;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationRubberStamp;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquiggly;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationStrikeout;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationText;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationUnderline;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;

/**
 * Live oracle probe for the REMAINING non-widget annotation appearance
 * GENERATION handlers — the markup types NOT covered by wave 1414's
 * AnnotAppearGenProbe (which did Line/Square/Circle/Polygon/PolyLine/Ink/
 * Highlight).
 *
 * Types covered here:
 *   Text (note icon "Note"), Caret, FileAttachment ("PushPin" icon),
 *   StrikeOut, Underline, Squiggly, FreeText, Popup, RubberStamp (Stamp).
 *
 * Two modes (mirrors AnnotAppearGenProbe exactly):
 *
 *   java ... AnnotAppear2Probe write out.pdf
 *       Build a page with one of each type — rect, colour, contents,
 *       quadpoints for the text-markup trio, icon /Name for Text +
 *       FileAttachment — then call annotation.constructAppearances(doc) on
 *       each and save.
 *
 *   java ... AnnotAppear2Probe read out.pdf
 *       Re-open and emit, per annotation in page /Annots order:
 *         ANNOT <subtype>
 *         BBOX <x0>,<y0>,<x1>,<y1>     (canonical floats; or "none"/NOAP)
 *         OP:<name>                     one line per operator token
 *         END
 *
 *   Operator-only fingerprint: the operands (numbers/names) are coordinate
 *   dependent and float-format dependent, so we compare the operator KEYWORD
 *   sequence plus the canonical-float /AP /N /BBox. A missing / wrong / extra
 *   drawing operator or a wrong bbox is caught; coordinate precision is
 *   normalised. NOAP is emitted when the type has no built-in handler
 *   (Popup, Stamp) so "no appearance generated" is itself a comparable fact.
 */
public final class AnnotAppear2Probe {
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

            // --- Text: note icon, yellow background ---
            PDAnnotationText text = new PDAnnotationText();
            text.setRectangle(new PDRectangle(50, 750, 20, 20));
            text.setName(PDAnnotationText.NAME_NOTE);
            text.setColor(rgb(1, 1, 0));
            text.setContents("a note");
            text.constructAppearances(doc);
            page.getAnnotations().add(text);

            // --- Caret: magenta ---
            PDAnnotationCaret caret = new PDAnnotationCaret();
            caret.setRectangle(new PDRectangle(100, 700, 30, 30));
            caret.setColor(rgb(1, 0, 1));
            caret.constructAppearances(doc);
            page.getAnnotations().add(caret);

            // --- FileAttachment: push-pin icon ---
            PDAnnotationFileAttachment fa = new PDAnnotationFileAttachment();
            fa.setRectangle(new PDRectangle(150, 700, 30, 30));
            fa.setAttachmentName(PDAnnotationFileAttachment.ATTACHMENT_NAME_PUSH_PIN);
            fa.setColor(rgb(0, 0, 0));
            fa.constructAppearances(doc);
            page.getAnnotations().add(fa);

            // --- StrikeOut: red, one quad ---
            PDAnnotationStrikeout strike = new PDAnnotationStrikeout();
            strike.setRectangle(new PDRectangle(50, 600, 250, 20));
            strike.setQuadPoints(new float[] {
                50, 616, 300, 616, 50, 604, 300, 604,
            });
            strike.setColor(rgb(1, 0, 0));
            strike.constructAppearances(doc);
            page.getAnnotations().add(strike);

            // --- Underline: blue, one quad ---
            PDAnnotationUnderline underline = new PDAnnotationUnderline();
            underline.setRectangle(new PDRectangle(50, 560, 250, 20));
            underline.setQuadPoints(new float[] {
                50, 576, 300, 576, 50, 564, 300, 564,
            });
            underline.setColor(rgb(0, 0, 1));
            underline.constructAppearances(doc);
            page.getAnnotations().add(underline);

            // --- Squiggly: green, one quad ---
            PDAnnotationSquiggly squiggly = new PDAnnotationSquiggly();
            squiggly.setRectangle(new PDRectangle(50, 520, 250, 20));
            squiggly.setQuadPoints(new float[] {
                50, 536, 300, 536, 50, 524, 300, 524,
            });
            squiggly.setColor(rgb(0, 1, 0));
            squiggly.constructAppearances(doc);
            page.getAnnotations().add(squiggly);

            // --- FreeText: text box, black text ---
            PDAnnotationFreeText freeText = new PDAnnotationFreeText();
            freeText.setRectangle(new PDRectangle(50, 350, 200, 100));
            freeText.setContents("Free text content");
            freeText.setColor(rgb(0, 0, 0));
            freeText.setDefaultAppearance("/Helv 12 Tf 0 g");
            freeText.constructAppearances(doc);
            page.getAnnotations().add(freeText);

            // --- Popup: no built-in handler upstream → expect NOAP ---
            PDAnnotationPopup popup = new PDAnnotationPopup();
            popup.setRectangle(new PDRectangle(300, 350, 150, 100));
            popup.constructAppearances(doc);
            page.getAnnotations().add(popup);

            // --- Stamp (RubberStamp): no built-in handler upstream → NOAP ---
            PDAnnotationRubberStamp stamp = new PDAnnotationRubberStamp();
            stamp.setRectangle(new PDRectangle(300, 200, 150, 100));
            stamp.setName(PDAnnotationRubberStamp.NAME_TOP_SECRET);
            stamp.constructAppearances(doc);
            page.getAnnotations().add(stamp);

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
}
