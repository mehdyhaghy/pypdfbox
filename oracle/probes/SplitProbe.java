import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.multipdf.Splitter;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Live oracle probe: split a PDF via PDFBox's {@link Splitter} at a fixed
 * split-at-page boundary, save each resulting part to disk, and emit the part
 * count + per-part page counts so the pypdfbox side can be compared against
 * PDFBox's actual split behaviour.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> SplitProbe in.pdf <splitAtPage> outDir
 *
 * Args:
 *   args[0] = input PDF to split.
 *   args[1] = the splitAtPage value passed to Splitter.setSplitAtPage (every
 *             N pages becomes one part).
 *   args[2] = directory the parts are written into (part_0.pdf, part_1.pdf...).
 *
 * Output (UTF-8, LF-terminated lines):
 *   parts <partCount>
 *   part <i> <pageCount>     (one line per part, 0-based index i)
 *
 * Each part is also saved to <outDir>/part_<i>.pdf so the test can validate it
 * with qpdf independently.
 */
public final class SplitProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int splitAt = Integer.parseInt(args[1]);
        File outDir = new File(args[2]);
        outDir.mkdirs();

        try (PDDocument source = Loader.loadPDF(new File(args[0]))) {
            Splitter splitter = new Splitter();
            splitter.setSplitAtPage(splitAt);
            List<PDDocument> parts = splitter.split(source);
            StringBuilder sb = new StringBuilder();
            sb.append("parts ").append(parts.size()).append('\n');
            for (int i = 0; i < parts.size(); i++) {
                PDDocument part = parts.get(i);
                try {
                    sb.append("part ").append(i).append(' ')
                            .append(part.getNumberOfPages()).append('\n');
                    part.save(new File(outDir, "part_" + i + ".pdf"));
                } finally {
                    part.close();
                }
            }
            out.print(sb);
        }
    }
}
