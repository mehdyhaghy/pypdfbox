import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.multipdf.Splitter;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe focused on PDFBox's {@link Splitter} *partition shape* at a
 * split-at-page interval, including the boundary intervals the sibling
 * SplitProbe / SplitContentProbe do not pin: interval 1 (one part per page),
 * interval N (ceil(pages/N) parts), and interval > pageCount (exactly one part
 * carrying every page).
 *
 * Unlike SplitProbe (page counts only) and SplitContentProbe (full per-page
 * text), this probe emits the partition AND the *first page's* text of each
 * part — a compact comparable signal that catches a mis-ordered partition (a
 * part whose first page is the wrong source page) without depending on the
 * text module's full per-page spacing heuristics.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> SplitterProbe in.pdf <splitAtPage>
 *
 * Args:
 *   args[0] = input PDF to split.
 *   args[1] = the splitAtPage value passed to Splitter.setSplitAtPage.
 *
 * Output (UTF-8): a single JSON object of the form
 *   {"parts":[{"pages":N,"first":"firstPageText"}, ...]}
 * "first" is "" for a (degenerate) zero-page part.
 */
public final class SplitterProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int splitAt = Integer.parseInt(args[1]);

        try (PDDocument source = Loader.loadPDF(new File(args[0]))) {
            Splitter splitter = new Splitter();
            splitter.setSplitAtPage(splitAt);
            List<PDDocument> parts = splitter.split(source);

            StringBuilder sb = new StringBuilder();
            sb.append("{\"parts\":[");
            try {
                for (int i = 0; i < parts.size(); i++) {
                    PDDocument part = parts.get(i);
                    if (i > 0) {
                        sb.append(',');
                    }
                    int pageCount = part.getNumberOfPages();
                    sb.append("{\"pages\":").append(pageCount).append(",\"first\":");
                    String first = "";
                    if (pageCount > 0) {
                        PDFTextStripper stripper = new PDFTextStripper();
                        stripper.setStartPage(1);
                        stripper.setEndPage(1);
                        first = normalize(stripper.getText(part));
                    }
                    emitString(sb, first);
                    sb.append('}');
                }
            } finally {
                for (PDDocument part : parts) {
                    part.close();
                }
            }
            sb.append("]}");
            out.print(sb);
        }
    }

    /**
     * Remove all whitespace so the comparison captures the Splitter behaviour
     * (the right source page landed first in the right part) without coupling
     * to the text module's inter-word spacing heuristic, which differs between
     * PDFBox's PDFTextStripper and pypdfbox's and is present in unsplit
     * extraction too. See SplitContentProbe for the full rationale.
     */
    private static String normalize(String s) {
        if (s == null) {
            return "";
        }
        return s.replaceAll("\\s+", "");
    }

    private static void emitString(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\b': sb.append("\\b"); break;
                case '\f': sb.append("\\f"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
    }
}
