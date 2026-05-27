import java.io.File;
import java.io.PrintStream;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDAttributeObject;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDMarkedContentReference;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDObjectReference;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureElement;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureNode;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureTreeRoot;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.Revisions;
import org.apache.pdfbox.pdmodel.documentinterchange.taggedpdf.PDLayoutAttributeObject;

/**
 * Live oracle probe: dump Apache PDFBox's tagged-PDF structure-element detail.
 *
 * Loads a PDF, fetches PDStructureTreeRoot, and emits:
 *
 *   ROOT\trolemap=<k1,k2,...>\tclassmap=<c1,c2,...>
 *
 * (the sorted key sets of the root /RoleMap and /ClassMap), followed by one
 * canonical multi-field line per structure element (pre-order DFS):
 *
 *   E\t<depth>\ts=<S>\tstd=<resolvedStandardType>\tt=<T>\tlang=<Lang>
 *     \talt=<Alt>\tactual=<ActualText>\tclasses=<c1,c2>
 *     \tattr=<O:sample>\tkids=<kind,kind,...>
 *
 * where:
 *   - s   = raw /S structure type (getStructureType)
 *   - std = role-map-resolved standard type (getStandardStructureType)
 *   - t/lang/alt/actual = getTitle / getLanguage / getAlternateDescription /
 *     getActualText, with "-" for null
 *   - classes = the /C class names from getClassNames(), comma-joined ("-" empty)
 *   - attr = first /A attribute object's owner (getOwner); when it is a Layout
 *     attribute object, append ":SpaceBefore=<value>" as a sample attribute.
 *     "-" when no attribute objects.
 *   - kids = the /K kid kinds in order: "mcid<n>" for an Integer MCID,
 *     "elem" for a PDStructureElement, "mcr<mcid>" for a PDMarkedContentReference,
 *     "objr" for a PDObjectReference, "other" for anything else.
 *
 * Output is UTF-8, one line per record, trailing newline per line.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> StructElemDetailProbe input.pdf
 */
public final class StructElemDetailProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDStructureTreeRoot root = catalog.getStructureTreeRoot();
            if (root == null) {
                return;
            }
            emitRoot(root, out);
            for (Object kid : root.getKids()) {
                if (kid instanceof PDStructureElement) {
                    walk((PDStructureElement) kid, 0, out);
                }
            }
        }
    }

    private static void emitRoot(PDStructureTreeRoot root, PrintStream out) {
        out.print("ROOT\trolemap=");
        out.print(sortedKeys(root.getRoleMap()));
        out.print("\tclassmap=");
        out.print(sortedKeys(root.getClassMap()));
        out.print('\n');
    }

    private static String sortedKeys(Map<String, ?> map) {
        if (map == null || map.isEmpty()) {
            return "-";
        }
        TreeSet<String> keys = new TreeSet<>(map.keySet());
        return String.join(",", keys);
    }

    private static void walk(PDStructureElement elem, int depth, PrintStream out) {
        String s = elem.getStructureType();
        String std = elem.getStandardStructureType();
        if (std == null) {
            std = s;
        }
        StringBuilder sb = new StringBuilder();
        sb.append("E\t").append(depth);
        sb.append("\ts=").append(nv(s));
        sb.append("\tstd=").append(nv(std));
        sb.append("\tt=").append(nv(elem.getTitle()));
        sb.append("\tlang=").append(nv(elem.getLanguage()));
        sb.append("\talt=").append(nv(elem.getAlternateDescription()));
        sb.append("\tactual=").append(nv(elem.getActualText()));
        sb.append("\tclasses=").append(classes(elem));
        sb.append("\tattr=").append(attr(elem));
        sb.append("\tkids=").append(kids(elem));
        out.print(sb.toString());
        out.print('\n');

        List<Object> kidList = elem.getKids();
        if (kidList == null) {
            return;
        }
        for (Object kid : kidList) {
            if (kid instanceof PDStructureElement) {
                walk((PDStructureElement) kid, depth + 1, out);
            }
        }
    }

    private static String nv(String value) {
        return value == null ? "-" : value;
    }

    private static String classes(PDStructureElement elem) {
        Revisions<String> rev = elem.getClassNames();
        if (rev == null || rev.size() == 0) {
            return "-";
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < rev.size(); i++) {
            if (i > 0) {
                sb.append(",");
            }
            sb.append(rev.getObject(i));
        }
        return sb.toString();
    }

    private static String attr(PDStructureElement elem) {
        Revisions<PDAttributeObject> rev = elem.getAttributes();
        if (rev == null || rev.size() == 0) {
            return "-";
        }
        PDAttributeObject ao = rev.getObject(0);
        if (ao == null) {
            return "-";
        }
        String owner = ao.getOwner();
        StringBuilder sb = new StringBuilder();
        sb.append(nv(owner));
        if (ao instanceof PDLayoutAttributeObject) {
            float sbValue = ((PDLayoutAttributeObject) ao).getSpaceBefore();
            sb.append(":SpaceBefore=").append(sbValue);
        }
        return sb.toString();
    }

    private static String kids(PDStructureElement elem) {
        List<Object> kidList = elem.getKids();
        if (kidList == null || kidList.isEmpty()) {
            return "-";
        }
        StringBuilder sb = new StringBuilder();
        boolean first = true;
        for (Object kid : kidList) {
            if (!first) {
                sb.append(",");
            }
            first = false;
            sb.append(kidKind(kid));
        }
        return sb.toString();
    }

    private static String kidKind(Object kid) {
        if (kid instanceof Integer) {
            return "mcid" + kid;
        }
        if (kid instanceof PDStructureElement) {
            return "elem";
        }
        if (kid instanceof PDMarkedContentReference) {
            return "mcr" + ((PDMarkedContentReference) kid).getMCID();
        }
        if (kid instanceof PDObjectReference) {
            return "objr";
        }
        if (kid instanceof PDStructureNode) {
            return "node";
        }
        return "other";
    }
}
