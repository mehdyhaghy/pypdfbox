import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDCheckBox;
import org.apache.pdfbox.pdmodel.interactive.form.PDChoice;
import org.apache.pdfbox.pdmodel.interactive.form.PDComboBox;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDListBox;
import org.apache.pdfbox.pdmodel.interactive.form.PDRadioButton;
import org.apache.pdfbox.pdmodel.interactive.form.PDTerminalField;

/**
 * Live oracle probe for CHOICE + BUTTON form-field get/set semantics.
 *
 * Emits canonical, deterministic facts about choice (combo/list-box),
 * radio-button, and checkbox fields so pypdfbox can be diffed against
 * Apache PDFBox's actual behaviour. Two modes:
 *
 *   READ:  java ChoiceButtonProbe read in.pdf name [name ...]
 *          For each named field, emit one LF-terminated line:
 *
 *            <name>\t<kind>\t<facts...>
 *
 *          where <kind> is one of choice / radio / checkbox / other and the
 *          fact columns are kind-specific (see the per-kind helpers below).
 *          All multi-valued columns are joined with '|'.
 *
 *   SET:   java ChoiceButtonProbe set in.pdf out.pdf op [op ...]
 *          Each op is "name=value" applied with the field's typed setValue
 *          (choice: setValue(String) or setValue(List) when value contains
 *          '|'; radio/checkbox: setValue(String)), then doc.save(out.pdf).
 *
 * The READ mode is the differential surface; the SET-then-READ round trip
 * is verified by SET into out.pdf then a READ of that file (driven from the
 * Python side).
 */
public final class ChoiceButtonProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("set".equals(mode)) {
            doSet(args);
        } else if ("read".equals(mode)) {
            doRead(args, out);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void doSet(String[] args) throws Exception {
        File in = new File(args[1]);
        File outFile = new File(args[2]);
        try (PDDocument doc = Loader.loadPDF(in)) {
            PDAcroForm form = doc.getDocumentCatalog().getAcroForm();
            for (int i = 3; i < args.length; i++) {
                int eq = args[i].indexOf('=');
                String name = args[i].substring(0, eq);
                String value = args[i].substring(eq + 1);
                PDField field = form.getField(name);
                if (field instanceof PDChoice) {
                    PDChoice ch = (PDChoice) field;
                    if (value.indexOf('|') >= 0) {
                        List<String> vals = new ArrayList<>();
                        for (String v : value.split("\\|", -1)) {
                            vals.add(v);
                        }
                        ch.setValue(vals);
                    } else {
                        ch.setValue(value);
                    }
                } else if (field instanceof PDRadioButton) {
                    ((PDRadioButton) field).setValue(value);
                } else if (field instanceof PDCheckBox) {
                    PDCheckBox cb = (PDCheckBox) field;
                    if ("__check__".equals(value)) {
                        cb.check();
                    } else if ("__uncheck__".equals(value)) {
                        cb.unCheck();
                    } else {
                        cb.setValue(value);
                    }
                } else if (field instanceof PDTerminalField) {
                    field.setValue(value);
                }
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
                PDField field = form.getField(name);
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
        if (field instanceof PDChoice) {
            return name + "\tchoice\t" + choiceFacts((PDChoice) field);
        }
        if (field instanceof PDRadioButton) {
            return name + "\tradio\t" + radioFacts((PDRadioButton) field);
        }
        if (field instanceof PDCheckBox) {
            return name + "\tcheckbox\t" + checkboxFacts((PDCheckBox) field);
        }
        return name + "\tother\t" + esc(field.getValueAsString());
    }

    /**
     * Choice facts:
     *   export=<e1|e2|...>\tdisplay=<d1|...>\tvalue=<v1|...>
     *   \tindices=<i1|...>\tmulti=<0/1>\tcombo=<0/1>\tvalueAsString=<...>
     */
    private static String choiceFacts(PDChoice ch) {
        boolean combo = ch instanceof PDComboBox;
        boolean multi = ch instanceof PDListBox && ((PDListBox) ch).isMultiSelect();
        List<String> exportValues = ch.getOptionsExportValues();
        List<String> displayValues = ch.getOptionsDisplayValues();
        List<String> value = ch.getValue();
        List<Integer> indices = ch.getSelectedOptionsIndex();
        return "export=" + joinStr(exportValues)
                + "\tdisplay=" + joinStr(displayValues)
                + "\tvalue=" + joinStr(value)
                + "\tindices=" + joinInt(indices)
                + "\tmulti=" + (multi ? "1" : "0")
                + "\tcombo=" + (combo ? "1" : "0")
                + "\tvalueAsString=" + esc(ch.getValueAsString());
    }

    /**
     * Radio facts:
     *   onValues=<o1|o2|...>\tvalue=<v>\texportValues=<e1|...>
     *   \tselectedIndex=<n>\twidgetAS=<as0|as1|...>
     */
    private static String radioFacts(PDRadioButton rb) {
        java.util.Set<String> onValues = rb.getOnValues();
        List<String> exportValues = rb.getExportValues();
        List<String> as = new ArrayList<>();
        for (PDAnnotationWidget w : rb.getWidgets()) {
            COSName asName = (COSName) w.getCOSObject()
                    .getDictionaryObject(COSName.AS);
            as.add(asName == null ? "<none>" : asName.getName());
        }
        return "onValues=" + joinStr(sorted(onValues))
                + "\tvalue=" + esc(rb.getValue())
                + "\texportValues=" + joinStr(exportValues)
                + "\tselectedIndex=" + rb.getSelectedIndex()
                + "\twidgetAS=" + joinStr(as);
    }

    /**
     * Checkbox facts:
     *   onValue=<on>\tvalue=<v>\tchecked=<0/1>\twidgetAS=<as0|...>
     */
    private static String checkboxFacts(PDCheckBox cb) {
        List<String> as = new ArrayList<>();
        for (PDAnnotationWidget w : cb.getWidgets()) {
            COSName asName = (COSName) w.getCOSObject()
                    .getDictionaryObject(COSName.AS);
            as.add(asName == null ? "<none>" : asName.getName());
        }
        return "onValue=" + esc(cb.getOnValue())
                + "\tvalue=" + esc(cb.getValue())
                + "\tchecked=" + (cb.isChecked() ? "1" : "0")
                + "\twidgetAS=" + joinStr(as);
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

    private static String joinInt(List<Integer> list) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < list.size(); i++) {
            if (i > 0) {
                sb.append('|');
            }
            sb.append(list.get(i));
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
