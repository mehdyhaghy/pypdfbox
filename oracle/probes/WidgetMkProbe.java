import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDPushButton;

/**
 * Live oracle probe for the WIDGET /MK appearance-characteristics surface
 * that WidgetApProbe (wave 1434) did NOT cover:
 *
 *   * /RC rollover caption + /AC alternate caption (WidgetApProbe only reads
 *     /CA normal caption);
 *   * the colour ARITY DISPATCH in getBorderColour()/getBackground(): a 1-,
 *     3- or 4-element array yields a DeviceGray / DeviceRGB / DeviceCMYK
 *     PDColor whose components round-trip, while a 2-element (or empty)
 *     array yields null — the high-value differential is whether pypdfbox's
 *     _read_color() coerces the same arities to colours and the same
 *     "other arity" to None;
 *   * /R rotation read on a widget whose /MK is authored by upstream PDFBox.
 *
 * The fixture is BUILT by Apache PDFBox (the authoritative writer) so the
 * differential is purely pypdfbox's READ path against what upstream wrote.
 * Two modes:
 *
 *   1. BUILD: java WidgetMkProbe build out.pdf
 *             Writes a one-page form with five push-button widgets, each
 *             carrying a distinct /MK configuration.
 *
 *   2. READ:  java WidgetMkProbe read in.pdf
 *             For each widget annotation (page /Annots order) emits a
 *             canonical block:
 *
 *               WIDGET <T|->
 *               BC <space-joined canon floats|none>
 *               BG <space-joined canon floats|none>
 *               CA <caption|none>
 *               RC <caption|none>
 *               AC <caption|none>
 *               R <int>
 *               END
 */
public final class WidgetMkProbe {
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

            // 1: DeviceGray /BC (arity 1) + normal caption + rotation 90.
            mk(doc, form, page, "btnGray", 50,
                    new float[] {0.25f}, null, "Push", null, null, 90);
            // 2: DeviceRGB /BC (arity 3) + DeviceGray /BG (arity 1) + all captions.
            mk(doc, form, page, "btnRgb", 110,
                    new float[] {1f, 0.5f, 0f},
                    new float[] {0.8f},
                    "Norm", "Roll", "Alt", 0);
            // 3: DeviceCMYK /BG (arity 4), no /BC, rotation 270.
            mk(doc, form, page, "btnCmyk", 170,
                    null, new float[] {0.1f, 0.2f, 0.3f, 0.4f},
                    null, null, null, 270);
            // 4: arity-2 /BC array -> getBorderColour() must be null.
            mk(doc, form, page, "btnTwo", 230,
                    new float[] {0.3f, 0.6f}, null, null, null, null, 0);
            // 5: empty /MK colour arrays + empty caption strings.
            mk(doc, form, page, "btnEmpty", 290,
                    new float[] {}, new float[] {}, "", "", "", 180);

            doc.save(out);
        }
    }

    private static void mk(PDDocument doc, PDAcroForm form, PDPage page,
            String name, float y, float[] bc, float[] bg,
            String ca, String rc, String ac, int rotation) throws Exception {
        PDPushButton button = new PDPushButton(form);
        button.setPartialName(name);
        form.getFields().add(button);

        PDAnnotationWidget widget = button.getWidgets().get(0);
        widget.setRectangle(new PDRectangle(50, y, 100, 40));
        widget.setPage(page);
        page.getAnnotations().add(widget);

        COSDictionary mk = new COSDictionary();
        if (bc != null) {
            mk.setItem(COSName.BC, toArray(bc));
        }
        if (bg != null) {
            mk.setItem(COSName.BG, toArray(bg));
        }
        if (ca != null) {
            mk.setString(COSName.CA, ca);
        }
        if (rc != null) {
            mk.setString(COSName.getPDFName("RC"), rc);
        }
        if (ac != null) {
            mk.setString(COSName.getPDFName("AC"), ac);
        }
        if (rotation != 0) {
            mk.setInt(COSName.R, rotation);
        }
        widget.getCOSObject().setItem(COSName.MK, mk);
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
        // PDPushButton stores the partial name on the field; the widget is
        // merged into the field dict, so /T is present on the widget too.
        COSBase tName = w.getCOSObject().getDictionaryObject(COSName.T);
        sb.append("WIDGET ").append(tName == null ? "-" : nameStr(tName)).append('\n');

        PDAppearanceCharacteristicsDictionary mk = w.getAppearanceCharacteristics();
        sb.append("BC ").append(mk == null ? "none" : colorArray(mk.getBorderColour())).append('\n');
        sb.append("BG ").append(mk == null ? "none" : colorArray(mk.getBackground())).append('\n');
        sb.append("CA ").append(caption(mk == null ? null : mk.getNormalCaption())).append('\n');
        sb.append("RC ").append(caption(mk == null ? null : mk.getRolloverCaption())).append('\n');
        sb.append("AC ").append(caption(mk == null ? null : mk.getAlternateCaption())).append('\n');
        sb.append("R ").append(mk == null ? 0 : mk.getRotation()).append('\n');
        sb.append("END\n");
    }

    private static String nameStr(COSBase b) {
        // /T is a COSString in PDFBox; COSString.toString() is not the value.
        if (b instanceof org.apache.pdfbox.cos.COSString) {
            return ((org.apache.pdfbox.cos.COSString) b).getString();
        }
        return b.toString();
    }

    private static String caption(String s) {
        return s == null ? "none" : ("[" + s + "]");
    }

    /** Space-joined canonical-float components of a /BC or /BG colour. */
    private static String colorArray(PDColor color) {
        if (color == null) {
            return "none";
        }
        COSArray arr = color.toCOSArray();
        List<String> comps = new ArrayList<>();
        for (int i = 0; i < arr.size(); i++) {
            COSBase b = arr.getObject(i);
            if (b instanceof org.apache.pdfbox.cos.COSNumber) {
                comps.add(canonFloat(((org.apache.pdfbox.cos.COSNumber) b).floatValue()));
            }
        }
        return comps.isEmpty() ? "none" : String.join(" ", comps);
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
