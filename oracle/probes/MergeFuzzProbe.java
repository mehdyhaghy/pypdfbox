import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.multipdf.PDFMergerUtility;
import org.apache.pdfbox.multipdf.PDFMergerUtility.AcroFormMergeMode;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDestinationNameTreeNode;
import org.apache.pdfbox.pdmodel.PDDocumentNameDictionary;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDDocumentOutline;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;

/**
 * Live oracle probe: differential-fuzz {@link PDFMergerUtility#mergeDocuments}
 * over an arbitrary ordered list of source PDFs and emit a STABLE structural
 * fingerprint of the merged result. Companion to {@code MergeFactsProbe} but
 * broadened so the same binary answers every fuzz scenario the wave-1546 test
 * drives (empty docs, self-merge, N-way page accumulation, two-sided outlines,
 * multi-source dest/field collisions, /OCProperties merge).
 *
 * Bytes are NOT compared — only recoverable structural facts. The source PDFs
 * are produced by pypdfbox so both engines see byte-identical inputs.
 *
 * Usage:
 *   java MergeFuzzProbe <LEGACY|JOIN> out.pdf in1.pdf in2.pdf ...
 *
 * args[0]      = AcroForm merge mode (LEGACY = PDFBOX_LEGACY_MODE,
 *                JOIN = JOIN_FORM_FIELDS_MODE).
 * args[1]      = output path the merged document is written to.
 * args[2..n-1] = the source PDFs to merge, in order (may be repeated for a
 *                self-merge; the list may be empty-page docs).
 *
 * Output (UTF-8, LF-terminated lines):
 *   pages <totalPageCount>
 *   fields <count>
 *   field <fullyQualifiedName>   (one per AcroForm field, sorted)
 *   outline <bookmarkCount>      (total bookmarks across the whole tree)
 *   dests <count>
 *   dest <name>                  (one per /Names /Dests key, sorted)
 *   ocgs <count>                 (length of merged /OCProperties/OCGs, -1 if
 *                                 no /OCProperties)
 */
public final class MergeFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String modeArg = args[0];
        File output = new File(args[1]);

        PDFMergerUtility merger = new PDFMergerUtility();
        if ("JOIN".equals(modeArg)) {
            merger.setAcroFormMergeMode(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE);
        } else {
            merger.setAcroFormMergeMode(AcroFormMergeMode.PDFBOX_LEGACY_MODE);
        }
        for (int i = 2; i < args.length; i++) {
            merger.addSource(new File(args[i]));
        }
        merger.setDestinationFileName(output.getAbsolutePath());
        merger.mergeDocuments(null);

        try (PDDocument merged = Loader.loadPDF(output)) {
            StringBuilder sb = new StringBuilder();
            PDDocumentCatalog catalog = merged.getDocumentCatalog();

            sb.append("pages ").append(merged.getNumberOfPages()).append('\n');

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

            // --- merged /OCProperties OCG count -----------------------
            int ocgCount = -1;
            COSBase ocpBase = catalog.getCOSObject()
                    .getDictionaryObject(COSName.getPDFName("OCProperties"));
            if (ocpBase instanceof COSDictionary) {
                COSArray ocgs = asArray(((COSDictionary) ocpBase)
                        .getDictionaryObject(COSName.getPDFName("OCGs")));
                ocgCount = ocgs == null ? 0 : ocgs.size();
            }
            sb.append("ocgs ").append(ocgCount).append('\n');

            out.print(sb);
        }
    }

    private static COSArray asArray(COSBase b) {
        if (b instanceof COSObject) {
            b = ((COSObject) b).getObject();
        }
        return b instanceof COSArray ? (COSArray) b : null;
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
}
