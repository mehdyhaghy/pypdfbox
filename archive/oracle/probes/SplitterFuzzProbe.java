import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.multipdf.Splitter;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe: differential-fuzz PDFBox's {@link Splitter} CONFIGURATION
 * surface over a single source document, emitting a STABLE structural
 * fingerprint of the resulting document list (count + per-result page count +
 * resolved MediaBox/Rotate of each result's first page + any exception class).
 *
 * Companion to SplitProbe (one fixed interval), SplitterProbe (partition +
 * first-page text at the three boundary intervals) and SplitterInheritProbe
 * (per-page geometry). This probe instead fuzzes the SETTERS themselves — the
 * angles those three do NOT cover:
 *
 *   - setSplitAtPage(n) with n = 1 / 2 / 3 / larger-than-pages / 0 (invalid);
 *   - setStartPage / setEndPage bounds, including start>end (invalid order);
 *   - start clamp + split interaction (the split_at_page modulo uses
 *     max(1, start));
 *   - a single-page source and a zero-page source;
 *   - inherited MediaBox/Rotate survival on the FIRST page of the FIRST result.
 *
 * The source PDF is produced by pypdfbox so both engines see byte-identical
 * input. Bytes are never compared — only recoverable structural facts and the
 * exception class on invalid configurations.
 *
 * Usage:
 *   java SplitterFuzzProbe in.pdf <config>
 *
 * config grammar (semicolon-separated key=value, all optional):
 *   split=N     -> setSplitAtPage(N)
 *   start=N     -> setStartPage(N)
 *   end=N       -> setEndPage(N)
 * e.g.  "split=2"   "start=2;end=4"   "split=3;start=2"   "split=0"
 *
 * Output (UTF-8, single line). On success:
 *   ok count=<C> pages=<p0,p1,...> firstmb=<x,y,w,h> firstrot=<R>
 * where firstmb/firstrot describe the first page of the first result document
 * (firstmb=- firstrot=- when there are no result pages). On an exception while
 * configuring or splitting:
 *   err <SimpleClassName>
 */
public final class SplitterFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File input = new File(args[0]);
        String config = args.length > 1 ? args[1] : "";

        try (PDDocument source = Loader.loadPDF(input)) {
            Splitter splitter = new Splitter();

            Integer split = null;
            Integer start = null;
            Integer end = null;
            for (String tok : config.split(";")) {
                tok = tok.trim();
                if (tok.isEmpty()) {
                    continue;
                }
                int eq = tok.indexOf('=');
                String key = tok.substring(0, eq).trim();
                int val = Integer.parseInt(tok.substring(eq + 1).trim());
                if ("split".equals(key)) {
                    split = val;
                } else if ("start".equals(key)) {
                    start = val;
                } else if ("end".equals(key)) {
                    end = val;
                }
            }

            List<PDDocument> parts;
            try {
                // Apply setters in the same order the PDFSplit tool does:
                // start, end, split. Each may throw IllegalArgumentException
                // for an out-of-range value.
                if (start != null) {
                    splitter.setStartPage(start);
                }
                if (end != null) {
                    splitter.setEndPage(end);
                }
                if (split != null) {
                    splitter.setSplitAtPage(split);
                }
                parts = splitter.split(source);
            } catch (Exception ex) {
                out.print("err " + ex.getClass().getSimpleName());
                return;
            }

            StringBuilder sb = new StringBuilder();
            sb.append("ok count=").append(parts.size());
            sb.append(" pages=");
            String mb = "-";
            String rot = "-";
            try {
                for (int i = 0; i < parts.size(); i++) {
                    if (i > 0) {
                        sb.append(',');
                    }
                    sb.append(parts.get(i).getNumberOfPages());
                }
                if (!parts.isEmpty() && parts.get(0).getNumberOfPages() > 0) {
                    PDPage first = parts.get(0).getPage(0);
                    PDRectangle r = first.getMediaBox();
                    mb = round(r.getLowerLeftX()) + "," + round(r.getLowerLeftY())
                            + "," + round(r.getWidth()) + "," + round(r.getHeight());
                    rot = Integer.toString(first.getRotation());
                }
            } finally {
                for (PDDocument part : parts) {
                    part.close();
                }
            }
            sb.append(" firstmb=").append(mb);
            sb.append(" firstrot=").append(rot);
            out.print(sb);
        }
    }

    private static long round(float v) {
        return Math.round(v);
    }
}
