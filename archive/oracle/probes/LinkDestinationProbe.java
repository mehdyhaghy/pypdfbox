import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.action.PDAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionGoTo;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDNamedDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitHeightDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageFitWidthDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageXYZDestination;

/**
 * Live oracle probe for LINK ANNOTATION destination resolution.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> LinkDestinationProbe input.pdf
 *
 * For every link annotation on every page, emit ONE canonical, single-line
 * record describing how the link's target resolves, in fixed document order
 * (page index, then /Annots order skipping non-link annotations):
 *
 *   page<p>.link<i>\t<source>\t<resolved>
 *
 * source = which slot carries the target:
 *   - "dest"   : the link's /Dest entry (PDAnnotationLink.getDestination()).
 *   - "action" : the link's /A /GoTo action (getAction() is a PDActionGoTo).
 *   - "none"   : neither slot resolves to a destination/GoTo action.
 *
 * resolved = the canonical destination signal:
 *   - explicit page destinations:
 *       "page<idx>:<fit>" plus any fit coordinates, e.g.
 *         "page2:XYZ:left=100,top=700,zoom=2"
 *         "page1:Fit"
 *         "page0:FitH:top=500"
 *         "page3:FitV:left=20"
 *     idx is retrievePageNumber() (0-based). Coordinates are canon-formatted
 *     floats; an unset XYZ slot (PDFBox -1 sentinel) is emitted as "null".
 *   - named destination (a string/name /Dest, or a /A /GoTo whose /D is a
 *     name) resolved through catalog.findNamedDestinationPage:
 *         "named:<name>->page<idx>:<fit>..."  when it resolves, or
 *         "named:<name>->unresolved"          when the name is not registered.
 *   - "none" when there is no destination.
 */
public final class LinkDestinationProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            StringBuilder sb = new StringBuilder();
            int p = 0;
            for (PDPage page : doc.getPages()) {
                int linkIndex = 0;
                for (PDAnnotation annot : page.getAnnotations()) {
                    if (!(annot instanceof PDAnnotationLink)) {
                        continue;
                    }
                    PDAnnotationLink link = (PDAnnotationLink) annot;
                    String source;
                    String resolved;
                    PDDestination dest = link.getDestination();
                    if (dest != null) {
                        source = "dest";
                        resolved = resolve(catalog, dest);
                    } else {
                        PDAction action = link.getAction();
                        if (action instanceof PDActionGoTo) {
                            source = "action";
                            resolved = resolve(catalog,
                                    ((PDActionGoTo) action).getDestination());
                        } else {
                            source = "none";
                            resolved = "none";
                        }
                    }
                    sb.append("page").append(p).append(".link").append(linkIndex)
                      .append('\t').append(source)
                      .append('\t').append(resolved).append('\n');
                    linkIndex++;
                }
                p++;
            }
            out.print(sb);
        }
    }

    /** Resolve a destination (explicit or named) to the canonical signal. */
    private static String resolve(PDDocumentCatalog catalog, PDDestination dest)
            throws Exception {
        if (dest == null) {
            return "none";
        }
        if (dest instanceof PDNamedDestination) {
            String name = ((PDNamedDestination) dest).getNamedDestination();
            PDPageDestination pageDest =
                    catalog.findNamedDestinationPage((PDNamedDestination) dest);
            if (pageDest == null) {
                return "named:" + nullToEmpty(name) + "->unresolved";
            }
            return "named:" + nullToEmpty(name) + "->" + pageSignal(pageDest);
        }
        if (dest instanceof PDPageDestination) {
            return pageSignal((PDPageDestination) dest);
        }
        return "none";
    }

    /** "page<idx>:<fit>[:coords]" for an explicit page destination. */
    private static String pageSignal(PDPageDestination dest) {
        StringBuilder sb = new StringBuilder();
        sb.append("page").append(dest.retrievePageNumber());
        if (dest instanceof PDPageXYZDestination) {
            PDPageXYZDestination d = (PDPageXYZDestination) dest;
            sb.append(":XYZ:left=").append(coord(d.getLeft()))
              .append(",top=").append(coord(d.getTop()))
              .append(",zoom=").append(coord(d.getZoom()));
        } else if (dest instanceof PDPageFitWidthDestination) {
            // TYPE "FitH": fit page width, /FitH carries a top coordinate.
            PDPageFitWidthDestination d = (PDPageFitWidthDestination) dest;
            sb.append(":FitH:top=").append(coord(d.getTop()));
        } else if (dest instanceof PDPageFitHeightDestination) {
            // TYPE "FitV": fit page height, /FitV carries a left coordinate.
            PDPageFitHeightDestination d = (PDPageFitHeightDestination) dest;
            sb.append(":FitV:left=").append(coord(d.getLeft()));
        } else if (dest instanceof PDPageFitDestination) {
            sb.append(":Fit");
        } else {
            sb.append(':').append(dest.getClass().getSimpleName());
        }
        return sb.toString();
    }

    /**
     * Canonical coordinate rendering. PDFBox's getLeft()/getTop()/getZoom()
     * return the int sentinel -1 when the slot is unset; emit "null" for it so
     * the signal matches pypdfbox's None-returning accessors.
     */
    private static String coord(float v) {
        if (v == -1f) {
            return "null";
        }
        return canonFloat(v);
    }

    private static String canonFloat(float v) {
        String s = String.format(java.util.Locale.ROOT, "%.3f", v);
        if (s.contains(".")) {
            s = s.replaceAll("0+$", "").replaceAll("\\.$", "");
        }
        if (s.equals("-0")) {
            s = "0";
        }
        return s;
    }

    private static String nullToEmpty(String s) {
        return s == null ? "" : s;
    }
}
