import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDTerminalField;

/**
 * Live oracle probe for the AcroForm field HIERARCHY + AcroForm-level
 * attribute surface, as Apache PDFBox 3.0.7 parses them.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> FieldTreeProbe input.pdf
 *
 * Output (UTF-8, LF-terminated lines). Two record kinds.
 *
 * One FIELD line per field in the form's getFieldTree(), sorted by the
 * fully-qualified name so order is independent of tree-walk order:
 *
 *   FIELD\t<fqName>\t<fieldType>\t<da>\t<ff>\t<terminal>\t<widgetCount>
 *
 *   - fqName       = getFullyQualifiedName() (the dotted path); "" -> "<empty>"
 *   - fieldType    = getFieldType() (inherited Tx/Btn/Ch/Sig) or "?" when null
 *   - da           = the inherited /DA string (walk self->parent->AcroForm),
 *                    escaped; "none" when absent across the whole chain
 *   - ff           = getFieldFlags() (inherited integer; 0 when absent)
 *   - terminal     = "T" when the field is a PDTerminalField, else "N"
 *   - widgetCount  = getWidgets().size()
 *
 * Then a block of ACROFORM-level lines:
 *
 *   NEEDAPPEARANCES\t<true/false>
 *   CO\t<comma-joined fqNames of getCalcOrder(), in order>   (omitted if empty)
 *   DR\t<comma-joined sorted /DR /Font keys>                 (omitted if empty)
 *   Q\t<getQ()>
 *   FORMDA\t<AcroForm getDefaultAppearance(), escaped>       (omitted if "")
 *   LOOKUP\t<requestedName>\t<resolved fqName | "<null>">    (one per arg[1..])
 *
 * arg[0] is the input PDF; arg[1..] (optional) are fully-qualified names to
 * resolve via getField(name) and emit as LOOKUP lines.
 */
public final class FieldTreeProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            // Pass a null fixup so we read the AcroForm exactly as parsed,
            // without PDFBox's AcroFormDefaultFixup (which would generate
            // missing appearances, clear /NeedAppearances, and inject a ZaDb
            // font into /DR). pypdfbox performs no such fixup on load, so the
            // null-fixup form is the apples-to-apples reference for the field
            // hierarchy + AcroForm-attribute surface under test.
            PDAcroForm form = catalog.getAcroForm(null);
            StringBuilder sb = new StringBuilder();
            if (form != null) {
                List<String> fieldLines = new ArrayList<>();
                for (PDField field : form.getFieldTree()) {
                    fieldLines.add(fieldLine(field));
                }
                Collections.sort(fieldLines);
                for (String l : fieldLines) {
                    sb.append(l).append('\n');
                }

                sb.append("NEEDAPPEARANCES\t").append(form.getNeedAppearances()).append('\n');

                List<PDField> co = form.getCalcOrder();
                if (co != null && !co.isEmpty()) {
                    StringBuilder coNames = new StringBuilder();
                    for (int i = 0; i < co.size(); i++) {
                        if (i > 0) {
                            coNames.append(',');
                        }
                        coNames.append(co.get(i).getFullyQualifiedName());
                    }
                    sb.append("CO\t").append(coNames).append('\n');
                }

                PDResources dr = form.getDefaultResources();
                String drFonts = fontKeys(dr);
                if (!drFonts.isEmpty()) {
                    sb.append("DR\t").append(drFonts).append('\n');
                }

                sb.append("Q\t").append(form.getQ()).append('\n');

                String formDa = form.getDefaultAppearance();
                if (formDa != null && !formDa.isEmpty()) {
                    sb.append("FORMDA\t").append(esc(formDa)).append('\n');
                }

                for (int i = 1; i < args.length; i++) {
                    String name = args[i];
                    PDField resolved = form.getField(name);
                    String fqn = resolved == null ? "<null>" : resolved.getFullyQualifiedName();
                    sb.append("LOOKUP\t").append(name).append('\t').append(fqn).append('\n');
                }
            }
            out.print(sb);
        }
    }

    private static String fieldLine(PDField field) {
        String name = field.getFullyQualifiedName();
        if (name == null || name.isEmpty()) {
            name = "<empty>";
        }
        String type = field.getFieldType();
        if (type == null) {
            type = "?";
        }
        String da = inheritedDA(field);
        int ff = field.getFieldFlags();
        String terminal = (field instanceof PDTerminalField) ? "T" : "N";
        int widgets = field.getWidgets().size();
        return "FIELD\t" + name + "\t" + type + "\t" + da + "\t" + ff + "\t"
                + terminal + "\t" + widgets;
    }

    /** Walk field -> parent chain then the AcroForm root looking for /DA,
     * mirroring PDField.getInheritableAttribute. */
    private static String inheritedDA(PDField field) {
        COSName key = COSName.DA;
        PDField current = field;
        while (current != null) {
            COSBase item = current.getCOSObject().getDictionaryObject(key);
            if (item instanceof COSString) {
                return esc(((COSString) item).getString());
            }
            current = current.getParent();
        }
        COSBase rootItem = field.getAcroForm().getCOSObject().getDictionaryObject(key);
        if (rootItem instanceof COSString) {
            return esc(((COSString) rootItem).getString());
        }
        return "none";
    }

    /** Comma-joined sorted /DR /Font key set, or "" when absent. */
    private static String fontKeys(PDResources dr) {
        if (dr == null) {
            return "";
        }
        COSBase resDict = dr.getCOSObject().getDictionaryObject(COSName.FONT);
        if (!(resDict instanceof COSDictionary)) {
            return "";
        }
        List<String> keys = new ArrayList<>();
        for (COSName k : ((COSDictionary) resDict).keySet()) {
            keys.add(k.getName());
        }
        Collections.sort(keys);
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < keys.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(keys.get(i));
        }
        return sb.toString();
    }

    private static String esc(String s) {
        if (s == null) {
            return "none";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
