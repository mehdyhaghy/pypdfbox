import java.io.File;
import java.io.PrintStream;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
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
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationCircle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquare;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for the SOLID-border Square / Circle appearance surface —
 * the OPERAND-LEVEL ``/AP /N`` content that the CloudyBorderProbe does NOT
 * exercise (CloudyBorderProbe only drives the ``/BE`` cloudy path).
 *
 * This drives PDSquareAppearanceHandler / PDCircleAppearanceHandler through
 * their SOLID branch (no ``/BE``): the plain ``re`` rectangle (square) and the
 * four-Bezier ellipse (circle, magic constant 0.55555417). It pins:
 *
 *   - default border width (1) — line-width command is suppressed,
 *   - thick width (5) — explicit ``5 w``,
 *   - zero width — no stroke even when a colour is set (drawShape gating),
 *   - interior colour ``/IC`` present vs absent (fill vs no fill),
 *   - dashed ``/BS /D`` — the ``[...] 0 d`` dash operand,
 *   - the ``/RD`` rect-difference REWRITE arithmetic (handleBorderBox: seed
 *     ``/RD`` = width/2 and enlarge ``/Rect`` when ``/RD`` unset),
 *   - the circle's four-Bezier kappa control points.
 *
 * Two modes (mirror FileAttachmentIconProbe / CloudyBorderProbe):
 *
 *   java ... SquareCircleSolidProbe write out.pdf
 *   java ... SquareCircleSolidProbe read out.pdf
 *       emits per annotation (in /Annots order):
 *         ANNOT <subtype>
 *         RECT <x0>,<y0>,<x1>,<y1>      annotation /Rect (after rewrite)
 *         BBOX <x0>,<y0>,<x1>,<y1>      form-XObject /BBox
 *         MTX  <a>,<b>,<c>,<d>,<e>,<f>  form-XObject /Matrix
 *         RD   <l>,<t>,<r>,<b>          /RD rect-difference (or "RD none")
 *         TOK <canonical token>          one per content-stream token
 *         END
 */
public final class SquareCircleSolidProbe {
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

            // 0: Square, default width (no /BS) — stroke blue, fill yellow.
            PDAnnotationSquare s0 = new PDAnnotationSquare();
            s0.setRectangle(new PDRectangle(50, 700, 100, 60));
            s0.setColor(rgb(0, 0, 1));
            s0.setInteriorColor(rgb(1, 1, 0));
            s0.constructAppearances(doc);
            page.getAnnotations().add(s0);

            // 1: Square, thick width 5 — stroke red, no fill.
            PDAnnotationSquare s1 = new PDAnnotationSquare();
            s1.setRectangle(new PDRectangle(50, 600, 100, 60));
            s1.setColor(rgb(1, 0, 0));
            PDBorderStyleDictionary bs1 = new PDBorderStyleDictionary();
            bs1.setWidth(5);
            s1.setBorderStyle(bs1);
            s1.constructAppearances(doc);
            page.getAnnotations().add(s1);

            // 2: Square, zero width — stroke set but suppressed by drawShape,
            //    fill green.
            PDAnnotationSquare s2 = new PDAnnotationSquare();
            s2.setRectangle(new PDRectangle(50, 500, 100, 60));
            s2.setColor(rgb(0, 0, 1));
            s2.setInteriorColor(rgb(0, 1, 0));
            PDBorderStyleDictionary bs2 = new PDBorderStyleDictionary();
            bs2.setWidth(0);
            s2.setBorderStyle(bs2);
            s2.constructAppearances(doc);
            page.getAnnotations().add(s2);

            // 3: Square, dashed /BS /D — stroke black, width 2.
            PDAnnotationSquare s3 = new PDAnnotationSquare();
            s3.setRectangle(new PDRectangle(50, 400, 100, 60));
            s3.setColor(rgb(0, 0, 0));
            PDBorderStyleDictionary bs3 = new PDBorderStyleDictionary();
            bs3.setWidth(2);
            bs3.setStyle(PDBorderStyleDictionary.STYLE_DASHED);
            COSArray dash = new COSArray();
            dash.add(org.apache.pdfbox.cos.COSInteger.get(3));
            dash.add(org.apache.pdfbox.cos.COSInteger.get(2));
            bs3.setDashStyle(dash);
            s3.setBorderStyle(bs3);
            s3.constructAppearances(doc);
            page.getAnnotations().add(s3);

            // 4: Square with a pre-set /RD — exercises the handleBorderBox
            //    "RD already set" branch (no rect enlargement).
            PDAnnotationSquare s4 = new PDAnnotationSquare();
            s4.setRectangle(new PDRectangle(50, 300, 100, 60));
            s4.setColor(rgb(0, 0, 1));
            s4.setRectDifferences(5, 4, 3, 2);
            PDBorderStyleDictionary bs4 = new PDBorderStyleDictionary();
            bs4.setWidth(2);
            s4.setBorderStyle(bs4);
            s4.constructAppearances(doc);
            page.getAnnotations().add(s4);

            // 5: Circle, default width — stroke green, fill pink.
            PDAnnotationCircle c0 = new PDAnnotationCircle();
            c0.setRectangle(new PDRectangle(200, 700, 100, 60));
            c0.setColor(rgb(0, 0.5f, 0));
            c0.setInteriorColor(rgb(1, 0.7f, 0.8f));
            c0.constructAppearances(doc);
            page.getAnnotations().add(c0);

            // 6: Circle, thick width 5 — stroke blue, no fill.
            PDAnnotationCircle c1 = new PDAnnotationCircle();
            c1.setRectangle(new PDRectangle(200, 600, 100, 60));
            c1.setColor(rgb(0, 0, 1));
            PDBorderStyleDictionary cbs1 = new PDBorderStyleDictionary();
            cbs1.setWidth(5);
            c1.setBorderStyle(cbs1);
            c1.constructAppearances(doc);
            page.getAnnotations().add(c1);

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
        if (tok instanceof COSArray) {
            COSArray arr = (COSArray) tok;
            StringBuilder s = new StringBuilder("[");
            for (int i = 0; i < arr.size(); i++) {
                if (i > 0) {
                    s.append(' ');
                }
                COSBase e = arr.getObject(i);
                if (e instanceof COSNumber) {
                    s.append(canon(((COSNumber) e).floatValue()));
                } else {
                    s.append(String.valueOf(e));
                }
            }
            s.append(']');
            return s.toString();
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
}
