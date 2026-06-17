import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDComboBox;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;

/**
 * Live oracle probe for EDITABLE COMBO BOX semantics (wave 1447).
 *
 * Emits canonical, deterministic facts about a combo-box choice field so
 * pypdfbox can be diffed against Apache PDFBox's actual behaviour. The surface
 * is the editable-combo detail PDFBox exposes through:
 *
 *   PDComboBox.isEdit()                  -> /Ff Edit bit (1 << 18)
 *   PDComboBox.isDoNotSpellCheck()       -> /Ff DoNotSpellCheck bit (1 << 22)
 *   PDComboBox.getValue()                -> /V (the selected/typed value(s))
 *   PDChoice.getOptionsExportValues()    -> export half of /Opt
 *   PDChoice.getOptionsDisplayValues()   -> display half of /Opt
 *   PDComboBox.setValue(String)          -> write /V (free text allowed)
 *
 * The high-value differential: an EDITABLE combo box may have setValue set to a
 * CUSTOM string that is NOT present in /Opt (a free-typed value). The
 * export/display "resolution" is resolved here exactly like PDFBox's own
 * PDComboBox.constructAppearances: if the value's export string is found in
 * /Opt, the field displays the paired display value; otherwise (a custom value)
 * it resolves to the value verbatim. PDFBox's PDChoice.setValue(String) does
 * NOT validate the value against /Opt at all (only the List overload does), so
 * a non-editable combo also accepts a String set to a custom value.
 *
 *   READ:  java EditableComboProbe read in.pdf name [name ...]
 *          For each named field emit one LF-terminated line:
 *            <name>\t<facts...>
 *          where the fact columns are k=v pairs (see comboFacts). Multi-valued
 *          columns are joined with '|'.
 *
 *   SET:   java EditableComboProbe set in.pdf out.pdf op [op ...]
 *          Each op is name=<value> -> ((PDComboBox) f).setValue(value)
 *          then doc.save(out.pdf). The SET-then-READ round trip verifies the
 *          /V write and that a custom value survives unchanged.
 */
public final class EditableComboProbe {
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
                String op = args[i];
                int eq = op.indexOf('=');
                String name = op.substring(0, eq);
                String value = op.substring(eq + 1);
                PDComboBox cb = (PDComboBox) form.getField(name);
                cb.setValue(value);
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
                if (!(field instanceof PDComboBox)) {
                    sb.append(name).append("\t<not-combo>\n");
                    continue;
                }
                sb.append(name).append('\t')
                        .append(comboFacts((PDComboBox) field)).append('\n');
            }
            out.print(sb);
        }
    }

    /**
     * Combo facts:
     *   edit=<0/1>\tspell=<0/1>\tvalue=<v1|...>\texport=<e1|...>
     *   \tdisplay=<d1|...>\tresolved=<r>\tinOpt=<0/1>
     *
     * resolved/inOpt resolve the first /V value against the /Opt export half
     * exactly like PDComboBox.constructAppearances: if the value is found in
     * the export list AND there are separate display values (export != display),
     * it resolves to the paired display value (inOpt=1); otherwise it resolves
     * to the value verbatim (inOpt=0 means the value is a custom free-typed
     * value). "Separate display values" is computed inline as !export.equals
     * (display) because the pinned 3.0.7 jar predates the public
     * hasSeparateExportAndDisplayValues accessor.
     */
    private static String comboFacts(PDComboBox cb) {
        boolean edit = cb.isEdit();
        boolean spell = cb.isDoNotSpellCheck();
        List<String> value = cb.getValue();
        List<String> export = cb.getOptionsExportValues();
        List<String> display = cb.getOptionsDisplayValues();

        String resolved;
        boolean inOpt;
        if (value.isEmpty()) {
            resolved = "";
            inOpt = false;
        } else {
            String first = value.get(0);
            int index = export.indexOf(first);
            inOpt = index != -1;
            boolean separate = !export.equals(display);
            if (inOpt && separate && index < display.size()) {
                resolved = display.get(index);
            } else {
                resolved = first;
            }
        }

        return "edit=" + (edit ? "1" : "0")
                + "\tspell=" + (spell ? "1" : "0")
                + "\tvalue=" + joinStr(value)
                + "\texport=" + joinStr(export)
                + "\tdisplay=" + joinStr(display)
                + "\tresolved=" + esc(resolved)
                + "\tinOpt=" + (inOpt ? "1" : "0");
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
                .replace("\t", "\\t").replace("|", "\\u007c").replace(":", "\\u003a");
    }
}
