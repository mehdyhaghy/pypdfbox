import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDPushButton;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for the WIDGET /MK push-button ICON surface that
 * WidgetMkProbe (wave 1455 — caption/colour-arity/rotation) and WidgetApProbe
 * (wave 1434 — /AS, /AP keying, /BG /BC /CA /R) did NOT cover:
 *
 *   * /I  normal icon  -> getNormalIcon()    : PDFormXObject
 *   * /RI rollover icon -> getRolloverIcon()  : PDFormXObject
 *   * /IX alternate icon -> getAlternateIcon() : PDFormXObject
 *
 * In PDFBox 3.0.7 PDAppearanceCharacteristicsDictionary exposes the three
 * icon getters as typed PDFormXObject (NOT raw COSStream); there is NO
 * setter, NO getTextPosition()/setTextPosition() (/TP), NO getIconFit()/
 * /IF accessor, and NO PDIconFit class. So this probe pins ONLY the real
 * 3.0.7 surface: the three icon form-XObject references and the facts a
 * caller reads off each returned PDFormXObject (BBox, Matrix, FormType).
 * A null icon getter (entry absent or non-stream) must report "none" under
 * both implementations.
 *
 * The fixture is BUILT by Apache PDFBox (the authoritative writer); /I /RI
 * /IX are installed on the raw /MK dictionary (no upstream setter) exactly
 * as a real form-authoring tool would. The differential is pypdfbox's READ
 * path against what upstream wrote.
 *
 *   BUILD: java WidgetIconProbe build out.pdf
 *   READ:  java WidgetIconProbe read in.pdf
 *
 * READ emits, per widget annotation in page /Annots order:
 *
 *   WIDGET <T|->
 *   I  <bbox|none> ; <matrix> ; <formtype>     (or: I none)
 *   RI <bbox|none> ; <matrix> ; <formtype>     (or: RI none)
 *   IX <bbox|none> ; <matrix> ; <formtype>     (or: IX none)
 *   END
 */
public final class WidgetIconProbe {
    public static void main(String[] args) throws Exception {
        if (args[0].equals("build")) {
            build(new File(args[1]));
        } else {
            read(new File(args[1]));
        }
    }

    private static void build(File out) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.LETTER);
            doc.addPage(page);
            PDAcroForm form = new PDAcroForm(doc);
            doc.getDocumentCatalog().setAcroForm(form);

            // 1: all three icons present, each a distinct BBox/Matrix.
            COSDictionary mk1 = new COSDictionary();
            mk1.setItem(COSName.I, iconStream(doc,
                    new float[] {0, 0, 20, 20},
                    new float[] {1, 0, 0, 1, 0, 0}));
            mk1.setItem(COSName.getPDFName("RI"), iconStream(doc,
                    new float[] {0, 0, 30, 15},
                    new float[] {2, 0, 0, 2, 5, 5}));
            mk1.setItem(COSName.getPDFName("IX"), iconStream(doc,
                    new float[] {1, 2, 41, 22},
                    new float[] {1, 0, 0, 1, 10, 0}));
            button(doc, form, page, "btnAll", 50, mk1);

            // 2: only the normal icon /I; /RI and /IX absent -> null.
            COSDictionary mk2 = new COSDictionary();
            mk2.setItem(COSName.I, iconStream(doc,
                    new float[] {0, 0, 12, 8},
                    new float[] {0.5f, 0, 0, 0.5f, 0, 0}));
            button(doc, form, page, "btnNormalOnly", 110, mk2);

            // 3: /MK present but no icon keys at all -> all three null.
            COSDictionary mk3 = new COSDictionary();
            mk3.setString(COSName.CA, "X");
            button(doc, form, page, "btnNoIcons", 170, mk3);

            // 4: /I key present but value is NOT a stream (a name) -> the
            //    getter must report null, not throw.
            COSDictionary mk4 = new COSDictionary();
            mk4.setItem(COSName.I, COSName.getPDFName("Bogus"));
            button(doc, form, page, "btnBadIcon", 230, mk4);

            doc.save(out);
        }
    }

    private static void button(PDDocument doc, PDAcroForm form, PDPage page,
            String name, float y, COSDictionary mk) throws Exception {
        PDPushButton b = new PDPushButton(form);
        b.setPartialName(name);
        form.getFields().add(b);
        PDAnnotationWidget w = b.getWidgets().get(0);
        w.setRectangle(new PDRectangle(50, y, 50, 40));
        w.setPage(page);
        page.getAnnotations().add(w);
        w.getCOSObject().setItem(COSName.MK, mk);
    }

    /** A minimal form-XObject icon stream with /BBox + /Matrix. */
    private static COSStream iconStream(PDDocument doc, float[] bbox, float[] matrix) {
        COSStream s = doc.getDocument().createCOSStream();
        s.setItem(COSName.TYPE, COSName.XOBJECT);
        s.setItem(COSName.SUBTYPE, COSName.FORM);
        s.setInt(COSName.FORMTYPE, 1);
        s.setItem(COSName.BBOX, toArray(bbox));
        s.setItem(COSName.MATRIX, toArray(matrix));
        return s;
    }

    private static COSArray toArray(float[] comps) {
        COSArray arr = new COSArray();
        for (float c : comps) {
            arr.add(new COSFloat(c));
        }
        return arr;
    }

    private static void read(File file) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(file)) {
            for (PDPage page : doc.getPages()) {
                for (PDAnnotation annot : page.getAnnotations()) {
                    if (annot instanceof PDAnnotationWidget) {
                        emit(sb, (PDAnnotationWidget) annot);
                    }
                }
            }
        }
        out.print(sb);
    }

    private static void emit(StringBuilder sb, PDAnnotationWidget w) {
        COSBase tName = w.getCOSObject().getDictionaryObject(COSName.T);
        sb.append("WIDGET ").append(tName == null ? "-" : nameStr(tName)).append('\n');

        PDAppearanceCharacteristicsDictionary mk = w.getAppearanceCharacteristics();
        sb.append("I ").append(form(mk == null ? null : mk.getNormalIcon())).append('\n');
        sb.append("RI ").append(form(mk == null ? null : mk.getRolloverIcon())).append('\n');
        sb.append("IX ").append(form(mk == null ? null : mk.getAlternateIcon())).append('\n');
        sb.append("END\n");
    }

    private static String nameStr(COSBase b) {
        if (b instanceof org.apache.pdfbox.cos.COSString) {
            return ((org.apache.pdfbox.cos.COSString) b).getString();
        }
        return b.toString();
    }

    /** Canonical facts read off a form-XObject icon: bbox ; matrix ; formtype. */
    private static String form(PDFormXObject f) {
        if (f == null) {
            return "none";
        }
        StringBuilder sb = new StringBuilder();
        PDRectangle r = f.getBBox();
        if (r == null) {
            sb.append("none");
        } else {
            sb.append(canonFloat(r.getLowerLeftX())).append(',')
              .append(canonFloat(r.getLowerLeftY())).append(',')
              .append(canonFloat(r.getUpperRightX())).append(',')
              .append(canonFloat(r.getUpperRightY()));
        }
        sb.append(" ; ");
        Matrix m = f.getMatrix();
        // /Matrix is [a b c d e f] = scaleX shearY shearX scaleY transX transY.
        sb.append(canonFloat(m.getScaleX())).append(' ')
          .append(canonFloat(m.getShearY())).append(' ')
          .append(canonFloat(m.getShearX())).append(' ')
          .append(canonFloat(m.getScaleY())).append(' ')
          .append(canonFloat(m.getTranslateX())).append(' ')
          .append(canonFloat(m.getTranslateY()));
        sb.append(" ; ").append(f.getFormType());
        return sb.toString();
    }

    /** Locale-independent canonical float: half-even to 3 decimals, strip zeros. */
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
}
