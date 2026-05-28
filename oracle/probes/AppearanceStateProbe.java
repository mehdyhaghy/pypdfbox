import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDCheckBox;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.pdmodel.interactive.form.PDTerminalField;

/**
 * Live oracle probe for the WIDGET /AS appearance-state COERCION + FALLBACK
 * behaviour on checkbox fields — the high-value cases the wave-1434
 * WidgetApProbe did NOT cover:
 *
 *   * /AS value coercion when the stored name does NOT exist in the
 *     /AP /N sub-dictionary (does PDFBox return the literal stored /AS or
 *     coerce to "Off"?);
 *   * /AS missing entirely (spec default — "Off" for checkboxes);
 *   * PDCheckBox.isChecked() across valid / invalid / absent /AS;
 *   * the resolved on-state stream (PDAppearanceEntry sub-dict lookup
 *     against the stored /AS — null when the key isn't present).
 *
 * READ-ONLY probe: the fixture is built once by pypdfbox and saved, then read
 * by BOTH implementations so the build itself is part of the differential
 * surface. Walks every terminal /Btn checkbox field on the form in /Fields
 * order. Per checkbox emits canonical lines:
 *
 *   FIELD <fqName>
 *   AS <state-name|none>                  // getAppearanceState (literal)
 *   APKEYS <sorted space-joined keys|->   // /AP /N sub-dict keys
 *   RESOLVED <name|none>                  // sub-dict.get(/AS) -> stream key
 *   VALUE <getValue>                      // PDButton.getValue (default "Off")
 *   ONVALUE <name|empty>                  // PDCheckBox.getOnValue
 *   ISCHECKED <0|1>                       // PDCheckBox.isChecked
 *   END
 */
public final class AppearanceStateProbe {
    public static void main(String[] args) throws Exception {
        File file = new File(args[1]);
        // arg[0] is always "read"; fixture is built by pypdfbox.
        read(file);
    }

    private static void read(File file) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(file)) {
            PDDocumentCatalog cat = doc.getDocumentCatalog();
            PDAcroForm form = cat.getAcroForm();
            if (form == null) {
                out.print(sb);
                return;
            }
            for (PDField field : form.getFieldTree()) {
                if (field instanceof PDCheckBox) {
                    emit(sb, (PDCheckBox) field);
                }
            }
        }
        out.print(sb);
    }

    private static void emit(StringBuilder sb, PDCheckBox cb) {
        sb.append("FIELD ").append(cb.getFullyQualifiedName()).append('\n');

        PDAnnotationWidget widget = ((PDTerminalField) cb).getWidgets().get(0);
        COSName asName = widget.getAppearanceState();
        sb.append("AS ").append(asName == null ? "none" : asName.getName()).append('\n');

        // /AP /N sub-dict keys, sorted.
        PDAppearanceDictionary ap = widget.getAppearance();
        PDAppearanceEntry normal = ap == null ? null : ap.getNormalAppearance();
        sb.append("APKEYS ").append(subKeys(normal)).append('\n');

        // RESOLVED — the on-state stream key actually selected for render.
        // PDFBox's flow: PDAnnotation.getNormalAppearanceStream() looks up
        // sub.get(getAppearanceState()) and returns null when the key is
        // missing. We report the key when the lookup returns a non-null
        // stream, "none" otherwise.
        sb.append("RESOLVED ").append(resolvedKey(widget, normal)).append('\n');

        sb.append("VALUE ").append(cb.getValue()).append('\n');
        sb.append("ONVALUE ").append(cb.getOnValue()).append('\n');
        sb.append("ISCHECKED ").append(cb.isChecked() ? "1" : "0").append('\n');
        sb.append("END\n");
    }

    private static String subKeys(PDAppearanceEntry entry) {
        if (entry == null || !entry.isSubDictionary()) {
            return "-";
        }
        List<String> keys = new ArrayList<>();
        for (COSName k : entry.getSubDictionary().keySet()) {
            keys.add(k.getName());
        }
        Collections.sort(keys);
        return keys.isEmpty() ? "-" : String.join(" ", keys);
    }

    private static String resolvedKey(PDAnnotationWidget w, PDAppearanceEntry normal) {
        if (normal == null) {
            return "none";
        }
        if (!normal.isSubDictionary()) {
            // Single-stream — there is no per-state key; "resolved" is
            // simply the single stream when present.
            return normal.getAppearanceStream() == null ? "none" : "-";
        }
        COSName state = w.getAppearanceState();
        if (state == null) {
            return "none";
        }
        PDAppearanceStream stream = normal.getSubDictionary().get(state);
        if (stream == null) {
            return "none";
        }
        return state.getName();
    }
}
