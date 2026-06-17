import java.io.File;
import java.io.PrintStream;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationCircle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquare;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderEffectDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for the CLOUDY-BORDER appearance generation surface
 * (PDF 32000 §12.5.4 /BE /S C — the "cloudy" border effect).
 *
 * This is the markup-appearance surface that the earlier AnnotAppearGen /
 * AnnotApAppearance probes did NOT exercise: those built Square / Circle
 * annotations with a SOLID border, so the generated /AP /N was a plain
 * `re` rectangle (square) or a four-Bezier ellipse (circle).  Setting a
 * cloudy border effect (/BE) routes PDSquareAppearanceHandler /
 * PDCircleAppearanceHandler through CloudyBorder.createCloudyRectangle /
 * createCloudyEllipse, which emits a curl-Bezier token stream and — crucially
 * — REWRITES the annotation /Rect, the form-XObject /BBox + /Matrix, and the
 * /RD rect-difference from the computed cloud geometry.
 *
 * Two modes (mirrors AnnotAppearGenProbe):
 *
 *   java ... CloudyBorderProbe write out.pdf
 *       Build a page with a cloudy Square and a cloudy Circle (each with a
 *       stroke colour, interior colour, border width, and intensity), call
 *       constructAppearances(doc) on each, save.
 *
 *   java ... CloudyBorderProbe read out.pdf
 *       Re-open and emit, per annotation (in /Annots order):
 *
 *         ANNOT <subtype>
 *         RECT <x0>,<y0>,<x1>,<y1>      annotation /Rect (canonical floats)
 *         BBOX <x0>,<y0>,<x1>,<y1>      form-XObject /BBox
 *         MTX  <a>,<b>,<c>,<d>,<e>,<f>  form-XObject /Matrix
 *         RD   <l>,<t>,<r>,<b>          /RD rect-difference (or "RD none")
 *         OP:<name>                      one per operator token
 *         OPCOUNT <n>                    total operator count
 *         END
 *
 * Square's cloudy rectangle is a pure polygon-curl path (no Ellipse2D
 * dependency) so its operator sequence + geometry are byte-exact across
 * implementations.  Circle's cloudy ellipse flattens via java.awt Ellipse2D
 * upstream vs an equal-angle emulation in the lite port (documented
 * divergence), so for Circle the test asserts the geometry contract (a real
 * cloudy /BBox enlargement + identity-translate /Matrix + non-trivial curl
 * output) rather than an exact operator count.
 */
public final class CloudyBorderProbe {
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

    private static PDBorderEffectDictionary cloudy(float intensity) {
        PDBorderEffectDictionary be = new PDBorderEffectDictionary();
        be.setStyle(PDBorderEffectDictionary.STYLE_CLOUDY);
        be.setIntensity(intensity);
        return be;
    }

    private static void write(File file) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.A4);
            doc.addPage(page);

            // --- Square: cloudy border, stroke blue, interior yellow, w=2, I=1 ---
            PDAnnotationSquare square = new PDAnnotationSquare();
            square.setRectangle(new PDRectangle(100, 100, 200, 150));
            square.setColor(rgb(0, 0, 1));
            square.setInteriorColor(rgb(1, 1, 0));
            PDBorderStyleDictionary squareBs = new PDBorderStyleDictionary();
            squareBs.setWidth(2);
            square.setBorderStyle(squareBs);
            square.setBorderEffect(cloudy(1));
            square.constructAppearances(doc);
            page.getAnnotations().add(square);

            // --- Circle: cloudy border, stroke green, interior pink, w=2, I=2 ---
            PDAnnotationCircle circle = new PDAnnotationCircle();
            circle.setRectangle(new PDRectangle(120, 400, 220, 160));
            circle.setColor(rgb(0, 0.5f, 0));
            circle.setInteriorColor(rgb(1, 0.7f, 0.8f));
            PDBorderStyleDictionary circleBs = new PDBorderStyleDictionary();
            circleBs.setWidth(2);
            circle.setBorderStyle(circleBs);
            circle.setBorderEffect(cloudy(2));
            circle.constructAppearances(doc);
            page.getAnnotations().add(circle);

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

        PDRectangle rect = annot.getRectangle();
        sb.append("RECT ").append(rectStr(rect)).append('\n');

        PDAppearanceStream stream = null;
        if (annot.getAppearance() != null
                && annot.getAppearance().getNormalAppearance() != null
                && !annot.getAppearance().getNormalAppearance().isSubDictionary()) {
            stream = annot.getAppearance().getNormalAppearance().getAppearanceStream();
        }
        if (stream == null) {
            sb.append("NOAP\nEND\n");
            return;
        }

        sb.append("BBOX ").append(rectStr(stream.getBBox())).append('\n');

        Matrix m = stream.getMatrix();
        sb.append("MTX ")
                .append(canon(m.getValue(0, 0))).append(',')
                .append(canon(m.getValue(0, 1))).append(',')
                .append(canon(m.getValue(1, 0))).append(',')
                .append(canon(m.getValue(1, 1))).append(',')
                .append(canon(m.getValue(2, 0))).append(',')
                .append(canon(m.getValue(2, 1))).append('\n');

        // /RD on the annotation dictionary (set by the cloudy handler).
        float[] rd = null;
        if (annot instanceof PDAnnotationSquare sq) {
            PDRectangle d = sq.getRectDifference();
            if (d != null) {
                rd = new float[] {
                    d.getLowerLeftX(), d.getUpperRightY(),
                    d.getUpperRightX(), d.getLowerLeftY()
                };
            }
        } else if (annot instanceof PDAnnotationCircle ci) {
            PDRectangle d = ci.getRectDifference();
            if (d != null) {
                rd = new float[] {
                    d.getLowerLeftX(), d.getUpperRightY(),
                    d.getUpperRightX(), d.getLowerLeftY()
                };
            }
        }
        if (rd == null) {
            sb.append("RD none\n");
        } else {
            sb.append("RD ")
                    .append(canon(rd[0])).append(',')
                    .append(canon(rd[1])).append(',')
                    .append(canon(rd[2])).append(',')
                    .append(canon(rd[3])).append('\n');
        }

        int count = 0;
        PDFStreamParser parser = new PDFStreamParser(stream);
        List<Object> tokens = parser.parse();
        for (Object tok : tokens) {
            if (tok instanceof Operator op) {
                sb.append("OP:").append(op.getName()).append('\n');
                count++;
            }
        }
        sb.append("OPCOUNT ").append(count).append('\n');
        sb.append("END\n");
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
}
