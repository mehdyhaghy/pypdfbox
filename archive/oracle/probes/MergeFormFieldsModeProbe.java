import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.multipdf.PDFMergerUtility;
import org.apache.pdfbox.multipdf.PDFMergerUtility.AcroFormMergeMode;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;

/**
 * Live oracle probe: AcroForm field merge under an explicit
 * {@link PDFMergerUtility.AcroFormMergeMode}.
 *
 * Confirms that in PDFBox 3.0.x JOIN_FORM_FIELDS_MODE and PDFBOX_LEGACY_MODE
 * produce identical field-name results (JOIN delegates to LEGACY upstream), so
 * a destination collision is renamed to {@code dummyFieldNameN} under BOTH
 * modes. Reads the same input PDFs that pypdfbox produced so both engines see
 * identical bytes.
 *
 * Usage:
 *   java MergeFormFieldsModeProbe <LEGACY|JOIN> out.pdf in1.pdf in2.pdf ...
 *
 * Output (UTF-8, LF-terminated):
 *   fields <count>
 *   field <fullyQualifiedName>   (one line per AcroForm field, sorted)
 */
public final class MergeFormFieldsModeProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String modeArg = args[0];
        File output = new File(args[1]);

        PDFMergerUtility merger = new PDFMergerUtility();
        if ("JOIN".equals(modeArg)) {
            merger.setAcroFormMergeMode(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE);
        } else {
            merger.setAcroFormMergeMode(AcroFormMergeMode.PDFBOX_LEGACY_MODE);
        }
        for (int i = 2; i < args.length; i++) {
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
