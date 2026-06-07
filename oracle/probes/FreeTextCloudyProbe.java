import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
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
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderEffectDictionary;

/**
 * Live oracle probe for the FreeText /BE *cloudy* border path in
 * PDFreeTextAppearanceHandler.generateNormalAppearance() (the
 * borderEffect != null && STYLE_CLOUDY branch, java lines 186-204).
 *
 * Distinct from FreeTextDaRdProbe (plain straight-edged rectangle): this probe
 * builds a FreeText whose /BE carries {@code /S /C /I <intensity>} plus a /RD
 * rectangle-difference, calls constructAppearances(doc), and fingerprints:
 *
 *   * the generated /AP /N appearance op-sequence WITH operands (the cloudy
 *     border emits a series of m / c / re / l moves rather than a single
 *     padded {@code re B}, so the op skeleton differs from the plain path);
 *   * the appearance-stream /BBox and /Matrix the CloudyBorder re-stamps;
 *   * the /Rect and /RD the cloud writes back onto the annotation.
 *
 * Two modes (mirrors FreeTextDaRdProbe):
 *
 *   java ... FreeTextCloudyProbe write out.pdf
 *   java ... FreeTextCloudyProbe read  out.pdf
 *
 * read emits, per FreeText annotation:
 *   ANNOT FreeText
 *   BE <style>,<intensity>
 *   RECT <x0>,<y0>,<x1>,<y1>
 *   RD <canonical floats or null>
 *   BBOX <x0>,<y0>,<x1>,<y1>
 *   MATRIX <a>,<b>,<c>,<d>,<e>,<f>     (or "none")
 *   TOK <op> <operand> ...             one line per operator token
 *   END
 */
public final class FreeTextCloudyProbe {
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
            freeText.setContents("cloudy");
            freeText.setColor(rgb(1, 1, 1)); // white background fill
            freeText.setDefaultAppearance("/Helv 12 Tf 0 0 1 rg");
            freeText.setIntent(PDAnnotationFreeText.IT_FREE_TEXT);
            freeText.setRectDifferences(5, 7, 9, 11);

            // /BE cloudy border, intensity 2.
            PDBorderEffectDictionary be = new PDBorderEffectDictionary();
            be.setStyle(PDBorderEffectDictionary.STYLE_CLOUDY);
            be.setIntensity(2f);
            freeText.setBorderEffect(be);

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
        PDBorderEffectDictionary be = ft.getBorderEffect();
        if (be == null) {
            sb.append("BE null\n");
        } else {
            sb.append("BE ").append(str(be.getStyle())).append(',')
              .append(canonFloat(be.getIntensity())).append('\n');
        }
        sb.append("RECT ").append(rectStr(ft.getRectangle())).append('\n');
        sb.append("RD ").append(floats(ft.getRectDifferences())).append('\n');

        PDAppearanceStream stream = normalStream(ft);
        if (stream == null) {
            sb.append("NOAP\n");
            sb.append("END\n");
            return;
        }
        sb.append("BBOX ").append(rectStr(stream.getBBox())).append('\n');
        sb.append("MATRIX ").append(matrixStr(stream)).append('\n');

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

    private static String matrixStr(PDAppearanceStream stream) {
        COSArray m = stream.getCOSObject().getCOSArray(COSName.MATRIX);
        if (m == null) {
            return "none";
        }
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < m.size(); i++) {
            if (i > 0) {
                b.append(',');
            }
            COSBase e = m.getObject(i);
            b.append(e instanceof COSNumber ? canonFloat(((COSNumber) e).floatValue())
                                            : e.toString());
        }
        return b.toString();
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
