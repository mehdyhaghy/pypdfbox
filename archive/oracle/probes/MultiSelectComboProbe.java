import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDChoice;
import org.apache.pdfbox.pdmodel.interactive.form.PDComboBox;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDListBox;

/**
 * Live oracle probe for the MULTI-SELECT VALUE + EDITABLE COMBO surface
 * (wave 1474).
 *
 * Where ListBoxDetailProbe (wave 1446) and EditableComboProbe (wave 1447)
 * each isolate one field, this probe reads a single document carrying BOTH a
 * multi-select list box (two of four options selected, /V an ARRAY) AND an
 * editable combo whose /V is a free-typed value NOT in /Opt — exercising the
 * choice-field type dispatch and the value surface that distinguishes them:
 *
 *   PDChoice.isMultiSelect()         -> /Ff MultiSelect bit (1 << 21)
 *   PDComboBox.isEdit()              -> /Ff Edit bit (1 << 18)
 *   PDChoice.getValue()              -> /V; a LIST for a multi-select list box
 *                                       (the selected export values), a single
 *                                       element list for the editable combo's
 *                                       free text.
 *   PDChoice.getSelectedOptionsIndex() -> /I (sorted ascending; empty for the
 *                                          editable combo's custom value).
 *   PDListBox.getTopIndex()          -> /TI top (first visible) index.
 *
 * There is NO getSelectedExportValues on PDChoice in 3.0.7; the selected
 * export set is resolved from /I against the /Opt export half (the same
 * resolution ListBoxDetailProbe uses) — this is the high-value diff for the
 * multi-select half. The combo's custom value resolves to itself (inOpt=0)
 * because a free-typed editable value is not in /Opt.
 *
 *   READ:  java MultiSelectComboProbe read in.pdf name [name ...]
 *          For each named field emit one LF-terminated line:
 *            <name>\t<facts...>
 *          where the fact columns are k=v pairs (see facts). Multi-valued
 *          columns are joined with '|'.
 *
 *   SET:   java MultiSelectComboProbe set in.pdf out.pdf op [op ...]
 *          Each op is one of:
 *            name=<v|v|...>   multi value -> ((PDChoice) f).setValue(List)
 *            name=<v>         single value -> ((PDChoice) f).setValue(String)
 *          then doc.save(out.pdf). The SET-then-READ round trip verifies a
 *          multi-select /V (array) + /I (sorted) update and that an editable
 *          combo's custom String survives unchanged with /I cleared.
 */
public final class MultiSelectComboProbe {
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
                PDChoice ch = (PDChoice) form.getField(name);
                if (value.indexOf('|') >= 0) {
                    List<String> vals = new ArrayList<>();
                    for (String v : value.split("\\|", -1)) {
                        vals.add(v);
                    }
                    ch.setValue(vals);
                } else {
                    ch.setValue(value);
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
                if (!(field instanceof PDChoice)) {
                    sb.append(name).append("\t<not-choice>\n");
                    continue;
                }
                sb.append(name).append('\t')
                        .append(facts((PDChoice) field)).append('\n');
            }
            out.print(sb);
        }
    }

    /**
     * Choice facts (one line per field):
     *   kind=<listbox|combo>\tmulti=<0/1>\tedit=<0/1>\ttopIndex=<n>
     *   \tvalue=<v1|...>\tindices=<i1|...>\texport=<e1|...>
     *   \tselExport=<se1|...>\tinOpt=<0/1>
     *
     * kind discriminates the concrete field type (the dispatch under test).
     * edit is "0" for a list box (the Edit flag is combo-only). selExport
     * resolves each /I index against the /Opt export half (an out-of-range
     * index -> "<oob>"). inOpt is 1 when EVERY /V value is found in the export
     * list (a pure in-/Opt selection) and 0 when at least one /V value is a
     * custom free-typed value (the editable-combo case).
     */
    private static String facts(PDChoice ch) {
        boolean multi = ch.isMultiSelect();
        boolean isCombo = ch instanceof PDComboBox;
        boolean edit = isCombo && ((PDComboBox) ch).isEdit();
        int topIndex = (ch instanceof PDListBox) ? ((PDListBox) ch).getTopIndex() : 0;
        List<String> value = ch.getValue();
        List<Integer> indices = ch.getSelectedOptionsIndex();
        List<String> export = ch.getOptionsExportValues();

        List<String> selExport = new ArrayList<>();
        for (Integer idx : indices) {
            int j = idx.intValue();
            selExport.add((j >= 0 && j < export.size()) ? export.get(j) : "<oob>");
        }

        boolean inOpt = !value.isEmpty();
        for (String v : value) {
            if (!export.contains(v)) {
                inOpt = false;
                break;
            }
        }

        return "kind=" + (isCombo ? "combo" : "listbox")
                + "\tmulti=" + (multi ? "1" : "0")
                + "\tedit=" + (edit ? "1" : "0")
                + "\ttopIndex=" + topIndex
                + "\tvalue=" + joinStr(value)
                + "\tindices=" + joinInt(indices)
                + "\texport=" + joinStr(export)
                + "\tselExport=" + joinStr(selExport)
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
                .replace("\t", "\\t").replace("|", "\\u007c").replace(":", "\\u003a");
    }
}
