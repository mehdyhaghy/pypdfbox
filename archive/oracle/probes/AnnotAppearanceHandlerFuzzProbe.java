import java.io.File;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeSet;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationCircle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFreeText;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationHighlight;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationInk;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLine;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolygon;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolyline;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquare;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquareCircle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationStrikeout;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquiggly;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationTextMarkup;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationUnderline;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe for the markup-annotation APPEARANCE-HANDLER surface — the
 * PDAbstractAppearanceHandler subclasses that synthesise the ``/AP /N`` form
 * XObject for Line / Square / Circle / Polygon / PolyLine / Ink / Highlight /
 * Underline / StrikeOut / Squiggly / FreeText annotations.
 *
 * Existing probes (LineAppearanceProbe, SquareCircleSolidProbe, PolyAppearance,
 * InkAppearance, HighlightBlend, StrikeoutSquiggly, CloudyBorder, BorderStyle)
 * pin the WELL-FORMED token streams byte-for-byte. NONE feed MALFORMED /
 * edge-case COS fields (wrong-arity colour, zero/negative /BS width, empty/zero
 * /D dash, short /L, odd /Vertices, empty/nested /InkList, unknown /LE, negative
 * /RD, wrong-arity /QuadPoints, zero-area /Rect) through constructAppearances.
 *
 * Rather than byte-equality this probe projects a STABLE SHAPE robust to small
 * numeric drift: whether an /AP /N stream was produced, its /BBox, the sorted
 * set of distinct content-stream OPERATORS, and presence flags for a stroke
 * colour op, a fill colour op, and any line-ending marker (a closepath ``h``,
 * used by closed arrows / diamonds). It also reports when generation raises.
 *
 * The corpus is built python-side as raw COS embedded in a non-standard
 * ``/FuzzAnnots`` catalog array of ONE ``corpus.pdf``; this probe loads that
 * exact pdf, walks the array IN ORDER, wraps each dict in its typed subclass,
 * calls constructAppearances(doc), and prints one framed record per case:
 *
 *   CASE <i>
 *   AP <yes|no|ERR:Name>
 *   BBOX <x0,y0,x1,y1|none>
 *   OPS <space separated sorted distinct operators|->
 *   FLAGS stroke=<0|1> fill=<0|1> close=<0|1>
 *   END
 *
 * Usage:  java ... AnnotAppearanceHandlerFuzzProbe <dir-with-corpus.pdf>
 */
public final class AnnotAppearanceHandlerFuzzProbe {
    public static void main(String[] args) throws Exception {
        File dir = new File(args[0]);
        File pdf = new File(dir, "corpus.pdf");
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            COSDictionary catalog = doc.getDocumentCatalog().getCOSObject();
            COSBase raw = catalog.getDictionaryObject(COSName.getPDFName("FuzzAnnots"));
            COSArray arr = (raw instanceof COSArray) ? (COSArray) raw : new COSArray();
            for (int i = 0; i < arr.size(); i++) {
                COSBase entry = arr.getObject(i);
                COSDictionary d = (entry instanceof COSDictionary) ? (COSDictionary) entry : null;
                emit(sb, doc, d, i);
            }
        }
        out.print(sb);
    }

    private static void emit(StringBuilder sb, PDDocument doc, COSDictionary d, int idx) {
        sb.append("CASE ").append(idx).append('\n');
        if (d == null) {
            sb.append("AP no\nBBOX none\nOPS -\nFLAGS stroke=0 fill=0 close=0\nEND\n");
            return;
        }
        PDAnnotation annot;
        try {
            annot = wrap(d);
        } catch (Exception e) {
            sb.append("AP ERR:").append(e.getClass().getSimpleName())
              .append("\nBBOX none\nOPS -\nFLAGS stroke=0 fill=0 close=0\nEND\n");
            return;
        }
        if (annot == null) {
            sb.append("AP no\nBBOX none\nOPS -\nFLAGS stroke=0 fill=0 close=0\nEND\n");
            return;
        }
        try {
            construct(annot, doc);
        } catch (Throwable e) {
            sb.append("AP ERR:").append(e.getClass().getSimpleName())
              .append("\nBBOX none\nOPS -\nFLAGS stroke=0 fill=0 close=0\nEND\n");
            return;
        }
        PDAppearanceStream stream = normalStream(annot);
        if (stream == null) {
            sb.append("AP no\nBBOX none\nOPS -\nFLAGS stroke=0 fill=0 close=0\nEND\n");
            return;
        }
        sb.append("AP yes\n");
        sb.append("BBOX ").append(rectStr(stream.getBBox())).append('\n');
        TreeSet<String> ops = new TreeSet<>();
        boolean stroke = false;
        boolean fill = false;
        boolean close = false;
        try {
            PDFStreamParser parser = new PDFStreamParser(stream);
            List<Object> tokens = parser.parse();
            for (Object tok : tokens) {
                if (tok instanceof Operator) {
                    String name = ((Operator) tok).getName();
                    ops.add(name);
                    if (isStrokeColorOp(name)) {
                        stroke = true;
                    }
                    if (isFillColorOp(name)) {
                        fill = true;
                    }
                    if ("h".equals(name)) {
                        close = true;
                    }
                }
            }
        } catch (Exception e) {
            ops.add("PARSEERR");
        }
        sb.append("OPS ");
        if (ops.isEmpty()) {
            sb.append('-');
        } else {
            sb.append(String.join(" ", ops));
        }
        sb.append('\n');
        sb.append("FLAGS stroke=").append(stroke ? 1 : 0)
          .append(" fill=").append(fill ? 1 : 0)
          .append(" close=").append(close ? 1 : 0).append('\n');
        sb.append("END\n");
    }

    private static boolean isStrokeColorOp(String n) {
        return "RG".equals(n) || "G".equals(n) || "K".equals(n)
                || "SC".equals(n) || "SCN".equals(n) || "CS".equals(n);
    }

    private static boolean isFillColorOp(String n) {
        return "rg".equals(n) || "g".equals(n) || "k".equals(n)
                || "sc".equals(n) || "scn".equals(n) || "cs".equals(n);
    }

    private static PDAnnotation wrap(COSDictionary d) {
        String sub = d.getNameAsString(COSName.SUBTYPE);
        if (sub == null) {
            return null;
        }
        switch (sub) {
            case "Line":
                return new PDAnnotationLine(d);
            case "Square":
                return new PDAnnotationSquare(d);
            case "Circle":
                return new PDAnnotationCircle(d);
            case "Polygon":
                return new PDAnnotationPolygon(d);
            case "PolyLine":
                return new PDAnnotationPolyline(d);
            case "Ink":
                return new PDAnnotationInk(d);
            case "Highlight":
                return new PDAnnotationHighlight(d);
            case "Underline":
                return new PDAnnotationUnderline(d);
            case "StrikeOut":
                return new PDAnnotationStrikeout(d);
            case "Squiggly":
                return new PDAnnotationSquiggly(d);
            case "FreeText":
                return new PDAnnotationFreeText(d);
            default:
                return null;
        }
    }

    private static void construct(PDAnnotation annot, PDDocument doc) throws Exception {
        if (annot instanceof PDAnnotationLine) {
            ((PDAnnotationLine) annot).constructAppearances(doc);
        } else if (annot instanceof PDAnnotationSquareCircle) {
            ((PDAnnotationSquareCircle) annot).constructAppearances(doc);
        } else if (annot instanceof PDAnnotationPolygon) {
            ((PDAnnotationPolygon) annot).constructAppearances(doc);
        } else if (annot instanceof PDAnnotationPolyline) {
            ((PDAnnotationPolyline) annot).constructAppearances(doc);
        } else if (annot instanceof PDAnnotationInk) {
            ((PDAnnotationInk) annot).constructAppearances(doc);
        } else if (annot instanceof PDAnnotationTextMarkup) {
            ((PDAnnotationTextMarkup) annot).constructAppearances(doc);
        } else if (annot instanceof PDAnnotationFreeText) {
            ((PDAnnotationFreeText) annot).constructAppearances(doc);
        }
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

    private static String rectStr(PDRectangle r) {
        if (r == null) {
            return "none";
        }
        return canon(r.getLowerLeftX()) + ","
                + canon(r.getLowerLeftY()) + ","
                + canon(r.getUpperRightX()) + ","
                + canon(r.getUpperRightY());
    }

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
}
