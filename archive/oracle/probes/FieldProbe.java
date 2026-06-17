import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;

/**
 * Live oracle probe: emit a CANONICAL, deterministic listing of every form
 * field in a PDF's AcroForm, as Apache PDFBox parses them.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> FieldProbe input.pdf
 *
 * Output (UTF-8, LF-terminated lines): one line per field, sorted by the
 * fully-qualified name so the order is independent of tree-walk order:
 *
 *   <fqName>\t<fieldType>\t<value>\t<defaultValue>
 *
 * Where:
 *   - fqName       = getFullyQualifiedName() (the dotted path)
 *   - fieldType    = getFieldType() (e.g. Tx, Btn, Ch, Sig) or "?" when null
 *   - value        = getValueAsString(), newlines escaped to "\\n" and tabs
 *                    to "\\t" so each record stays single-line
 *   - defaultValue = canonical render of the inheritable /DV entry, same
 *                    escaping; "none" when /DV is absent
 *
 * When the document has no AcroForm the output is empty.
 */
public final class FieldProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDAcroForm form = catalog.getAcroForm();
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
        String name = field.getFullyQualifiedName();
        String type = field.getFieldType();
        if (type == null) {
            type = "?";
        }
        String value = esc(field.getValueAsString());
        String dv = defaultValue(field);
        return name + "\t" + type + "\t" + value + "\t" + dv;
    }

    /** Canonical render of the inheritable /DV entry. We read it straight off
     * the COS dictionary (walking up parents) rather than calling a typed
     * getDefaultValue(), because the latter is not present on PDField in a
     * uniform form across field types. */
    private static String defaultValue(PDField field) {
        COSBase dv = inheritable(field, COSName.DV);
        if (dv == null) {
            return "none";
        }
        if (dv instanceof COSString) {
            return esc(((COSString) dv).getString());
        }
        if (dv instanceof COSName) {
            return esc(((COSName) dv).getName());
        }
        return "present";
    }

    /** Walk the field -> parent chain looking for a key, then fall back to the
     * AcroForm root, mirroring PDField.getInheritableAttribute. */
    private static COSBase inheritable(PDField field, COSName key) {
        PDField current = field;
        while (current != null) {
            COSBase item = current.getCOSObject().getDictionaryObject(key);
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
