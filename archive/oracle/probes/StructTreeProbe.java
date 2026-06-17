import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureElement;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureNode;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureTreeRoot;

/**
 * Live oracle probe: dump Apache PDFBox's logical-structure tree.
 *
 * Loads a PDF, fetches PDStructureTreeRoot from the catalog, walks the
 * structure-element tree depth-first (pre-order), and emits one canonical line
 * per structure element:
 *
 *   <depth>\t<role>\talt=<0|1>\tactual=<0|1>
 *
 * where role is the element's structure type (/S) resolved through the
 * role-map to its standard structure type, alt is /Alt presence, actual is
 * /ActualText presence. Non-structure-element kids (MCID ints, marked-content
 * references, object references) are skipped — only the element tree shape is
 * dumped. Output is UTF-8, no extra framing.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> StructTreeProbe input.pdf
 */
public final class StructTreeProbe {
    private static final COSName ALT = COSName.getPDFName("Alt");
    private static final COSName ACTUAL_TEXT = COSName.getPDFName("ActualText");

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
        String role = elem.getStandardStructureType();
        if (role == null) {
            role = elem.getStructureType();
        }
        COSDictionary cos = elem.getCOSObject();
        int alt = cos.getDictionaryObject(ALT) != null ? 1 : 0;
        int actual = cos.getDictionaryObject(ACTUAL_TEXT) != null ? 1 : 0;
        out.print(depth);
        out.print('\t');
        out.print(role);
        out.print("\talt=");
        out.print(alt);
        out.print("\tactual=");
        out.print(actual);
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
}
