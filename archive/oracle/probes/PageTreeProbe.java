import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageTree;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe: emit Apache PDFBox's page-tree traversal so the pypdfbox
 * PDPageTree port can be compared field-for-field.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> PageTreeProbe in.pdf
 *   java -cp <pdfbox-app.jar>:<build> PageTreeProbe in.pdf remove <N> out.pdf
 *   java -cp <pdfbox-app.jar>:<build> PageTreeProbe in.pdf insert <N> out.pdf
 *
 * Default mode loads the PDF and dumps the canonical traversal:
 *   line 1: "count <getNumberOfPages>"
 *   then one line per page index i (in /Kids document-traversal order):
 *     "page <i> idx <indexOf> media <llx> <lly> <urx> <ury> fonts <n>"
 * where idx is PDPageTree.indexOf(page) — proving the iteration order and the
 * index lookup agree — and media/fonts are the inheritable-attribute-resolved
 * MediaBox and the resolved /Font resource count (exercises inheritance from
 * intermediate /Pages nodes).
 *
 * Mutation modes load the PDF, remove the page at index N (removePage) or
 * insert a fresh Letter page after index N (add when N is the last index,
 * else insertAfter the page at N), save to out.pdf, reload it, and emit the
 * same canonical traversal of the *reloaded* document — so the test asserts
 * the post-save/reload tree shape matches.
 */
public final class PageTreeProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File in = new File(args[0]);
        if (args.length == 1) {
            try (PDDocument doc = Loader.loadPDF(in)) {
                out.print(traversal(doc));
            }
            return;
        }
        String op = args[1];
        int n = Integer.parseInt(args[2]);
        File outFile = new File(args[3]);
        try (PDDocument doc = Loader.loadPDF(in)) {
            if ("remove".equals(op)) {
                doc.removePage(n);
            } else if ("insert".equals(op)) {
                PDPage fresh = new PDPage(PDRectangle.A4);
                PDPageTree tree = doc.getPages();
                if (n >= tree.getCount() - 1) {
                    doc.addPage(fresh);
                } else {
                    tree.insertAfter(fresh, doc.getPage(n));
                }
            } else {
                throw new IllegalArgumentException("unknown op: " + op);
            }
            doc.save(outFile);
        }
        try (PDDocument reloaded = Loader.loadPDF(outFile)) {
            out.print(traversal(reloaded));
        }
    }

    private static String traversal(PDDocument doc) {
        StringBuilder sb = new StringBuilder();
        int count = doc.getNumberOfPages();
        sb.append("count ").append(count).append('\n');
        PDPageTree tree = doc.getPages();
        int i = 0;
        for (PDPage page : tree) {
            int idx = tree.indexOf(page);
            PDRectangle media = page.getMediaBox();
            int fonts = 0;
            PDResources res = page.getResources();
            if (res != null) {
                for (COSName name : res.getFontNames()) {
                    fonts++;
                }
            }
            sb.append("page ").append(i)
              .append(" idx ").append(idx)
              .append(" media ").append(box(media))
              .append(" fonts ").append(fonts)
              .append('\n');
            i++;
        }
        return sb.toString();
    }

    private static String box(PDRectangle r) {
        return fmt(r.getLowerLeftX()) + " " + fmt(r.getLowerLeftY()) + " "
             + fmt(r.getUpperRightX()) + " " + fmt(r.getUpperRightY());
    }

    private static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Long.toString((long) v);
        }
        String s = String.format(Locale.ROOT, "%.4f", v);
        int end = s.length();
        while (end > 0 && s.charAt(end - 1) == '0') {
            end--;
        }
        if (end > 0 && s.charAt(end - 1) == '.') {
            end--;
        }
        return s.substring(0, end);
    }
}
