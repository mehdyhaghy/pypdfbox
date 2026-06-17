import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureElement;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureTreeRoot;

/**
 * Live oracle probe: dump Apache PDFBox's role-map resolution for every
 * structure element in a tagged PDF.
 *
 * Loads a PDF, fetches PDStructureTreeRoot, walks the structure-element tree
 * pre-order (DFS), and emits one canonical line per structure element:
 *
 *   <depth>\ts=<getStructureType>\tstd=<getStandardStructureType>
 *
 * with "-" for a null value. This isolates the /RoleMap resolution surface:
 * upstream getStandardStructureType() performs exactly ONE role-map lookup
 * (PDStructureElement.java) — if /S maps to a String it returns that String,
 * otherwise it returns /S unchanged. It does NOT recurse through a multi-hop
 * role-map chain and does NOT short-circuit on standard structure types. This
 * probe exercises exactly that contract so pypdfbox's resolution can be
 * differentially checked against it.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> RoleMapResolveProbe input.pdf
 */
public final class RoleMapResolveProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDStructureTreeRoot root = catalog.getStructureTreeRoot();
            if (root == null) {
                return;
            }
            for (Object kid : root.getKids()) {
                if (kid instanceof PDStructureElement) {
                    walk((PDStructureElement) kid, 0, out);
                }
            }
        }
    }

    private static void walk(PDStructureElement elem, int depth, PrintStream out) {
        String s = elem.getStructureType();
        String std = elem.getStandardStructureType();
        out.print(depth);
        out.print("\ts=");
        out.print(nv(s));
        out.print("\tstd=");
        out.print(nv(std));
        out.print('\n');
        List<Object> kids = elem.getKids();
        if (kids == null) {
            return;
        }
        for (Object kid : kids) {
            if (kid instanceof PDStructureElement) {
                walk((PDStructureElement) kid, depth + 1, out);
            }
        }
    }

    private static String nv(String value) {
        return value == null ? "-" : value;
    }
}
