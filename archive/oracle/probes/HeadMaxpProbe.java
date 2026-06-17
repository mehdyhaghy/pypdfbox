import java.io.File;
import java.io.PrintStream;
import java.util.Calendar;
import org.apache.fontbox.ttf.HeaderTable;
import org.apache.fontbox.ttf.MaximumProfileTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;

/**
 * Live oracle probe: emit Apache FontBox's parsed {@code head} and {@code maxp}
 * table fields in a canonical line-oriented format that pypdfbox's
 * {@code HeaderTable} / {@code MaximumProfileTable} mirror.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> HeadMaxpProbe font.ttf
 *
 * Output (UTF-8, stdout): one TAB-separated KEY\tVALUE line per accessor.
 *
 * Dates ({@code head.created} / {@code head.modified}) are emitted as the
 * absolute epoch-millisecond instant ({@link Calendar#getTimeInMillis()}); this
 * is timezone-independent so the Python side can compare against
 * {@code int(datetime.timestamp() * 1000)} without locale/offset drift.
 */
public final class HeadMaxpProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (TrueTypeFont ttf = new TTFParser().parse(
                new RandomAccessReadBufferedFile(new File(args[0])))) {
            HeaderTable head = ttf.getHeader();
            if (head == null) {
                out.println("head\tabsent");
            } else {
                out.println("head\tpresent");
                out.println("head.version\t" + head.getVersion());
                out.println("head.fontRevision\t" + head.getFontRevision());
                out.println("head.checkSumAdjustment\t" + head.getCheckSumAdjustment());
                out.println("head.magicNumber\t" + head.getMagicNumber());
                out.println("head.flags\t" + head.getFlags());
                out.println("head.unitsPerEm\t" + head.getUnitsPerEm());
                out.println("head.created\t" + millis(head.getCreated()));
                out.println("head.modified\t" + millis(head.getModified()));
                out.println("head.xMin\t" + head.getXMin());
                out.println("head.yMin\t" + head.getYMin());
                out.println("head.xMax\t" + head.getXMax());
                out.println("head.yMax\t" + head.getYMax());
                out.println("head.macStyle\t" + head.getMacStyle());
                out.println("head.lowestRecPPEM\t" + head.getLowestRecPPEM());
                out.println("head.fontDirectionHint\t" + head.getFontDirectionHint());
                out.println("head.indexToLocFormat\t" + head.getIndexToLocFormat());
                out.println("head.glyphDataFormat\t" + head.getGlyphDataFormat());
            }

            MaximumProfileTable maxp = ttf.getMaximumProfile();
            if (maxp == null) {
                out.println("maxp\tabsent");
            } else {
                out.println("maxp\tpresent");
                out.println("maxp.version\t" + maxp.getVersion());
                out.println("maxp.numGlyphs\t" + maxp.getNumGlyphs());
                out.println("maxp.maxPoints\t" + maxp.getMaxPoints());
                out.println("maxp.maxContours\t" + maxp.getMaxContours());
                out.println("maxp.maxCompositePoints\t" + maxp.getMaxCompositePoints());
                out.println("maxp.maxCompositeContours\t" + maxp.getMaxCompositeContours());
                out.println("maxp.maxZones\t" + maxp.getMaxZones());
                out.println("maxp.maxTwilightPoints\t" + maxp.getMaxTwilightPoints());
                out.println("maxp.maxStorage\t" + maxp.getMaxStorage());
                out.println("maxp.maxFunctionDefs\t" + maxp.getMaxFunctionDefs());
                out.println("maxp.maxInstructionDefs\t" + maxp.getMaxInstructionDefs());
                out.println("maxp.maxStackElements\t" + maxp.getMaxStackElements());
                out.println("maxp.maxSizeOfInstructions\t" + maxp.getMaxSizeOfInstructions());
                out.println("maxp.maxComponentElements\t" + maxp.getMaxComponentElements());
                out.println("maxp.maxComponentDepth\t" + maxp.getMaxComponentDepth());
            }
        }
    }

    private static String millis(Calendar c) {
        return c == null ? "null" : Long.toString(c.getTimeInMillis());
    }
}
