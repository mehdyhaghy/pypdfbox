import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDDestinationOrAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionGoTo;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDNamedDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitHeightDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitRectangleDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitWidthDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageXYZDestination;

/**
 * Live oracle probe: NAMED-DESTINATION RESOLUTION. Loads a PDF and resolves a
 * battery of named destinations to their explicit page destination via Apache
 * PDFBox, emitting — per named destination — the resolved 0-based page index,
 * the destination's fit-type name, and the type-appropriate coordinates.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> NamedDestProbe input.pdf
 *
 * Resolution surfaces exercised (one line each, LF-terminated, UTF-8):
 *
 *   dests:<name>     legacy catalog /Dests flat dictionary (PDF 1.1), resolved
 *                    via catalog.findNamedDestinationPage(PDNamedDestination).
 *   tree:<name>      modern /Names /Dests name tree (multi-level /Kids+/Limits),
 *                    resolved via catalog.findNamedDestinationPage(...).
 *   link:<idx>       a link annotation's /Dest given as a NAMED string — the
 *                    name is read off the annotation, wrapped in a
 *                    PDNamedDestination, then resolved through the catalog.
 *   action           the catalog /OpenAction GoTo action whose /D is a NAMED
 *                    string — resolved the same way.
 *
 * Each line's payload is "<pageIndex>\t<typeName>\t<coords>". A name that does
 * not resolve prints "<surface>\t-1\tnull\t". Coordinate grammar matches the
 * sibling DestTypeProbe (XYZ -> left,top,zoom; FitH/FitBH -> top; FitV/FitBV ->
 * left; FitR -> left,bottom,right,top; Fit/FitB -> empty).
 */
public final class NamedDestProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            StringBuilder sb = new StringBuilder();

            // Legacy /Dests flat dictionary.
            for (String n : new String[] {"intro"}) {
                sb.append("dests:").append(n).append('\t')
                  .append(resolveNamed(catalog, n)).append('\n');
            }
            // Modern /Names /Dests name tree (multi-level).
            for (String n : new String[] {"chapter1", "chapter2"}) {
                sb.append("tree:").append(n).append('\t')
                  .append(resolveNamed(catalog, n)).append('\n');
            }
            // Link annotation whose /Dest is a named string.
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                List<PDAnnotation> annots = page.getAnnotations();
                for (PDAnnotation a : annots) {
                    if (a instanceof PDAnnotationLink) {
                        PDDestination d = ((PDAnnotationLink) a).getDestination();
                        if (d instanceof PDNamedDestination) {
                            String n = ((PDNamedDestination) d).getNamedDestination();
                            sb.append("link:").append(pageIndex).append('\t')
                              .append(resolveNamed(catalog, n)).append('\n');
                        }
                    }
                }
                pageIndex++;
            }
            // OpenAction GoTo with a named /D.
            PDDestinationOrAction openAction = catalog.getOpenAction();
            if (openAction instanceof PDActionGoTo) {
                PDDestination d = ((PDActionGoTo) openAction).getDestination();
                if (d instanceof PDNamedDestination) {
                    String n = ((PDNamedDestination) d).getNamedDestination();
                    sb.append("action").append('\t')
                      .append(resolveNamed(catalog, n)).append('\n');
                }
            }

            out.print(sb);
        }
    }

    /**
     * Resolve a named destination through the catalog and reduce the resolved
     * page destination to "<pageIndex>\t<typeName>\t<coords>".
     */
    private static String resolveNamed(PDDocumentCatalog catalog, String name)
            throws Exception {
        if (name == null) {
            return "-1\tnull\t";
        }
        PDNamedDestination named = new PDNamedDestination(name);
        PDPageDestination dest = catalog.findNamedDestinationPage(named);
        if (dest == null) {
            return "-1\tnull\t";
        }
        int pageIndex = dest.retrievePageNumber();
        return pageIndex + "\t" + describe(dest);
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
                // Fit / FitB carry no coordinates.
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
