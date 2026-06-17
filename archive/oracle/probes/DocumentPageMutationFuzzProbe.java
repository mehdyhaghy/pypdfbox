import java.io.PrintStream;

import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe: PDDocument-level page-tree MUTATION sequences.
 *
 * Complements PageTreeMutateProbe (which checks the internal /Kids tree shape
 * after a single structural mutation built on a hand-rolled unbalanced tree)
 * by exercising the high-level PDDocument mutation API on a FLAT, freshly
 * created document:
 *
 *   addPage(PDPage)              -- append a new page
 *   removePage(int)              -- remove by 0-based index
 *   removePage(PDPage)           -- remove by reference
 *   importPage(PDPage)           -- deep-clone a page from a 2nd document
 *   getPage(int)                 -- random-access lookup (incl. out of range)
 *   getNumberOfPages()
 *
 * Each page is tagged with a unique integer marker baked into its /MediaBox
 * width so identity + document order survive every mutation. After every op
 * the probe projects, on one line:
 *
 *   <step>: count=<n> count_field=<root/Count> order=[w0,w1,...] err=<NONE|Class>
 *
 * where order is the live document-order page widths (via getPage(i)), and
 * count_field is the root /Pages /Count after the op (the cached count
 * getNumberOfPages relies on). err records the exception class name when the
 * op throws (e.g. getPage out of range).
 *
 * Usage:
 *   java ... DocumentPageMutationFuzzProbe <scenario>
 *
 * Scenarios (args[0]) are self-contained — no fixture, no save/reload; the
 * point is to pin the in-memory mutation semantics (count + order + /Count +
 * exceptions), not the serialized bytes.
 */
public final class DocumentPageMutationFuzzProbe {

    private static PrintStream out;
    private static int step;

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        String scenario = args[0];
        switch (scenario) {
            case "add_to_empty":
                addToEmpty();
                break;
            case "add_n_then_count":
                addNThenCount();
                break;
            case "remove_first":
                removeAt(0);
                break;
            case "remove_last":
                removeLast();
                break;
            case "remove_middle":
                removeAt(2);
                break;
            case "remove_by_ref":
                removeByRef();
                break;
            case "remove_single_page_doc":
                removeSinglePageDoc();
                break;
            case "remove_all_sequential":
                removeAllSequential();
                break;
            case "getpage_out_of_range":
                getPageOutOfRange();
                break;
            case "getpage_negative":
                getPageNegative();
                break;
            case "getpage_after_removal":
                getPageAfterRemoval();
                break;
            case "import_page":
                importPage();
                break;
            case "import_then_mutate_source":
                importThenMutateSource();
                break;
            case "add_page_owned_by_other":
                addPageOwnedByOther();
                break;
            case "remove_then_readd":
                removeThenReadd();
                break;
            case "interleaved":
                interleaved();
                break;
            default:
                throw new IllegalArgumentException("unknown scenario: " + scenario);
        }
    }

    /** Build a flat doc with the given marker widths. */
    private static PDDocument flat(int... widths) {
        PDDocument doc = new PDDocument();
        for (int w : widths) {
            doc.addPage(page(w));
        }
        return doc;
    }

    private static PDPage page(int width) {
        return new PDPage(new PDRectangle(width, 200));
    }

    /** Project the live state of the doc after a labelled step. */
    private static void project(String label, PDDocument doc) {
        project(label, doc, "NONE");
    }

    private static void project(String label, PDDocument doc, String err) {
        StringBuilder order = new StringBuilder("[");
        int n = doc.getNumberOfPages();
        for (int i = 0; i < n; i++) {
            if (i > 0) {
                order.append(",");
            }
            int w = (int) doc.getPage(i).getMediaBox().getWidth();
            order.append(w);
        }
        order.append("]");
        int countField = doc.getPages().getCOSObject().getInt(COSName.COUNT, -999);
        out.println("step" + (step++) + " " + label
                + ": count=" + n
                + " count_field=" + countField
                + " order=" + order
                + " err=" + err);
    }

    private static String exc(Throwable t) {
        return t.getClass().getSimpleName();
    }

    // ---- scenarios ----

    private static void addToEmpty() throws Exception {
        step = 0;
        try (PDDocument doc = new PDDocument()) {
            project("empty", doc);
            doc.addPage(page(10));
            project("add10", doc);
            doc.addPage(page(20));
            project("add20", doc);
        }
    }

    private static void addNThenCount() throws Exception {
        step = 0;
        try (PDDocument doc = new PDDocument()) {
            for (int i = 0; i < 7; i++) {
                doc.addPage(page(100 + i));
            }
            project("after_add7", doc);
        }
    }

    private static void removeAt(int idx) throws Exception {
        step = 0;
        try (PDDocument doc = flat(10, 20, 30, 40, 50)) {
            project("init", doc);
            doc.removePage(idx);
            project("removePage(" + idx + ")", doc);
        }
    }

    private static void removeLast() throws Exception {
        step = 0;
        try (PDDocument doc = flat(10, 20, 30, 40, 50)) {
            project("init", doc);
            int last = doc.getNumberOfPages() - 1;
            doc.removePage(last);
            project("removePage(last)", doc);
        }
    }

    private static void removeByRef() throws Exception {
        step = 0;
        try (PDDocument doc = flat(10, 20, 30, 40, 50)) {
            project("init", doc);
            PDPage mid = doc.getPage(2);
            doc.removePage(mid);
            project("removePage(page@30)", doc);
            // remove the same page object again — already gone.
            String err = "NONE";
            try {
                doc.removePage(mid);
            } catch (Exception e) {
                err = exc(e);
            }
            project("removePage(page@30)_again", doc, err);
        }
    }

    private static void removeSinglePageDoc() throws Exception {
        step = 0;
        try (PDDocument doc = flat(77)) {
            project("init", doc);
            doc.removePage(0);
            project("removePage(0)", doc);
            // remove from the now-empty doc.
            String err = "NONE";
            try {
                doc.removePage(0);
            } catch (Exception e) {
                err = exc(e);
            }
            project("removePage(0)_on_empty", doc, err);
        }
    }

    private static void removeAllSequential() throws Exception {
        step = 0;
        try (PDDocument doc = flat(10, 20, 30)) {
            project("init", doc);
            while (doc.getNumberOfPages() > 0) {
                doc.removePage(0);
                project("removePage(0)", doc);
            }
        }
    }

    private static void getPageOutOfRange() throws Exception {
        step = 0;
        try (PDDocument doc = flat(10, 20, 30)) {
            String err = "NONE";
            try {
                doc.getPage(3);
            } catch (Exception e) {
                err = exc(e);
            }
            project("getPage(3)", doc, err);
            err = "NONE";
            try {
                doc.getPage(99);
            } catch (Exception e) {
                err = exc(e);
            }
            project("getPage(99)", doc, err);
        }
    }

    private static void getPageNegative() throws Exception {
        step = 0;
        try (PDDocument doc = flat(10, 20, 30)) {
            String err = "NONE";
            try {
                doc.getPage(-1);
            } catch (Exception e) {
                err = exc(e);
            }
            project("getPage(-1)", doc, err);
        }
    }

    private static void getPageAfterRemoval() throws Exception {
        step = 0;
        try (PDDocument doc = flat(10, 20, 30)) {
            project("init", doc);
            doc.removePage(2);
            project("removePage(2)", doc);
            String err = "NONE";
            try {
                doc.getPage(2);
            } catch (Exception e) {
                err = exc(e);
            }
            project("getPage(2)_after_removal", doc, err);
        }
    }

    private static void importPage() throws Exception {
        step = 0;
        try (PDDocument dst = flat(10, 20);
                PDDocument src = flat(900)) {
            project("dst_init", dst);
            PDPage srcPage = src.getPage(0);
            PDPage imported = dst.importPage(srcPage);
            project("after_import", dst);
            // The imported page object must be independent of the source's.
            boolean independent = imported.getCOSObject() != srcPage.getCOSObject();
            out.println("step" + (step++) + " imported_independent: " + independent);
            // Source doc is unchanged.
            project("src_after_import", src);
        }
    }

    private static void importThenMutateSource() throws Exception {
        step = 0;
        try (PDDocument dst = flat(10);
                PDDocument src = flat(900)) {
            PDPage imported = dst.importPage(src.getPage(0));
            // Mutate the source page's MediaBox; the deep clone must NOT follow.
            src.getPage(0).setMediaBox(new PDRectangle(111, 200));
            int importedWidth = (int) imported.getMediaBox().getWidth();
            out.println("step" + (step++) + " imported_width_after_src_mutate: " + importedWidth);
            project("dst", dst);
        }
    }

    private static void addPageOwnedByOther() throws Exception {
        step = 0;
        // addPage of a PDPage whose dict already has a /Parent from another doc.
        try (PDDocument dst = flat(10, 20);
                PDDocument src = flat(900)) {
            PDPage srcPage = src.getPage(0);
            project("dst_init", dst);
            dst.addPage(srcPage);
            project("dst_after_add_foreign", dst);
            // After re-parenting, where does the foreign page's /Parent point?
            boolean reparented =
                srcPage.getCOSObject().getDictionaryObject(COSName.PARENT)
                    == dst.getPages().getCOSObject();
            out.println("step" + (step++) + " foreign_reparented_to_dst: " + reparented);
            // Does the source doc still see its page?
            project("src_after_add_foreign", src);
        }
    }

    private static void removeThenReadd() throws Exception {
        step = 0;
        try (PDDocument doc = flat(10, 20, 30)) {
            project("init", doc);
            PDPage p = doc.getPage(1);
            doc.removePage(p);
            project("removePage(page@20)", doc);
            doc.addPage(p);
            project("addPage(page@20)_back", doc);
        }
    }

    private static void interleaved() throws Exception {
        step = 0;
        try (PDDocument doc = new PDDocument()) {
            project("empty", doc);
            doc.addPage(page(1));
            doc.addPage(page(2));
            doc.addPage(page(3));
            project("add_1_2_3", doc);
            doc.removePage(1);
            project("removePage(1)", doc);
            doc.addPage(page(4));
            project("addPage(4)", doc);
            doc.removePage(0);
            project("removePage(0)", doc);
            doc.removePage(doc.getNumberOfPages() - 1);
            project("removePage(last)", doc);
        }
    }
}
