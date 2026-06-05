import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDNamedDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;

/**
 * Live oracle probe: NAMED-DESTINATION RESOLUTION EDGE CASES. Complements the
 * sibling NamedDestProbe (happy-path resolution surfaces) by pinning the
 * trickier dispatch / precedence / fallthrough behaviours of
 * PDDocumentCatalog.findNamedDestinationPage:
 *
 *   precedence   a name registered in BOTH the modern /Names /Dests name tree
 *                AND the legacy catalog /Dests dict — which wins? Emits the
 *                resolved page index + fit type so the caller can prove the
 *                name tree shadows the legacy dict.
 *   legacyonly   a name that exists ONLY in the legacy /Dests dict (no tree
 *                entry) — proves the fallback path is reached.
 *   dictD        a legacy /Dests entry whose value is a {/D <array>} dict
 *                rather than a bare array — both forms must resolve.
 *   barearray    a legacy /Dests entry whose value is a bare array.
 *   chaintree    a name-tree leaf whose value is itself a named string
 *                (string -> string chain) — PDFBOX-5975: convertCOSToPD
 *                returns null (no recursion). Resolves to -1/null.
 *   chainlegacy  a legacy /Dests entry whose value is a bare COSString
 *                (string -> string chain) — getDestination only accepts
 *                array / dict-with-D, so resolves to -1/null.
 *   missing      a name registered nowhere — resolves to -1/null.
 *
 * One line each, "<label>\t<pageIndex>\t<typeName>\t<coords>", LF-terminated,
 * UTF-8. Coordinate grammar omitted (callers only need page+type here, so
 * coords is left empty for non-coordinate-bearing checks; XYZ/FitH emit their
 * primary coordinate so a regression that swaps fit types is caught).
 */
public final class NamedDestEdgeProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            StringBuilder sb = new StringBuilder();
            for (String n : new String[] {
                    "precedence", "legacyonly", "dictD", "barearray",
                    "chaintree", "chainlegacy", "missing"}) {
                sb.append(n).append('\t').append(resolve(catalog, n)).append('\n');
            }
            out.print(sb);
        }
    }

    private static String resolve(PDDocumentCatalog catalog, String name)
            throws Exception {
        PDNamedDestination named = new PDNamedDestination(name);
        PDPageDestination dest;
        try {
            dest = catalog.findNamedDestinationPage(named);
        } catch (Exception e) {
            return "EXC\t" + e.getClass().getSimpleName() + "\t";
        }
        if (dest == null) {
            return "-1\tnull\t";
        }
        COSBase cos = dest.getCOSObject();
        String typeName = "null";
        String coord = "";
        if (cos instanceof COSArray) {
            String t = ((COSArray) cos).getName(1);
            if (t != null) {
                typeName = t;
            }
        }
        return dest.retrievePageNumber() + "\t" + typeName + "\t" + coord;
    }
}
