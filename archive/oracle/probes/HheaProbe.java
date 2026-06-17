import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.ttf.HorizontalHeaderTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;

/**
 * Live oracle probe: emit Apache FontBox's parsed {@code hhea} (horizontal
 * header) table fields in a canonical line-oriented format that pypdfbox's
 * {@code HorizontalHeaderTable} mirrors.
 *
 * Prior fontbox oracle waves pinned {@code hmtx}, {@code head}/{@code maxp},
 * {@code OS/2}, {@code vhea}/{@code vmtx}, and {@code post}; this probe targets
 * the {@code hhea} table — the required horizontal writing-mode header whose
 * {@code numberOfHMetrics} count drives the {@code hmtx} table layout.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> HheaProbe font.ttf
 *
 * Output (UTF-8, stdout): one TAB-separated KEY\tVALUE line per accessor.
 *
 * {@code getVersion} is a Java {@code float} (16.16 fixed); the Python side
 * compares it against a {@code Float.toString}-faithful shortest-repr helper.
 */
public final class HheaProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (TrueTypeFont ttf = new TTFParser().parse(
                new RandomAccessReadBufferedFile(new File(args[0])))) {
            HorizontalHeaderTable hhea = ttf.getHorizontalHeader();
            if (hhea == null) {
                out.println("hhea\tabsent");
                return;
            }
            out.println("hhea\tpresent");
            out.println("hhea.version\t" + hhea.getVersion());
            out.println("hhea.ascender\t" + hhea.getAscender());
            out.println("hhea.descender\t" + hhea.getDescender());
            out.println("hhea.lineGap\t" + hhea.getLineGap());
            out.println("hhea.advanceWidthMax\t" + hhea.getAdvanceWidthMax());
            out.println("hhea.minLeftSideBearing\t" + hhea.getMinLeftSideBearing());
            out.println("hhea.minRightSideBearing\t" + hhea.getMinRightSideBearing());
            out.println("hhea.xMaxExtent\t" + hhea.getXMaxExtent());
            out.println("hhea.caretSlopeRise\t" + hhea.getCaretSlopeRise());
            out.println("hhea.caretSlopeRun\t" + hhea.getCaretSlopeRun());
            out.println("hhea.reserved1\t" + hhea.getReserved1());
            out.println("hhea.reserved2\t" + hhea.getReserved2());
            out.println("hhea.reserved3\t" + hhea.getReserved3());
            out.println("hhea.reserved4\t" + hhea.getReserved4());
            out.println("hhea.reserved5\t" + hhea.getReserved5());
            out.println("hhea.metricDataFormat\t" + hhea.getMetricDataFormat());
            out.println("hhea.numberOfHMetrics\t" + hhea.getNumberOfHMetrics());
        }
    }
}
