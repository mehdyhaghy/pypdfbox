import java.io.File;
import java.io.PrintStream;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.pdmodel.PDDestinationNameTreeNode;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDocumentNameDictionary;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitHeightDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitRectangleDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitWidthDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageXYZDestination;

/**
 * Live oracle probe: emit a CANONICAL, deterministic listing of every entry in
 * a PDF's catalog /Names /Dests name tree, reduced to its resolved DESTINATION
 * TYPE + COORDINATES, exactly as Apache PDFBox parses it.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> DestTypeProbe input.pdf
 *
 * Output (UTF-8, LF-terminated lines), one line per destination, sorted by the
 * destination's name so the listing is independent of name-tree node layout:
 *
 *   <name>\t<typeName>\t<coords>
 *
 * Where:
 *   - name      = the name-tree key.
 *   - typeName  = the concrete PDF destination type, taken from /D[1] (the
 *                 destination array's type name): XYZ, Fit, FitB, FitH, FitBH,
 *                 FitV, FitBV, FitR. This is the behaviourally-meaningful
 *                 identity; the Java wrapper CLASS that getNames() resolves to
 *                 (e.g. FitH and FitBH both map to PDPageFitWidthDestination)
 *                 is an implementation detail and is NOT what we compare on.
 *   - coords    = the coordinate getters appropriate to the type, read from the
 *                 resolved concrete subclass, comma-joined. Upstream getters
 *                 return the int sentinel -1 (or float -1.0 for XYZ zoom) when a
 *                 slot is null/missing; we print integral values as plain ints.
 *                   XYZ  -> left,top,zoom
 *                   FitH/FitBH -> top
 *                   FitV/FitBV -> left
 *                   FitR -> left,bottom,right,top
 *                   Fit/FitB -> (empty)
 *
 * When the document has no /Names /Dests tree (or it is empty) output is empty.
 */
public final class DestTypeProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            StringBuilder sb = new StringBuilder();
            PDDocumentNameDictionary names = catalog.getNames();
            if (names != null) {
                PDDestinationNameTreeNode dests = names.getDests();
                if (dests != null) {
                    Map<String, PDPageDestination> map = dests.getNames();
                    if (map != null) {
                        // TreeMap → stable name-sorted order.
                        TreeMap<String, PDPageDestination> sorted = new TreeMap<>(map);
                        for (Map.Entry<String, PDPageDestination> e : sorted.entrySet()) {
                            sb.append(e.getKey()).append('\t')
                              .append(describe(e.getValue())).append('\n');
                        }
                    }
                }
            }
            out.print(sb);
        }
    }

    /** Emit "<typeName>\t<coords>" for one resolved page destination. */
    private static String describe(PDPageDestination dest) {
        if (dest == null) {
            return "null\t";
        }
        COSBase cos = dest.getCOSObject();
        String typeName = "null";
        if (cos instanceof COSArray) {
            String n = ((COSArray) cos).getName(1);
            if (n != null) {
                typeName = n;
            }
        }
        return typeName + "\t" + coords(dest, typeName);
    }

    private static String coords(PDPageDestination dest, String typeName) {
        switch (typeName) {
            case "XYZ": {
                PDPageXYZDestination d = (PDPageXYZDestination) dest;
                return num(d.getLeft()) + "," + num(d.getTop()) + "," + num(d.getZoom());
            }
            case "FitH":
            case "FitBH": {
                PDPageFitWidthDestination d = (PDPageFitWidthDestination) dest;
                return num(d.getTop());
            }
            case "FitV":
            case "FitBV": {
                PDPageFitHeightDestination d = (PDPageFitHeightDestination) dest;
                return num(d.getLeft());
            }
            case "FitR": {
                PDPageFitRectangleDestination d = (PDPageFitRectangleDestination) dest;
                return num(d.getLeft()) + "," + num(d.getBottom()) + ","
                     + num(d.getRight()) + "," + num(d.getTop());
            }
            case "Fit":
            case "FitB": {
                // No coordinates; touch the class so a wrong dispatch would ClassCast.
                @SuppressWarnings("unused")
                PDPageFitDestination d = (PDPageFitDestination) dest;
                return "";
            }
            default:
                return "";
        }
    }

    /** Print an int coordinate as a plain integer. */
    private static String num(int v) {
        return Integer.toString(v);
    }

    /** Print a float coordinate as an int when integral, else as-is. */
    private static String num(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Integer.toString((int) v);
        }
        return Float.toString(v);
    }
}
