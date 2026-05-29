import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDRadioButton;

/**
 * Live oracle probe for the AcroForm RADIO-BUTTON GROUP surface that the
 * existing ChoiceButtonProbe does NOT cover: a radio group carrying /Opt
 * export values, driven through getSelectedExportValues(), the
 * isRadiosInUnison() flag, and the setValue(int) index overload.
 *
 * Modes (all operate on a named PDRadioButton field):
 *
 *   READ:  java RadioGroupProbe read in.pdf name [name ...]
 *          For each named radio field emit one LF-terminated record:
 *
 *            <name>\tradio\t<facts...>
 *
 *          facts (all multi-valued columns '|' joined):
 *            onValues=<sorted union of on-state names>
 *            value=<getValue()>
 *            exportValues=<getExportValues(), /Opt order>
 *            selectedExport=<getSelectedExportValues()>
 *            selectedIndex=<getSelectedIndex()>
 *            radiosInUnison=<0/1>
 *            widgetAS=<each widget /AS, /Off when none>
 *            widgetOn=<each widget's first non-Off /AP /N key>
 *
 *   SET:   java RadioGroupProbe set in.pdf out.pdf name value
 *          PDRadioButton.setValue(String value), then doc.save(out).
 *
 *   SETINDEX: java RadioGroupProbe setindex in.pdf out.pdf name idx
 *          PDRadioButton.setValue(int idx), then doc.save(out).
 *
 * The READ mode is the differential surface; SET / SETINDEX then a READ of the
 * saved file (driven from the Python side) verifies the set round trip.
 */
public final class RadioGroupProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("set".equals(mode)) {
            doSet(args, false);
        } else if ("setindex".equals(mode)) {
            doSet(args, true);
        } else if ("read".equals(mode)) {
            doRead(args, out);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void doSet(String[] args, boolean byIndex) throws Exception {
        File in = new File(args[1]);
        File outFile = new File(args[2]);
        String name = args[3];
        String value = args[4];
        try (PDDocument doc = Loader.loadPDF(in)) {
            PDAcroForm form = doc.getDocumentCatalog().getAcroForm();
            PDRadioButton rb = (PDRadioButton) form.getField(name);
            if (byIndex) {
                rb.setValue(Integer.parseInt(value));
            } else {
                rb.setValue(value);
            }
            doc.save(outFile);
        }
    }

    private static void doRead(String[] args, PrintStream out) throws Exception {
        File in = new File(args[1]);
        try (PDDocument doc = Loader.loadPDF(in)) {
            PDAcroForm form = doc.getDocumentCatalog().getAcroForm();
            StringBuilder sb = new StringBuilder();
            for (int i = 2; i < args.length; i++) {
                String name = args[i];
                PDField field = form == null ? null : form.getField(name);
                if (!(field instanceof PDRadioButton)) {
                    sb.append(name).append("\t<missing>\n");
                    continue;
                }
                sb.append(name).append("\tradio\t")
                        .append(radioFacts((PDRadioButton) field)).append('\n');
            }
            out.print(sb);
        }
    }

    private static String radioFacts(PDRadioButton rb) {
        java.util.Set<String> onValues = rb.getOnValues();
        List<String> exportValues = rb.getExportValues();
        List<String> selectedExport = rb.getSelectedExportValues();
        List<String> as = new ArrayList<>();
        List<String> widgetOn = new ArrayList<>();
        for (PDAnnotationWidget w : rb.getWidgets()) {
            COSName asName = (COSName) w.getCOSObject()
                    .getDictionaryObject(COSName.AS);
            as.add(asName == null ? "Off" : asName.getName());
            widgetOn.add(onValueForWidget(w));
        }
        return "onValues=" + joinStr(sorted(onValues))
                + "\tvalue=" + esc(rb.getValue())
                + "\texportValues=" + joinStr(exportValues)
                + "\tselectedExport=" + joinStr(selectedExport)
                + "\tselectedIndex=" + rb.getSelectedIndex()
                + "\tradiosInUnison=" + (rb.isRadiosInUnison() ? "1" : "0")
                + "\twidgetAS=" + joinStr(as)
                + "\twidgetOn=" + joinStr(widgetOn);
    }

    private static String onValueForWidget(PDAnnotationWidget w) {
        org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary ap =
                w.getAppearance();
        if (ap == null || ap.getNormalAppearance() == null) {
            return "<none>";
        }
        for (COSName key : ap.getNormalAppearance().getSubDictionary().keySet()) {
            if (!COSName.Off.equals(key)) {
                return key.getName();
            }
        }
        return "<none>";
    }

    private static List<String> sorted(java.util.Set<String> s) {
        List<String> out = new ArrayList<>(s);
        java.util.Collections.sort(out);
        return out;
    }

    private static String joinStr(List<String> list) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < list.size(); i++) {
            if (i > 0) {
                sb.append('|');
            }
            sb.append(esc(list.get(i)));
        }
        return sb.toString();
    }

    private static String esc(String s) {
        if (s == null) {
            return "none";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t").replace("|", "\\u007c");
    }
}
