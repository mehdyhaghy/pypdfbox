import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDTerminalField;
import org.apache.pdfbox.pdmodel.interactive.form.PDTextField;
import org.apache.pdfbox.pdmodel.interactive.form.PDChoice;

/**
 * Live oracle probe for the AcroForm field QUALIFIED-NAME + VALUE/DEFAULT
 * surface, as Apache PDFBox 3.0.7 reports it.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> FieldQualifiedValueProbe input.pdf
 *
 * This complements FieldProbe (sorted fqName/type/value/dv listing) and
 * FieldTreeProbe (hierarchy + DA/Ff/terminal + AcroForm attrs) and the
 * FieldFlagsProbe by isolating the PDField NAMING + VALUE-resolution surface:
 *
 *   - getPartialName()           the local /T
 *   - getFullyQualifiedName()    the dotted /Parent-/T chain
 *   - getParent()'s FQN          parent linkage ("<root>" when no parent)
 *   - getValueAsString()         typed /V render (text -> string, choice ->
 *                                Arrays.toString, non-terminal -> toString)
 *   - getDefaultValue()          the typed /DV render (text -> String, choice
 *                                -> List.toString); rendered to a single
 *                                canonical string here
 *   - getFieldType()             inherited /FT (Tx/Btn/Ch/Sig) or "?"
 *
 * The fixture (built by pypdfbox) is a nested field tree: a non-terminal
 * parent carrying /FT /Tx + /V + /DV, with two terminal text-field children
 * that OMIT /FT, /V and /DV so each child must INHERIT type, value and default
 * from the parent (PDF 32000-1 §12.7.4). A top-level choice field carries its
 * own /V + /DV. So the probe exercises both inheritance and own-value paths.
 *
 * Output (UTF-8, LF-terminated). One line per field in getFieldTree(), sorted
 * by fully-qualified name so order is tree-walk-independent:
 *
 *   <fqName>\t<partialName>\t<parentFqn>\t<fieldType>\t<valueAsString>\t<defaultValue>
 *
 * Tabs / newlines inside any value are escaped so each record stays one line.
 * When the document has no AcroForm the output is empty.
 */
public final class FieldQualifiedValueProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            // null fixup: report the AcroForm exactly as parsed, with no
            // AcroFormDefaultFixup. pypdfbox performs no such fixup on load.
            PDAcroForm form = catalog.getAcroForm(null);
            StringBuilder sb = new StringBuilder();
            if (form != null) {
                List<String> lines = new ArrayList<>();
                for (PDField field : form.getFieldTree()) {
                    lines.add(line(field));
                }
                Collections.sort(lines);
                for (String l : lines) {
                    sb.append(l).append('\n');
                }
            }
            out.print(sb);
        }
    }

    private static String line(PDField field) {
        String fqn = field.getFullyQualifiedName();
        if (fqn == null || fqn.isEmpty()) {
            fqn = "<empty>";
        }
        String partial = field.getPartialName();
        if (partial == null) {
            partial = "<null>";
        }
        PDField parent = field.getParent();
        String parentFqn = (parent == null) ? "<root>" : parent.getFullyQualifiedName();
        if (parentFqn == null || parentFqn.isEmpty()) {
            parentFqn = "<empty>";
        }
        String type = field.getFieldType();
        if (type == null) {
            type = "?";
        }
        String value = esc(field.getValueAsString());
        String dv = defaultValue(field);
        return fqn + "\t" + esc(partial) + "\t" + esc(parentFqn) + "\t" + type
                + "\t" + value + "\t" + dv;
    }

    /** Canonical render of the typed getDefaultValue() across field kinds.
     * PDTextField.getDefaultValue() returns a String; PDChoice.getDefaultValue()
     * returns a List<String> (rendered with List.toString, i.e. "[a, b]"). For
     * any other field kind we read the inheritable /DV off the COS dictionary
     * and emit "present"/"none". This mirrors getValueAsString's typed dispatch
     * but for the /DV side, which has no uniform getValueAsString analogue. */
    private static String defaultValue(PDField field) {
        if (field instanceof PDTextField) {
            return esc(((PDTextField) field).getDefaultValue());
        }
        if (field instanceof PDChoice) {
            return esc(((PDChoice) field).getDefaultValue().toString());
        }
        // Non-text/choice terminal or non-terminal: read inherited /DV raw.
        org.apache.pdfbox.cos.COSBase dv = inheritable(field, COSName.DV);
        if (dv == null) {
            return "none";
        }
        return "present";
    }

    private static org.apache.pdfbox.cos.COSBase inheritable(PDField field, COSName key) {
        PDField current = field;
        while (current != null) {
            org.apache.pdfbox.cos.COSBase item =
                    current.getCOSObject().getDictionaryObject(key);
            if (item != null) {
                return item;
            }
            current = current.getParent();
        }
        return field.getAcroForm().getCOSObject().getDictionaryObject(key);
    }

    private static String esc(String s) {
        if (s == null) {
            return "none";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
