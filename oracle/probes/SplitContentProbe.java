import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.multipdf.Splitter;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: split a PDF via PDFBox's {@link Splitter} at a fixed
 * split-at-page boundary and emit, per resulting part, the part's page count
 * and the PDFTextStripper text of each page in that part. This lets the
 * pypdfbox side assert not only that the partition (part count + per-part page
 * counts) matches PDFBox, but also that each part's pages preserve their
 * original text content after the split.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> SplitContentProbe in.pdf <splitAtPage>
 *
 * Args:
 *   args[0] = input PDF to split.
 *   args[1] = the splitAtPage value passed to Splitter.setSplitAtPage (every
 *             N pages becomes one part).
 *
 * Output (UTF-8): a single JSON object of the form
 *   {"parts":[{"pages":N,"text":["page0text","page1text",...]}, ...]}
 * Text is extracted per page (start==end==page index within the part) so the
 * Python side compares text page-for-page across the partition.
 */
public final class SplitContentProbe {

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
                    sb.append("{\"pages\":").append(pageCount).append(",\"text\":[");
                    for (int p = 0; p < pageCount; p++) {
                        if (p > 0) {
                            sb.append(',');
                        }
                        PDFTextStripper stripper = new PDFTextStripper();
                        stripper.setStartPage(p + 1);
                        stripper.setEndPage(p + 1);
                        String text = stripper.getText(part);
                        emitString(sb, normalize(text));
                    }
                    sb.append("]}");
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
     * Remove all whitespace (spaces, tabs, CR/LF in any combination) so the
     * comparison captures exactly what this probe is for: that the Splitter
     * preserved each page's text *content* and assigned the page to the right
     * part. We deliberately do NOT compare inter-word spacing: PDFBox's
     * PDFTextStripper and pypdfbox's differ in how many spaces they synthesise
     * across dot-leader / tab-stop runs (e.g. a table-of-contents
     * ".... 5-1" vs "....5-1"), and that divergence lives entirely in the
     * text-extraction module and is present in unsplit extraction too — it is
     * not a Splitter behaviour. Stripping whitespace keeps this a faithful
     * content-preservation pin on the Splitter while staying agnostic to the
     * text module's spacing heuristic. A genuinely dropped, duplicated, or
     * mis-assigned page still fails (its characters move or vanish).
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
