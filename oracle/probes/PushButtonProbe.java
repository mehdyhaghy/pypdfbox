import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDButton;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDPushButton;

/**
 * Live oracle probe for PDPushButton field + /MK appearance characteristics
 * captions.
 *
 * Usage: java PushButtonProbe read in.pdf name [name ...]
 *
 * For each named push-button field, emit one LF-terminated record:
 *
 *   <name>\t<kind>\t<facts...>
 *
 * where <kind> is "pushbutton" / "other" / "&lt;missing&gt;" and facts are:
 *
 *   isPushbutton=<0/1>\tisRadio=<0/1>\tfieldType=<FT>
 *   \tvalue=<getValue>\tvalueAsString=<getValueAsString>
 *   \tdefaultValue=<getDefaultValue>\twidgetCount=<n>
 *   \tnormalCaption=<MK /CA on widget0 or "&lt;none&gt;">
 *   \trolloverCaption=<MK /RC on widget0 or "&lt;none&gt;">
 *   \talternateCaption=<MK /AC on widget0 or "&lt;none&gt;">
 *
 * The /MK captions are read via
 * PDAnnotationWidget.getAppearanceCharacteristics() ->
 * PDAppearanceCharacteristicsDictionary.getNormalCaption() / getRolloverCaption()
 * / getAlternateCaption().
 */
public final class PushButtonProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if (!"read".equals(mode)) {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
        File in = new File(args[1]);
        try (PDDocument doc = Loader.loadPDF(in)) {
            PDAcroForm form = doc.getDocumentCatalog().getAcroForm();
            StringBuilder sb = new StringBuilder();
            for (int i = 2; i < args.length; i++) {
                String name = args[i];
                PDField field = form == null ? null : form.getField(name);
                if (field == null) {
                    sb.append(name).append("\t<missing>\n");
                    continue;
                }
                sb.append(line(name, field)).append('\n');
            }
            out.print(sb);
        }
    }

    private static String line(String name, PDField field) {
        if (field instanceof PDPushButton) {
            return name + "\tpushbutton\t" + pushButtonFacts((PDPushButton) field);
        }
        // Some other /Btn (radio / checkbox) or unrelated field — still emit the
        // pushbutton flag so the diff stays meaningful when dispatch goes wrong.
        boolean isPb = false;
        boolean isRadio = false;
        if (field instanceof PDButton) {
            PDButton btn = (PDButton) field;
            isPb = btn.isPushButton();
            isRadio = btn.isRadioButton();
        }
        return name + "\tother\tisPushbutton=" + (isPb ? "1" : "0")
                + "\tisRadio=" + (isRadio ? "1" : "0")
                + "\tfieldType=" + esc(field.getFieldType());
    }

    private static String pushButtonFacts(PDPushButton pb) {
        boolean isPb = pb.isPushButton();
        boolean isRadio = pb.isRadioButton();
        List<PDAnnotationWidget> widgets = pb.getWidgets();
        int widgetCount = widgets.size();
        String normal = "<none>";
        String rollover = "<none>";
        String alternate = "<none>";
        if (widgetCount > 0) {
            PDAnnotationWidget w = widgets.get(0);
            PDAppearanceCharacteristicsDictionary mk =
                    w.getAppearanceCharacteristics();
            if (mk == null) {
                // Fall back: widget may inherit /MK from the field dict; check
                // there directly.
                COSDictionary fieldCos = pb.getCOSObject();
                COSDictionary mkDict = (COSDictionary) fieldCos
                        .getDictionaryObject(COSName.getPDFName("MK"));
                if (mkDict != null) {
                    mk = new PDAppearanceCharacteristicsDictionary(mkDict);
                }
            }
            if (mk != null) {
                String ca = mk.getNormalCaption();
                String rc = mk.getRolloverCaption();
                String ac = mk.getAlternateCaption();
                if (ca != null) {
                    normal = ca;
                }
                if (rc != null) {
                    rollover = rc;
                }
                if (ac != null) {
                    alternate = ac;
                }
            }
        }
        return "isPushbutton=" + (isPb ? "1" : "0")
                + "\tisRadio=" + (isRadio ? "1" : "0")
                + "\tfieldType=" + esc(pb.getFieldType())
                + "\tvalue=" + esc(pb.getValue())
                + "\tvalueAsString=" + esc(pb.getValueAsString())
                + "\tdefaultValue=" + esc(pb.getDefaultValue())
                + "\twidgetCount=" + widgetCount
                + "\tnormalCaption=" + esc(normal)
                + "\trolloverCaption=" + esc(rollover)
                + "\talternateCaption=" + esc(alternate);
    }

    private static String esc(String s) {
        if (s == null) {
            return "<null>";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
