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
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFileAttachment;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;

/**
 * Live oracle probe for FILE-ATTACHMENT annotation appearance generation —
 * the OPERAND-LEVEL /AP /N content (not just operator keywords).
 *
 * Drives PDFileAttachmentAppearanceHandler.generateNormalAppearance() (invoked
 * via PDAnnotationFileAttachment.constructAppearances(doc)) for each of the four
 * standard attachment icons — PushPin (default), Paperclip, Graph, Tag — and
 * emits the FULL token stream, every operand number/name canonicalised to 3
 * decimals. The four icon glyph paths are exact SVG-derived ports upstream, so
 * a wrong control point, a wrong icon-dispatch, a missing q/Q (Tag), a wrong
 * scale/translate cm matrix, or a wrongly-rewritten /Rect or /BBox is caught
 * byte-for-byte.
 *
 * Two modes:
 *
 *   java ... FileAttachmentIconProbe write out.pdf
 *       Build a page with four FileAttachment annotations (one per icon) and
 *       call constructAppearances(doc); save. Keyed FA0..FA3 by /Annots order.
 *
 *   java ... FileAttachmentIconProbe read out.pdf
 *       Re-open and emit, per annotation (in /Annots order):
 *
 *         ANNOT <subtype>
 *         RECT <x0>,<y0>,<x1>,<y1>      annotation /Rect (canonical floats)
 *         BBOX <x0>,<y0>,<x1>,<y1>      form-XObject /BBox
 *         TOK <canonical token>          one per content-stream token
 *         END
 */
public final class FileAttachmentIconProbe {
    public static void main(String[] args) throws Exception {
        String mode = args[0];
        File file = new File(args[1]);
        if ("write".equals(mode)) {
            write(file);
        } else {
            read(file);
        }
    }

    private static void write(File file) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.A4);
            doc.addPage(page);

            String[] names = {
                PDAnnotationFileAttachment.ATTACHMENT_NAME_PUSH_PIN,
                PDAnnotationFileAttachment.ATTACHMENT_NAME_PAPERCLIP,
                PDAnnotationFileAttachment.ATTACHMENT_NAME_GRAPH,
                PDAnnotationFileAttachment.ATTACHMENT_NAME_TAG,
            };
            float y = 700;
            for (String name : names) {
                PDAnnotationFileAttachment fa = new PDAnnotationFileAttachment();
                fa.setRectangle(new PDRectangle(50, y, 30, 30));
                fa.setAttachmentName(name);
                fa.constructAppearances(doc);
                page.getAnnotations().add(fa);
                y -= 50;
            }

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
