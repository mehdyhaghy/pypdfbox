import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDChoice;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDListBox;

/**
 * Live oracle probe for LIST-BOX DETAIL semantics (wave 1446).
 *
 * Emits canonical, deterministic facts about a list-box choice field so
 * pypdfbox can be diffed against Apache PDFBox's actual behaviour. The surface
 * is the list-box detail PDFBox exposes through:
 *
 *   PDListBox.getTopIndex()        -> /TI top (first visible) index
 *   PDListBox.setTopIndex(Integer) -> write /TI
 *   PDChoice.getSelectedOptionsIndex()  -> /I, sorted ascending
 *   PDChoice.getOptionsExportValues()   -> export half of /Opt
 *   PDChoice.getOptionsDisplayValues()  -> display half of /Opt
 *   PDChoice.getValue()                 -> /V (the selected export value(s))
 *   PDChoice.isMultiSelect()            -> /Ff MultiSelect bit
 *
 * PDFBox has no getSelectedExportValues/getSelectedDisplayValues on PDChoice;
 * the "selected export vs display" detail is resolved here from /I against the
 * /Opt export and display halves (this resolution is the high-value diff).
 *
 *   READ:  java ListBoxDetailProbe read in.pdf name [name ...]
 *          For each named field emit one LF-terminated line:
 *
 *            <name>\t<facts...>
 *
 *          where the fact columns are k=v pairs (see listBoxFacts). Multi-
 *          valued columns are joined with '|'.
 *
 *   SET:   java ListBoxDetailProbe set in.pdf out.pdf op [op ...]
 *          Each op is one of:
 *            name#ti=<int>       -> ((PDListBox) f).setTopIndex(int)
 *            name=<v|v|...>      -> f.setValue(List)  (multi-select)
 *            name=<v>            -> f.setValue(String)
 *          then doc.save(out.pdf). The SET-then-READ round trip verifies the
 *          /TI write and the /V + /I (sorted) update.
 */
public final class ListBoxDetailProbe {
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
                int hash = op.indexOf('#');
                if (hash >= 0 && op.startsWith("ti=", hash + 1)) {
                    String name = op.substring(0, hash);
                    int ti = Integer.parseInt(op.substring(hash + 4));
                    PDField field = form.getField(name);
                    ((PDListBox) field).setTopIndex(ti);
                    continue;
                }
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
                if (!(field instanceof PDListBox)) {
                    sb.append(name).append("\t<not-listbox>\n");
                    continue;
                }
                sb.append(name).append('\t')
                        .append(listBoxFacts((PDListBox) field)).append('\n');
            }
            out.print(sb);
        }
    }

    /**
     * List-box facts:
     *   topIndex=<n>\tindices=<i1|i2|...>\tvalue=<v1|...>\tmulti=<0/1>
     *   \texport=<e1|...>\tdisplay=<d1|...>
     *   \tselExport=<se1|...>\tselDisplay=<sd1|...>
     *   \tpairs=<e1:d1|e2:d2|...>
     *
     * selExport/selDisplay resolve each /I index against the export and display
     * halves of /Opt — the selected set rendered both ways. An index out of
     * range is reported as "<oob>".
     */
    private static String listBoxFacts(PDListBox lb) {
        int topIndex = lb.getTopIndex();
        List<Integer> indices = lb.getSelectedOptionsIndex();
        List<String> value = lb.getValue();
        boolean multi = lb.isMultiSelect();
        List<String> export = lb.getOptionsExportValues();
        List<String> display = lb.getOptionsDisplayValues();

        List<String> selExport = new ArrayList<>();
        List<String> selDisplay = new ArrayList<>();
        for (Integer idx : indices) {
            int j = idx.intValue();
            selExport.add((j >= 0 && j < export.size()) ? export.get(j) : "<oob>");
            selDisplay.add((j >= 0 && j < display.size()) ? display.get(j) : "<oob>");
        }

        StringBuilder pairs = new StringBuilder();
        int n = Math.min(export.size(), display.size());
        for (int i = 0; i < n; i++) {
            if (i > 0) {
                pairs.append('|');
            }
            pairs.append(esc(export.get(i))).append(':').append(esc(display.get(i)));
        }

        return "topIndex=" + topIndex
                + "\tindices=" + joinInt(indices)
                + "\tvalue=" + joinStr(value)
                + "\tmulti=" + (multi ? "1" : "0")
                + "\texport=" + joinStr(export)
                + "\tdisplay=" + joinStr(display)
                + "\tselExport=" + joinStr(selExport)
                + "\tselDisplay=" + joinStr(selDisplay)
                + "\tpairs=" + pairs;
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
