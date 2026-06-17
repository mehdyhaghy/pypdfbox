import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;

/**
 * Live oracle probe: emit the observable effect of the no-arg
 * {@code getAcroForm()} (which applies {@code AcroFormDefaultFixup}) on a
 * PDF, contrasting it against the unfixed {@code getAcroForm(null)} form.
 *
 * The probe loads the same document twice (fresh load each time so caching
 * state does not leak) and dumps the post-access /DA, /DR fonts and field
 * tree counts for each variant. Output is tab-separated key/value lines.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> AcroFormDefaultFixupProbe input.pdf
 *
 * Output (UTF-8, LF-terminated):
 *   NULL_DA\t<getAcroForm(null) default appearance>
 *   NULL_DRFONTS\t<sorted /DR font names, "" when none>
 *   NULL_FIELDS\t<top-level field count>
 *   FIXUP_DA\t<no-arg getAcroForm() default appearance>
 *   FIXUP_DRFONTS\t<sorted /DR font names>
 *   FIXUP_FIELDS\t<top-level field count>
 */
public final class AcroFormDefaultFixupProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();

        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDAcroForm form = catalog.getAcroForm(null);
            if (form == null) {
                sb.append("NULL_FORMPRESENT\tfalse\n");
            } else {
                sb.append("NULL_FORMPRESENT\ttrue\n");
                sb.append("NULL_DA\t").append(esc(form.getDefaultAppearance())).append('\n');
                sb.append("NULL_DRFONTS\t").append(drFonts(form)).append('\n');
                sb.append("NULL_FIELDS\t").append(form.getFields().size()).append('\n');
            }
        }

        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDAcroForm form = catalog.getAcroForm();
            if (form == null) {
                sb.append("FIXUP_FORMPRESENT\tfalse\n");
            } else {
                sb.append("FIXUP_FORMPRESENT\ttrue\n");
                sb.append("FIXUP_DA\t").append(esc(form.getDefaultAppearance())).append('\n');
                sb.append("FIXUP_DRFONTS\t").append(drFonts(form)).append('\n');
                sb.append("FIXUP_FIELDS\t").append(form.getFields().size()).append('\n');
                int treeCount = 0;
                for (PDField ignored : form.getFieldTree()) {
                    treeCount++;
                }
                sb.append("FIXUP_FIELDTREE\t").append(treeCount).append('\n');
            }
        }

        out.print(sb);
    }

    private static String drFonts(PDAcroForm form) {
        PDResources dr = form.getDefaultResources();
        if (dr == null) {
            return "";
        }
        java.util.List<String> names = new java.util.ArrayList<>();
        for (COSName fontName : dr.getFontNames()) {
            names.add(fontName.getName());
        }
        java.util.Collections.sort(names);
        return String.join(",", names);
    }

    private static String esc(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
