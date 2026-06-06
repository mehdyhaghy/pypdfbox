import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.multipdf.PDFMergerUtility;
import org.apache.pdfbox.pdmodel.PDDestinationNameTreeNode;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDocumentNameDictionary;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDDocumentOutline;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem;

/**
 * Live oracle probe: merge N source PDFs that each carry named destinations
 * (/Names /Dests name tree) and outline bookmarks whose destinations point at
 * their own pages, then RESOLVE each merged named-destination and each merged
 * outline item back to a 0-based page INDEX in the merged document.
 *
 * Where MergeFactsProbe only emits the set of surviving destination NAMES, this
 * probe answers the load-bearing correctness question: after the merge, does
 * "CharlieDest" still land on Charlie's page (which has shifted to a higher
 * index in the concatenated document) rather than dangling at the wrong page or
 * pointing into nothing? A merge that fails to re-resolve the inner page
 * reference through the clone identity table would report the wrong index here.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> MergeDestResolveProbe out.pdf in1.pdf in2.pdf ...
 *
 * Output (UTF-8, LF-terminated, destinations sorted by name then outline items
 * in document order):
 *   pages <totalPageCount>
 *   dest <name> page=<pageIndex|-1>      (named-destination -> merged page idx)
 *   outline <title> page=<pageIndex|-1>  (outline item dest -> merged page idx)
 */
public final class MergeDestResolveProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File output = new File(args[0]);

        PDFMergerUtility merger = new PDFMergerUtility();
        for (int i = 1; i < args.length; i++) {
            merger.addSource(new File(args[i]));
        }
        merger.setDestinationFileName(output.getAbsolutePath());
        merger.mergeDocuments(null);

        try (PDDocument merged = Loader.loadPDF(output)) {
            PDDocumentCatalog catalog = merged.getDocumentCatalog();
            StringBuilder sb = new StringBuilder();
            sb.append("pages ").append(merged.getNumberOfPages()).append('\n');

            PDDocumentNameDictionary names = catalog.getNames();
            if (names != null) {
                PDDestinationNameTreeNode dests = names.getDests();
                if (dests != null) {
                    Map<String, PDPageDestination> map = dests.getNames();
                    if (map != null) {
                        List<String> keys = new ArrayList<>(map.keySet());
                        Collections.sort(keys);
                        for (String k : keys) {
                            sb.append("dest ").append(k).append(" page=")
                                    .append(pageIndex(merged, map.get(k))).append('\n');
                        }
                    }
                }
            }

            PDDocumentOutline outline = catalog.getDocumentOutline();
            if (outline != null) {
                for (PDOutlineItem item : outline.children()) {
                    String title = item.getTitle();
                    int idx = -1;
                    try {
                        if (item.getDestination() instanceof PDPageDestination) {
                            idx = pageIndex(merged, (PDPageDestination) item.getDestination());
                        }
                    } catch (Exception e) {
                        idx = -1;
                    }
                    sb.append("outline ").append(title == null ? "" : title)
                            .append(" page=").append(idx).append('\n');
                }
            }
            out.print(sb);
        }
    }

    private static int pageIndex(PDDocument doc, PDPageDestination dest) {
        if (dest == null) {
            return -1;
        }
        try {
            int explicit = dest.retrievePageNumber();
            if (explicit >= 0) {
                return explicit;
            }
        } catch (Exception e) {
            // fall through to identity scan
        }
        PDPage target = dest.getPage();
        if (target == null) {
            return -1;
        }
        int i = 0;
        for (PDPage p : doc.getPages()) {
            if (p.getCOSObject() == target.getCOSObject()) {
                return i;
            }
            i++;
        }
        return -1;
    }
}
