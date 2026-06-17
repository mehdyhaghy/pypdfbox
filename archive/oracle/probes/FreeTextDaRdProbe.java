import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFreeText;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;

/**
 * Live oracle probe for the FreeText /DA-parse + /RD-rectangle-difference path
 * in PDFreeTextAppearanceHandler.generateNormalAppearance().
 *
 * Distinct from FreeTextLineProbe (which drills the callout / line-ending
 * skeleton): this probe builds a PLAIN (non-callout) FreeText whose /DA carries
 * a non-default font (/Helv 14.5 Tf) and a 3-component RGB non-stroking colour
 * (0.2 0.4 0.6 rg), with a /RD rectangle-difference and NO /DS override. It then
 * fingerprints the generated /AP /N stream as a sequence of operator tokens
 * WITH their numeric/name operands, so a test can verify that:
 *
 *   * the /DA font name + size flow into the AP as ``/Helv 14.5 Tf``;
 *   * the last /DA non-stroking RGB colour flows in as the text ``rg`` triple
 *     and as the ``RG`` stroking triple (Adobe uses /DA's last non-stroking
 *     colour for stroking too);
 *   * /RD shrinks the /BBox exactly (applyRectDifferences).
 *
 * Two modes (mirrors FreeTextLineProbe):
 *
 *   java ... FreeTextDaRdProbe write out.pdf
 *   java ... FreeTextDaRdProbe read  out.pdf
 *
 * read emits, per FreeText annotation:
 *   ANNOT FreeText
 *   DA <string>
 *   RD <canonical floats or null>
 *   RECT <x0>,<y0>,<x1>,<y1>
 *   BBOX <x0>,<y0>,<x1>,<y1>
 *   TOK <op> <operand> <operand> ...     one line per operator token
 *   END
 */
public final class FreeTextDaRdProbe {
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

            PDAnnotationFreeText freeText = new PDAnnotationFreeText();
            freeText.setRectangle(new PDRectangle(100, 500, 240, 120));
            freeText.setContents("hello");
            freeText.setColor(rgb(1, 1, 1)); // white background fill
            // Non-default font + a 3-component RGB non-stroking colour.
            freeText.setDefaultAppearance("/Helv 14.5 Tf 0.2 0.4 0.6 rg");
            // Plain intent (no callout, no line ending).
            freeText.setIntent(PDAnnotationFreeText.IT_FREE_TEXT);
            // Rectangle differences (left, top, right, bottom margins).
            freeText.setRectDifferences(5, 7, 9, 11);
            freeText.constructAppearances(doc);
            page.getAnnotations().add(freeText);

            doc.save(file);
        }
    }

    private static void read(File file) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(file)) {
            for (PDPage page : doc.getPages()) {
                for (PDAnnotation annot : page.getAnnotations()) {
                    if (annot instanceof PDAnnotationFreeText) {
                        emit(sb, (PDAnnotationFreeText) annot);
                    }
                }
            }
        }
        out.print(sb);
    }

    private static void emit(StringBuilder sb, PDAnnotationFreeText ft) throws Exception {
        sb.append("ANNOT FreeText\n");
        sb.append("DA ").append(str(ft.getDefaultAppearance())).append('\n');
        sb.append("RD ").append(floats(ft.getRectDifferences())).append('\n');
        PDRectangle rect = ft.getRectangle();
        sb.append("RECT ").append(rectStr(rect)).append('\n');

        PDAppearanceStream stream = normalStream(ft);
        if (stream == null) {
            sb.append("NOAP\n");
            sb.append("END\n");
            return;
        }
        PDRectangle bbox = stream.getBBox();
        sb.append("BBOX ").append(rectStr(bbox)).append('\n');

        PDFStreamParser parser = new PDFStreamParser(stream);
        List<Object> tokens = parser.parse();
        java.util.ArrayList<String> operands = new java.util.ArrayList<>();
        for (Object tok : tokens) {
            if (tok instanceof Operator) {
                sb.append("TOK ").append(((Operator) tok).getName());
                for (String op : operands) {
                    sb.append(' ').append(op);
                }
                sb.append('\n');
                operands.clear();
            } else if (tok instanceof COSBase) {
                operands.add(operand((COSBase) tok));
            }
        }
        sb.append("END\n");
    }

    private static String operand(COSBase b) {
        if (b instanceof COSName) {
            return "/" + ((COSName) b).getName();
        }
        if (b instanceof COSInteger || b instanceof COSFloat || b instanceof COSNumber) {
            return canonFloat(((COSNumber) b).floatValue());
        }
        return b.toString();
    }

    private static String rectStr(PDRectangle r) {
        if (r == null) {
            return "none";
        }
        return canonFloat(r.getLowerLeftX()) + "," + canonFloat(r.getLowerLeftY())
                + "," + canonFloat(r.getUpperRightX()) + "," + canonFloat(r.getUpperRightY());
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
