import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.interactive.annotation.AnnotationFilter;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationCircle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLine;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPopup;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquare;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationHighlight;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationText;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;

/**
 * Live oracle probe for <code>PDPage.getAnnotations()</code> factory dispatch,
 * order preservation, and the <code>getAnnotations(AnnotationFilter)</code>
 * overload.
 *
 * Builds a single-page document with a deterministic mix of annotation
 * subtypes on <code>/Annots</code> (Link / Text / Square / Circle / Widget /
 * Line / Popup / Highlight, plus an unknown subtype and a /Subtype-less dict),
 * saves it to bytes and reloads it. Reloading makes PDFBox write the /Annots
 * entries as indirect objects, so the parse-back path exercises real
 * indirect-reference resolution while order must still match the original
 * array order.
 *
 * Output JSON (UTF-8, no trailing newline):
 * {
 *   "all":     [ {"cls":..,"subtype":..,"rect":[x0,y0,x1,y1]}, ... ],  // /Annots order
 *   "widgets": [ ... ]                                                  // filter == Widget only
 * }
 *
 * Rect corners are emitted as nearest-int so float-format differences between
 * the two stacks never cause a spurious mismatch. A missing /Rect is "null".
 */
public final class PageAnnotRetrievalProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] pdf = buildPdf();
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            PDPage page = doc.getPage(0);

            StringBuilder sb = new StringBuilder();
            sb.append('{');
            sb.append("\"all\":");
            emitList(sb, page.getAnnotations());
            sb.append(',');
            sb.append("\"widgets\":");
            AnnotationFilter widgetOnly = new AnnotationFilter() {
                @Override
                public boolean accept(PDAnnotation annotation) {
                    return annotation instanceof PDAnnotationWidget;
                }
            };
            emitList(sb, page.getAnnotations(widgetOnly));
            sb.append('}');
            out.print(sb);
        }
    }

    private static byte[] buildPdf() throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.A4);
            doc.addPage(page);

            COSArray annots = new COSArray();

            PDAnnotationLink link = new PDAnnotationLink();
            link.setRectangle(new PDRectangle(10, 20, 100, 30));
            annots.add(link);

            PDAnnotationText text = new PDAnnotationText();
            text.setRectangle(new PDRectangle(50, 60, 18, 20));
            annots.add(text);

            PDAnnotationSquare square = new PDAnnotationSquare();
            square.setRectangle(new PDRectangle(120, 200, 80, 40));
            annots.add(square);

            PDAnnotationCircle circle = new PDAnnotationCircle();
            circle.setRectangle(new PDRectangle(300, 400, 60, 60));
            annots.add(circle);

            PDAnnotationWidget widget = new PDAnnotationWidget();
            widget.setRectangle(new PDRectangle(15, 700, 200, 30));
            annots.add(widget);

            PDAnnotationLine line = new PDAnnotationLine();
            line.setRectangle(new PDRectangle(0, 0, 595, 842));
            annots.add(line);

            PDAnnotationPopup popup = new PDAnnotationPopup();
            popup.setRectangle(new PDRectangle(400, 500, 150, 100));
            annots.add(popup);

            PDAnnotationHighlight hl = new PDAnnotationHighlight();
            hl.setRectangle(new PDRectangle(200, 210, 240, 225));
            annots.add(hl);

            // Unknown subtype — factory falls back to PDAnnotationUnknown.
            COSDictionary unknown = new COSDictionary();
            unknown.setItem(COSName.TYPE, COSName.ANNOT);
            unknown.setItem(COSName.SUBTYPE, COSName.getPDFName("Frobnicate"));
            COSArray uRect = new COSArray();
            uRect.add(COSInteger.get(1));
            uRect.add(COSInteger.get(2));
            uRect.add(COSInteger.get(3));
            uRect.add(COSInteger.get(4));
            unknown.setItem(COSName.RECT, uRect);
            annots.add(unknown);

            // Subtype-less dict — factory still returns PDAnnotationUnknown.
            COSDictionary noSub = new COSDictionary();
            noSub.setItem(COSName.TYPE, COSName.ANNOT);
            annots.add(noSub);

            page.getCOSObject().setItem(COSName.ANNOTS, annots);

            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            doc.save(baos);
            return baos.toByteArray();
        }
    }

    private static void emitList(StringBuilder sb, List<PDAnnotation> list) {
        sb.append('[');
        for (int i = 0; i < list.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            emitAnnot(sb, list.get(i));
        }
        sb.append(']');
    }

    private static void emitAnnot(StringBuilder sb, PDAnnotation annot) {
        sb.append('{');
        sb.append("\"cls\":\"").append(annot.getClass().getSimpleName()).append('"');
        sb.append(',');
        String subtype = annot.getSubtype();
        sb.append("\"subtype\":");
        if (subtype == null) {
            sb.append("null");
        } else {
            sb.append('"').append(subtype).append('"');
        }
        sb.append(',');
        sb.append("\"rect\":");
        PDRectangle r = annot.getRectangle();
        if (r == null) {
            sb.append("null");
        } else {
            sb.append('[')
                    .append(Math.round(r.getLowerLeftX())).append(',')
                    .append(Math.round(r.getLowerLeftY())).append(',')
                    .append(Math.round(r.getUpperRightX())).append(',')
                    .append(Math.round(r.getUpperRightY()))
                    .append(']');
        }
        sb.append('}');
    }
}
