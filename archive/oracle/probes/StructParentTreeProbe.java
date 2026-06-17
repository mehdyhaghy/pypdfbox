import java.io.File;
import java.io.PrintStream;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.COSObjectable;
import org.apache.pdfbox.pdmodel.common.PDNumberTreeNode;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureElement;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureTreeRoot;

/**
 * Live oracle probe: dump Apache PDFBox's tagged-PDF /ParentTree number-tree
 * mapping that resolves marked-content (MCID) back to structure elements.
 *
 * This is a DISTINCT surface from StructTreeProbe (structure-element tree
 * shape) and StructElemDetailProbe (per-element role/class/attr detail): it
 * exercises the reverse mapping —
 * PDStructureTreeRoot.getParentTreeNextKey() and
 * PDStructureTreeRoot.getParentTree().getNumbers() — plus per-page
 * /StructParents linkage.
 *
 * Loads a PDF, fetches PDStructureTreeRoot, and emits:
 *
 *   NEXTKEY\t<getParentTreeNextKey()>
 *   PAGE\t<pageIndex>\tsp=<StructParents or -1>
 *   ENTRY\t<key>\t<value>
 *
 * where the ENTRY <value> classifies the parent-tree leaf for that integer key
 * (PDF 32000-1 §14.7.4.4):
 *   - "arr[r0,r1,...]" when the value is a COSArray indexed by MCID; each slot
 *     ri is the resolved standard structure type (getStandardStructureType,
 *     falling back to raw getStructureType) of the structure element in that
 *     slot, or "null" for a null/absent slot, or "?" when the slot is not a
 *     structure-element dictionary.
 *   - "elem:<resolvedType>" when the value is a single structure-element
 *     dictionary (used for annotations / XObjects whose whole content maps to
 *     one element).
 *   - "?" for any other shape.
 *
 * ENTRY lines are emitted in ascending key order. Output is UTF-8, one record
 * per line, trailing newline per line.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> StructParentTreeProbe input.pdf
 */
public final class StructParentTreeProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDStructureTreeRoot root = catalog.getStructureTreeRoot();
            if (root == null) {
                return;
            }
            out.print("NEXTKEY\t");
            out.print(root.getParentTreeNextKey());
            out.print('\n');

            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                out.print("PAGE\t");
                out.print(pageIndex);
                out.print("\tsp=");
                out.print(page.getStructParents());
                out.print('\n');
                pageIndex++;
            }

            PDNumberTreeNode parentTree = root.getParentTree();
            if (parentTree == null) {
                return;
            }
            Map<Integer, COSObjectable> numbers = parentTree.getNumbers();
            if (numbers == null) {
                return;
            }
            TreeMap<Integer, COSObjectable> sorted = new TreeMap<>(numbers);
            for (Map.Entry<Integer, COSObjectable> e : sorted.entrySet()) {
                out.print("ENTRY\t");
                out.print(e.getKey());
                out.print('\t');
                out.print(classify(e.getValue()));
                out.print('\n');
            }
        }
    }

    private static String classify(COSObjectable value) {
        if (value == null) {
            return "?";
        }
        COSBase base = unwrap(value.getCOSObject());
        if (base instanceof COSArray) {
            COSArray arr = (COSArray) base;
            StringBuilder sb = new StringBuilder("arr[");
            for (int i = 0; i < arr.size(); i++) {
                if (i > 0) {
                    sb.append(",");
                }
                sb.append(slot(unwrap(arr.getObject(i))));
            }
            sb.append("]");
            return sb.toString();
        }
        if (base instanceof COSDictionary) {
            return "elem:" + resolvedType((COSDictionary) base);
        }
        return "?";
    }

    private static String slot(COSBase base) {
        if (base == null) {
            return "null";
        }
        if (base instanceof COSDictionary) {
            return resolvedType((COSDictionary) base);
        }
        return "?";
    }

    private static String resolvedType(COSDictionary dict) {
        PDStructureElement elem = new PDStructureElement(dict);
        String std = elem.getStandardStructureType();
        if (std != null) {
            return std;
        }
        String raw = elem.getStructureType();
        return raw == null ? "?" : raw;
    }

    private static COSBase unwrap(COSBase base) {
        while (base instanceof COSObject) {
            base = ((COSObject) base).getObject();
        }
        return base;
    }
}
