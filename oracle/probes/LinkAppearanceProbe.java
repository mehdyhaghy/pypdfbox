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
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary;

/**
 * Live oracle probe for LINK annotation appearance generation — the
 * OPERAND-LEVEL /AP /N content (not just operator keywords).
 *
 * Drives PDLinkAppearanceHandler.generateNormalAppearance() (invoked via
 * PDAnnotationLink.constructAppearances(doc)) and emits the FULL token stream —
 * every operand number/name canonicalised to 3 decimals — so the padded
 * border-edge quad (m / l / l / l / h), the dashed-border dash pattern ([..] 0
 * d), the STYLE_UNDERLINE single-edge path (no close), the explicit /QuadPoints
 * sub-paths, the /C stroke colour and the rewritten /BBox are all caught
 * byte-for-byte.
 *
 * Six Link variants are written (one per page); because all share subtype
 * "Link" the records are keyed by their /Annots ordinal index (LINK0, LINK1…):
 *
 *   0: plain solid border, default colour (no /C → black gray 0), width 1
 *   1: red /C, solid border, width 3
 *   2: dashed border ([3 2] dash), green /C, width 2
 *   3: underline border style (single edge, no close), blue /C, width 2
 *   4: explicit /QuadPoints inside /Rect, magenta /C, width 1
 *   5: /QuadPoints partly OUTSIDE /Rect (ignored → falls back to /Rect), w 2
 *
 * Modes:
 *
 *   java ... LinkAppearanceProbe write out.pdf
 *   java ... LinkAppearanceProbe read out.pdf
 *       Re-open and emit, per annotation (in /Annots order):
 *         ANNOT LINK<idx>
 *         RECT <x0>,<y0>,<x1>,<y1>      annotation /Rect (canonical floats)
 *         BBOX <x0>,<y0>,<x1>,<y1>      form-XObject /BBox
 *         TOK <canonical token>          one per content-stream token
 *         END
 */
public final class LinkAppearanceProbe {
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

    private static PDBorderStyleDictionary border(float width, String style) {
        PDBorderStyleDictionary bs = new PDBorderStyleDictionary();
        bs.setWidth(width);
        if (style != null) {
            bs.setStyle(style);
        }
        return bs;
    }

    private static void write(File file) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            // 0: plain solid border, no /C (black gray 0), width 1
            PDPage p0 = new PDPage(PDRectangle.A4);
            doc.addPage(p0);
            PDAnnotationLink a0 = new PDAnnotationLink();
            a0.setRectangle(new PDRectangle(50, 500, 200, 40));
            a0.setBorderStyle(border(1, PDBorderStyleDictionary.STYLE_SOLID));
            a0.constructAppearances(doc);
            p0.getAnnotations().add(a0);

            // 1: red /C, solid, width 3
            PDPage p1 = new PDPage(PDRectangle.A4);
            doc.addPage(p1);
            PDAnnotationLink a1 = new PDAnnotationLink();
            a1.setRectangle(new PDRectangle(50, 400, 200, 40));
            a1.setColor(rgb(1, 0, 0));
            a1.setBorderStyle(border(3, PDBorderStyleDictionary.STYLE_SOLID));
            a1.constructAppearances(doc);
            p1.getAnnotations().add(a1);

            // 2: dashed border [3 2], green /C, width 2
            PDPage p2 = new PDPage(PDRectangle.A4);
            doc.addPage(p2);
            PDAnnotationLink a2 = new PDAnnotationLink();
            a2.setRectangle(new PDRectangle(50, 300, 200, 40));
            a2.setColor(rgb(0, 1, 0));
            PDBorderStyleDictionary dbs = border(2, PDBorderStyleDictionary.STYLE_DASHED);
            COSArray dash = new COSArray();
            dash.add(org.apache.pdfbox.cos.COSInteger.get(3));
            dash.add(org.apache.pdfbox.cos.COSInteger.get(2));
            dbs.setDashStyle(dash);
            a2.setBorderStyle(dbs);
            a2.constructAppearances(doc);
            p2.getAnnotations().add(a2);

            // 3: underline border style (single edge, no close), blue /C, w 2
            PDPage p3 = new PDPage(PDRectangle.A4);
            doc.addPage(p3);
            PDAnnotationLink a3 = new PDAnnotationLink();
            a3.setRectangle(new PDRectangle(50, 200, 200, 40));
            a3.setColor(rgb(0, 0, 1));
            a3.setBorderStyle(border(2, PDBorderStyleDictionary.STYLE_UNDERLINE));
            a3.constructAppearances(doc);
            p3.getAnnotations().add(a3);

            // 4: explicit /QuadPoints inside /Rect, magenta /C, width 1
            PDPage p4 = new PDPage(PDRectangle.A4);
            doc.addPage(p4);
            PDAnnotationLink a4 = new PDAnnotationLink();
            a4.setRectangle(new PDRectangle(50, 100, 200, 40));
            a4.setColor(rgb(1, 0, 1));
            a4.setQuadPoints(new float[] {60, 110, 240, 110, 240, 130, 60, 130});
            a4.setBorderStyle(border(1, PDBorderStyleDictionary.STYLE_SOLID));
            a4.constructAppearances(doc);
            p4.getAnnotations().add(a4);

            // 5: /QuadPoints partly OUTSIDE /Rect (ignored → /Rect), w 2
            PDPage p5 = new PDPage(PDRectangle.A4);
            doc.addPage(p5);
            PDAnnotationLink a5 = new PDAnnotationLink();
            a5.setRectangle(new PDRectangle(50, 60, 200, 30));
            a5.setColor(rgb(0, 0, 0));
            // 9999 lies outside /Rect → handler discards QuadPoints, uses /Rect
            a5.setQuadPoints(new float[] {60, 70, 9999, 70, 9999, 80, 60, 80});
            a5.setBorderStyle(border(2, PDBorderStyleDictionary.STYLE_SOLID));
            a5.constructAppearances(doc);
            p5.getAnnotations().add(a5);

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
        sb.append("ANNOT LINK").append(idx).append('\n');
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
        if (tok instanceof COSArray) {
            COSArray a = (COSArray) tok;
            StringBuilder s = new StringBuilder("[");
            for (int i = 0; i < a.size(); ++i) {
                if (i > 0) {
                    s.append(' ');
                }
                COSBase b = a.getObject(i);
                if (b instanceof COSNumber) {
                    s.append(canon(((COSNumber) b).floatValue()));
                } else {
                    s.append(String.valueOf(b));
                }
            }
            return s.append(']').toString();
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
