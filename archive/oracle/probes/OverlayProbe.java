import java.io.File;
import java.io.PrintStream;
import java.util.HashMap;
import java.util.Map;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.multipdf.Overlay;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: overlay a stamp PDF onto every page of a base PDF with
 * Apache PDFBox's {@link Overlay#overlay(Map)} using a default overlay, save
 * the result, reload it, and emit a deterministic fingerprint of the overlaid
 * structure so the pypdfbox Overlay can be compared against PDFBox's actual
 * behaviour.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> OverlayProbe out.pdf base.pdf stamp.pdf [position]
 *
 * Args:
 *   args[0] = output path the overlaid document is written to.
 *   args[1] = base/input PDF (overlay applied to every page).
 *   args[2] = stamp PDF (its first page is the default overlay).
 *   args[3] = optional "FOREGROUND" or "BACKGROUND" (default BACKGROUND).
 *
 * Output (UTF-8, LF-terminated lines):
 *   pages <totalPageCount>
 *   page <i> <escapedExtractedText>   (one line per page, 0-based i; the text
 *                                       extractor sees BOTH layers, so both the
 *                                       base and the stamp marker appear)
 *   xobject <i> <count>               (number of /XObject entries on page i's
 *                                       Resources — the overlaid form adds one)
 *   olkey <i> <bool>                  ("true" when page i's /XObject map carries
 *                                       a key with the "OL" prefix that Overlay
 *                                       registers the overlay form under)
 */
public final class OverlayProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File output = new File(args[0]);
        File base = new File(args[1]);
        File stamp = new File(args[2]);
        Overlay.Position position = Overlay.Position.BACKGROUND;
        if (args.length > 3 && "FOREGROUND".equals(args[3])) {
            position = Overlay.Position.FOREGROUND;
        }

        try (PDDocument baseDoc = Loader.loadPDF(base);
                PDDocument stampDoc = Loader.loadPDF(stamp);
                Overlay overlay = new Overlay()) {
            overlay.setInputPDF(baseDoc);
            overlay.setDefaultOverlayPDF(stampDoc);
            overlay.setOverlayPosition(position);
            PDDocument result = overlay.overlay(new HashMap<Integer, String>());
            result.save(output);
        }

        try (PDDocument reloaded = Loader.loadPDF(output)) {
            StringBuilder sb = new StringBuilder();
            int total = reloaded.getNumberOfPages();
            sb.append("pages ").append(total).append('\n');

            PDFTextStripper stripper = new PDFTextStripper();
            for (int i = 0; i < total; i++) {
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

    private static String esc(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    private OverlayProbe() {}
}
