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
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;

/**
 * Live oracle probe for the AcroForm orphan-widget rebuild + generate
 * appearances arm of {@code AcroFormDefaultFixup} (PDFBOX-4985).
 *
 * Loads the document via the no-arg {@code getAcroForm()} (which applies the
 * full fixup chain: defaults + orphan-widget rebuild + appearance
 * generation when /NeedAppearances is true with empty /Fields) and dumps the
 * observable post-fixup state: the field tree (sorted FQN:SimpleClassName),
 * the /NeedAppearances flag, the sorted /DR font names, and per-page widget
 * /AP presence.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> AcroFormOrphanFixupProbe input.pdf
 *
 * Output (UTF-8, LF-terminated, tab-separated):
 *   FORMPRESENT\t<true|false>
 *   FIELDS\t<top-level field count>
 *   TREE\t<FQN:SimpleClassName,FQN:SimpleClassName,... sorted, "" when none>
 *   NEEDAPPEARANCES\t<true|false>
 *   DRFONTS\t<sorted /DR font names, "" when none>
 *   WIDGETAP\t<count of page widgets carrying a non-null /AP>/<total widgets>
 */
public final class AcroFormOrphanFixupProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();

        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDAcroForm form = catalog.getAcroForm();
            if (form == null) {
                sb.append("FORMPRESENT\tfalse\n");
            } else {
                sb.append("FORMPRESENT\ttrue\n");
                sb.append("FIELDS\t").append(form.getFields().size()).append('\n');

                List<String> tree = new ArrayList<>();
                for (PDField field : form.getFieldTree()) {
                    tree.add(field.getFullyQualifiedName() + ":"
                            + field.getClass().getSimpleName());
                }
                Collections.sort(tree);
                sb.append("TREE\t").append(String.join(",", tree)).append('\n');

                sb.append("NEEDAPPEARANCES\t").append(form.getNeedAppearances())
                        .append('\n');
                sb.append("DRFONTS\t").append(drFonts(form)).append('\n');

                int total = 0;
                int withAp = 0;
                for (PDPage page : doc.getPages()) {
                    for (PDAnnotation annot : page.getAnnotations()) {
                        if (COSName.WIDGET.getName().equals(annot.getSubtype())) {
                            total++;
                            COSBase ap = annot.getCOSObject()
                                    .getDictionaryObject(COSName.AP);
                            if (ap != null) {
                                withAp++;
                            }
                        }
                    }
                }
                sb.append("WIDGETAP\t").append(withAp).append('/').append(total)
                        .append('\n');
            }
        }

        out.print(sb);
    }

    private static String drFonts(PDAcroForm form) {
        PDResources dr = form.getDefaultResources();
        if (dr == null) {
            return "";
        }
        List<String> names = new ArrayList<>();
        for (COSName fontName : dr.getFontNames()) {
            names.add(fontName.getName());
        }
        Collections.sort(names);
        return String.join(",", names);
    }

    private AcroFormOrphanFixupProbe() {
    }
}
