import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.multipdf.PDFMergerUtility;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDestinationNameTreeNode;
import org.apache.pdfbox.pdmodel.PDDocumentNameDictionary;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDDocumentOutline;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: merge N source PDFs into one with Apache PDFBox's
 * {@link PDFMergerUtility#mergeDocuments}, save the result, reload it, and emit
 * a deterministic fingerprint of the MERGED interactive structure so the
 * pypdfbox merge can be compared against PDFBox's actual behaviour.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> MergeFactsProbe out.pdf in1.pdf in2.pdf ...
 *
 * Args:
 *   args[0]      = output path the merged document is written to.
 *   args[1..n-1] = the source PDFs to merge, in order.
 *
 * Output (UTF-8, LF-terminated lines):
 *   pages <totalPageCount>
 *   page <i> <escapedExtractedText>      (one line per merged page, 0-based i;
 *                                          PDFTextStripper run over that single
 *                                          page only — escaped so it stays one
 *                                          line: \\, \n, \r, \t)
 *   fields <count>
 *   field <fullyQualifiedName>           (one line per AcroForm field, sorted
 *                                          by FQ name so order is tree-walk
 *                                          independent)
 *   outline <bookmarkCount>              (total bookmarks across the whole tree)
 *   dests <count>
 *   dest <name>                          (one line per /Names /Dests key,
 *                                          sorted)
 *
 * The merge is run with a null memory-usage setting (in-memory), matching the
 * other merge probe and pypdfbox's default merge path.
 */
public final class MergeFactsProbe {

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
            StringBuilder sb = new StringBuilder();

            // --- page count + per-page text (in order) ----------------
            int total = merged.getNumberOfPages();
            sb.append("pages ").append(total).append('\n');
            PDFTextStripper stripper = new PDFTextStripper();
            for (int i = 0; i < total; i++) {
                stripper.setStartPage(i + 1);
                stripper.setEndPage(i + 1);
                String text = stripper.getText(merged).trim();
                sb.append("page ").append(i).append(' ').append(esc(text)).append('\n');
            }

            PDDocumentCatalog catalog = merged.getDocumentCatalog();

            // --- merged AcroForm field FQ names (sorted) --------------
            List<String> fieldNames = new ArrayList<>();
            PDAcroForm form = catalog.getAcroForm(null);
            if (form != null) {
                for (PDField field : form.getFieldTree()) {
                    String fqn = field.getFullyQualifiedName();
                    fieldNames.add(fqn == null ? "<null>" : fqn);
                }
            }
            Collections.sort(fieldNames);
            sb.append("fields ").append(fieldNames.size()).append('\n');
            for (String n : fieldNames) {
                sb.append("field ").append(n).append('\n');
            }

            // --- merged outline bookmark count ------------------------
            int outlineCount = 0;
            PDDocumentOutline outline = catalog.getDocumentOutline();
            if (outline != null) {
                outlineCount = countBookmarks(outline.children());
            }
            sb.append("outline ").append(outlineCount).append('\n');

            // --- merged named destinations (sorted names) -------------
            List<String> destNames = new ArrayList<>();
            PDDocumentNameDictionary names = catalog.getNames();
            if (names != null) {
                PDDestinationNameTreeNode dests = names.getDests();
                if (dests != null) {
                    Map<String, PDPageDestination> map = dests.getNames();
                    if (map != null) {
                        destNames.addAll(map.keySet());
                    }
                }
            }
            Collections.sort(destNames);
            sb.append("dests ").append(destNames.size()).append('\n');
            for (String n : destNames) {
                sb.append("dest ").append(n).append('\n');
            }

            out.print(sb);
        }
    }

    /** Recursively count every bookmark reachable from an iterable of items. */
    private static int countBookmarks(Iterable<PDOutlineItem> items) {
        int count = 0;
        for (PDOutlineItem item : items) {
            count++;
            count += countBookmarks(item.children());
        }
        return count;
    }

    private static String esc(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
