import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.multipdf.PDFMergerUtility;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;

/**
 * Live oracle probe focused narrowly on PDFBox's legacy AcroForm field merge
 * when source documents carry COLLIDING field names.
 *
 * It merges N source PDFs through {@link PDFMergerUtility#mergeDocuments} (the
 * default legacy-mode merge), saves, reloads, and emits the merged AcroForm's
 * fully-qualified field-name list (sorted) plus the count. PDFBox's legacy
 * merge renames a source field whose FQ name already exists in the destination
 * form to {@code dummyFieldNameN}; the destination name set is snapshotted once
 * up front, BEFORE any source field is appended, so two same-named fields that
 * arrive together from one source and do NOT collide with the destination are
 * both kept verbatim (a within-result duplicate). This probe lets the pypdfbox
 * side be compared against that exact behaviour.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> MergeFormFieldsProbe out.pdf in1.pdf ...
 *
 * Args:
 *   args[0]      = output path for the merged document.
 *   args[1..n-1] = the source PDFs to merge, in order.
 *
 * Output (UTF-8, LF-terminated lines):
 *   fields <count>
 *   field <fullyQualifiedName>      (one line per AcroForm field, sorted)
 */
public final class MergeFormFieldsProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File output = new File(args[0]);

        PDFMergerUtility merger = new PDFMergerUtility();
        for (int i = 1; i < args.length; i++) {
            merger.addSource(new File(args[i]));
        }
        merger.setDestinationFileName(output.getAbsolutePath());
        merger.mergeDocuments(null);

        try (PDDocument merged = Loader.loadPDF(output)) {
            PDDocumentCatalog catalog = merged.getDocumentCatalog();
            List<String> fieldNames = new ArrayList<>();
            PDAcroForm form = catalog.getAcroForm(null);
            if (form != null) {
                for (PDField field : form.getFieldTree()) {
                    String fqn = field.getFullyQualifiedName();
                    fieldNames.add(fqn == null ? "<null>" : fqn);
                }
            }
            Collections.sort(fieldNames);
            StringBuilder sb = new StringBuilder();
            sb.append("fields ").append(fieldNames.size()).append('\n');
            for (String n : fieldNames) {
                sb.append("field ").append(n).append('\n');
            }
            out.print(sb);
        }
    }
}
