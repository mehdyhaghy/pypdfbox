import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.multipdf.Overlay;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: differential-fuzz Apache PDFBox's
 * {@link org.apache.pdfbox.multipdf.Overlay} across a matrix of overlay
 * configurations that the existing {@code OverlayProbe} (default overlay only)
 * and {@code OverlayToolProbe} (CLI selectors) do not cover:
 *
 *   - all-pages (repeating-cycle) overlay where the i-th overlay page lands on
 *     the i-th (mod N) input page, with the base having MORE pages than the
 *     overlay (the cycle wraps),
 *   - all-pages overlay where the base has FEWER pages than the overlay (the
 *     extra overlay pages are silently unused),
 *   - per-page-number specific overlay with GAPS (some input pages get no
 *     overlay),
 *   - selector precedence: first/last vs odd/even vs default on the same run,
 *   - foreground vs background,
 *   - overlay an empty (zero-content) page,
 *   - overlay pages of different sizes / rotations onto a fixed base.
 *
 * The configuration is named by args[2]; all input docs are pre-built by the
 * Python side and handed in by path so both sides overlay byte-identical input.
 *
 * Usage:
 *   java -cp <jar>:<build> OverlayFuzzProbe <out.pdf> <base.pdf> <config> [docPaths...]
 *
 * Configs (and the doc-path args they consume after args[2]):
 *   default-bg     <stamp>                  default overlay, BACKGROUND
 *   default-fg     <stamp>                  default overlay, FOREGROUND
 *   all-pages      <multi>                  all-pages repeating overlay (BG)
 *   all-pages-fg   <multi>                  all-pages repeating overlay (FG)
 *   specific-gaps  <a> <b>                  page 1 -> a, page 3 -> b (gaps)
 *   first-last     <first> <last>           first + last page overlays
 *   odd-even       <odd> <even>             odd + even page overlays
 *   first-last-odd-even <first> <last> <odd> <even>  full precedence stack
 *   default-plus-first  <default> <first>   default + first (first wins page 1)
 *   empty-overlay  <emptydoc>               overlay whose first page has no Contents
 *
 * Output (UTF-8, LF-terminated):
 *   pages <n>
 *   page <i> <escapedText>     (0-based; extractor sees all applied layers)
 *   xobject <i> <count>
 *   olkey <i> <bool>           (true if page i has an OL-prefixed /XObject key)
 */
public final class OverlayFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File output = new File(args[0]);
        File base = new File(args[1]);
        String config = args[2];

        try (PDDocument baseDoc = Loader.loadPDF(base);
                Overlay overlay = new Overlay()) {
            overlay.setInputPDF(baseDoc);
            List<PDDocument> opened = new ArrayList<>();
            try {
                Map<Integer, String> pageMap = new HashMap<>();
                switch (config) {
                    case "default-bg":
                        overlay.setDefaultOverlayPDF(open(opened, args[3]));
                        overlay.setOverlayPosition(Overlay.Position.BACKGROUND);
                        break;
                    case "default-fg":
                        overlay.setDefaultOverlayPDF(open(opened, args[3]));
                        overlay.setOverlayPosition(Overlay.Position.FOREGROUND);
                        break;
                    case "all-pages":
                        overlay.setAllPagesOverlayPDF(open(opened, args[3]));
                        overlay.setOverlayPosition(Overlay.Position.BACKGROUND);
                        break;
                    case "all-pages-fg":
                        overlay.setAllPagesOverlayPDF(open(opened, args[3]));
                        overlay.setOverlayPosition(Overlay.Position.FOREGROUND);
                        break;
                    case "specific-gaps":
                        pageMap.put(1, args[3]);
                        pageMap.put(3, args[4]);
                        break;
                    case "first-last":
                        overlay.setFirstPageOverlayPDF(open(opened, args[3]));
                        overlay.setLastPageOverlayPDF(open(opened, args[4]));
                        break;
                    case "odd-even":
                        overlay.setOddPageOverlayPDF(open(opened, args[3]));
                        overlay.setEvenPageOverlayPDF(open(opened, args[4]));
                        break;
                    case "first-last-odd-even":
                        overlay.setFirstPageOverlayPDF(open(opened, args[3]));
                        overlay.setLastPageOverlayPDF(open(opened, args[4]));
                        overlay.setOddPageOverlayPDF(open(opened, args[5]));
                        overlay.setEvenPageOverlayPDF(open(opened, args[6]));
                        break;
                    case "default-plus-first":
                        overlay.setDefaultOverlayPDF(open(opened, args[3]));
                        overlay.setFirstPageOverlayPDF(open(opened, args[4]));
                        break;
                    case "empty-overlay":
                        overlay.setDefaultOverlayPDF(open(opened, args[3]));
                        break;
                    default:
                        throw new IllegalArgumentException("unknown config: " + config);
                }
                PDDocument result = overlay.overlay(pageMap);
                result.save(output);
            } finally {
                for (PDDocument d : opened) {
                    d.close();
                }
            }
        }

        try (PDDocument reloaded = Loader.loadPDF(output)) {
            StringBuilder sb = new StringBuilder();
            int total = reloaded.getNumberOfPages();
            sb.append("pages ").append(total).append('\n');

            for (int i = 0; i < total; i++) {
                PDFTextStripper stripper = new PDFTextStripper();
                stripper.setStartPage(i + 1);
                stripper.setEndPage(i + 1);
                String text = stripper.getText(reloaded).trim();
                sb.append("page ").append(i).append(' ').append(esc(text)).append('\n');
            }

            for (int i = 0; i < total; i++) {
                PDPage page = reloaded.getPage(i);
                PDResources res = page.getResources();
                int xobjCount = 0;
                boolean hasOlKey = false;
                if (res != null) {
                    for (COSName name : res.getXObjectNames()) {
                        xobjCount++;
                        if (name.getName().startsWith("OL")) {
                            hasOlKey = true;
                        }
                    }
                }
                sb.append("xobject ").append(i).append(' ').append(xobjCount).append('\n');
                sb.append("olkey ").append(i).append(' ').append(hasOlKey).append('\n');
            }

            out.print(sb);
        }
    }

    private static PDDocument open(List<PDDocument> opened, String path) throws Exception {
        PDDocument d = Loader.loadPDF(new File(path));
        opened.add(d);
        return d;
    }

    private static String esc(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    private OverlayFuzzProbe() {}
}
