import java.io.File;
import java.io.PrintStream;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDocumentNameDictionary;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionJavaScript;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitHeightDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitRectangleDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitWidthDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageXYZDestination;

/**
 * Live oracle probe: DOCUMENT /Names SUB-TREE ENUMERATION on
 * {@code PDDocumentNameDictionary}.
 *
 * Loads a PDF, reaches the catalog {@code /Names} dictionary via
 * {@code catalog.getNames()}, then drives the two value-bearing sub-trees this
 * wave targets:
 *
 *   js:<name>        the {@code /Names /JavaScript} name tree. PDFBox resolves
 *                    each leaf to a {@code PDActionJavaScript}; we emit the
 *                    name and the action's JavaScript body
 *                    ({@code getAction()}).
 *   dest:<name>      the {@code /Names /Dests} name tree. PDFBox resolves each
 *                    leaf to a {@code PDPageDestination}; we emit the name, the
 *                    0-based resolved page index ({@code retrievePageNumber}),
 *                    the fit-type name ({@code /D[1]}) and coordinates.
 *
 * Presence/identity lines pin the wrapper itself:
 *
 *   names:present    "1" when {@code getNames()} is non-null, else "0".
 *   ef:present       "1" when {@code getEmbeddedFiles()} is non-null.
 *   ap:present       "1" when {@code getNames().getCOSObject()} carries /AP.
 *   js:count         number of entries in the resolved /JavaScript map.
 *   dest:count       number of entries in the resolved /Dests map.
 *
 * Output is LF-terminated UTF-8; the maps are emitted in sorted-key order so
 * the two languages compare byte-for-byte. Coordinate grammar matches the
 * sibling DestTypeProbe (XYZ -> left,top,zoom; FitH/FitBH -> top; FitV/FitBV ->
 * left; FitR -> left,bottom,right,top; Fit/FitB -> empty).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> DocNamesSubtreeProbe input.pdf
 */
public final class DocNamesSubtreeProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            StringBuilder sb = new StringBuilder();

            PDDocumentNameDictionary names = catalog.getNames();
            sb.append("names:present\t").append(names != null ? "1" : "0").append('\n');
            if (names == null) {
                out.print(sb);
                return;
            }

            sb.append("ef:present\t")
              .append(names.getEmbeddedFiles() != null ? "1" : "0").append('\n');
            sb.append("ap:present\t")
              .append(names.getCOSObject().containsKey("AP") ? "1" : "0").append('\n');

            // /Names /JavaScript sub-tree.
            Map<String, PDActionJavaScript> js = null;
            if (names.getJavaScript() != null) {
                js = names.getJavaScript().getNames();
            }
            int jsCount = js == null ? 0 : js.size();
            sb.append("js:count\t").append(jsCount).append('\n');
            if (js != null) {
                for (Map.Entry<String, PDActionJavaScript> e
                        : new TreeMap<>(js).entrySet()) {
                    PDActionJavaScript action = e.getValue();
                    String body = action == null ? "null" : action.getAction();
                    if (body == null) {
                        body = "null";
                    }
                    sb.append("js:").append(e.getKey()).append('\t')
                      .append(body).append('\n');
                }
            }

            // /Names /Dests sub-tree.
            Map<String, PDPageDestination> dests = null;
            if (names.getDests() != null) {
                dests = names.getDests().getNames();
            }
            int destCount = dests == null ? 0 : dests.size();
            sb.append("dest:count\t").append(destCount).append('\n');
            if (dests != null) {
                for (Map.Entry<String, PDPageDestination> e
                        : new TreeMap<>(dests).entrySet()) {
                    PDPageDestination dest = e.getValue();
                    sb.append("dest:").append(e.getKey()).append('\t');
                    if (dest == null) {
                        sb.append("-1\tnull\t");
                    } else {
                        sb.append(dest.retrievePageNumber()).append('\t')
                          .append(describe(dest));
                    }
                    sb.append('\n');
                }
            }

            out.print(sb);
        }
    }

    /** Emit "<typeName>\t<coords>" for one resolved page destination. */
    private static String describe(PDPageDestination dest) {
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
            default:
                return "";
        }
    }

    private static String num(int v) {
        return Integer.toString(v);
    }

    private static String num(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Integer.toString((int) v);
        }
        return Float.toString(v);
    }
}
