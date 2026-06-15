import java.io.File;
import java.nio.file.Files;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.fontbox.ttf.TTFTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Live oracle probe for the GPOS (Glyph Positioning) table parse contract under
 * malformed input (wave 1534 differential GPOS fuzz).
 *
 * The critical fact this probe pins: Apache FontBox 3.0.7 has NO
 * {@code GlyphPositioningTable} class at all. {@code TTFParser.readTableDirectory}
 * only instantiates a typed table for cmap / glyf / head / hhea / hmtx / loca /
 * maxp / name / OS-2 / post / DSIG / kern / vhea / vmtx / VORG / GSUB. Every
 * other tag — including "GPOS" — is stored as a generic, never-decoded
 * {@link TTFTable} holding only tag / offset / length / checksum. Consequently
 * FontBox is completely INSENSITIVE to GPOS-internal corruption (wrong version,
 * out-of-bounds ScriptList / FeatureList / LookupList offsets, truncated header,
 * huge lookup count, version 1.1 featureVariations, zero lookups): the table is
 * never parsed, so it never throws. The table is only dropped from the map when
 * the directory entry's offset/length runs past the file (the "Skip table" path
 * — already covered by TtfParserFuzzProbe at the directory level).
 *
 * We project that contract as a stable fingerprint the pypdfbox side reproduces:
 *
 *   ok=true
 *   hasGPOS=<true|false>          // present in getTableMap()
 *   gposClass=<simple class name of the GPOS table object, or ->
 *   gposInit=<getInitialized() of the GPOS table>
 *
 * or the sole line
 *
 *   ok=false
 *
 * on any throw from {@code TTFParser.parse}.
 *
 * Usage:
 *   java -cp ... GposTableFuzzProbe font.bin            # non-embedded (strict) arm
 *   java -cp ... GposTableFuzzProbe font.bin embedded   # embedded (lenient) arm
 */
public final class GposTableFuzzProbe
{
    public static void main(String[] args) throws Exception
    {
        File file = new File(args[0]);
        boolean embedded = args.length > 1 && "embedded".equals(args[1]);
        byte[] bytes = Files.readAllBytes(file.toPath());

        StringBuilder sb = new StringBuilder();
        try (TrueTypeFont font =
                new TTFParser(embedded).parse(new RandomAccessReadBuffer(bytes)))
        {
            TTFTable gpos = font.getTableMap().get("GPOS");
            sb.append("ok=true\n");
            sb.append("hasGPOS=").append(gpos != null).append('\n');
            sb.append("gposClass=")
              .append(gpos == null ? "-" : gpos.getClass().getSimpleName())
              .append('\n');
            sb.append("gposInit=")
              .append(gpos == null ? "-" : String.valueOf(gpos.getInitialized()))
              .append('\n');
        }
        catch (Throwable t)
        {
            System.out.print("ok=false\n");
            return;
        }
        System.out.print(sb);
    }
}
