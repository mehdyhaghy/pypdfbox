import java.io.PrintStream;
import org.apache.fontbox.cmap.CMap;
import org.apache.fontbox.cmap.CMapParser;

/**
 * Live oracle probe: predefined-CMap *metadata* (the facet PredefCMapProbe /
 * PredefCMapType0Probe / EmbeddedCMapProbe leave unpinned).
 *
 * Those probes pin getName / getWMode / toCID / readCode length. This one pins
 * the CIDSystemInfo triple and the mapping/space predicates that PDFBox derives
 * from a predefined CMap's own ``/CIDSystemInfo`` dict (and, for -V variants,
 * inherits behaviourally through the ``usecmap`` base):
 *
 *   - CMap.getRegistry()          (/Registry of the embedded CIDSystemInfo)
 *   - CMap.getOrdering()          (/Ordering)
 *   - CMap.getSupplement()        (/Supplement)
 *   - CMap.getWMode()             (0 horizontal / 1 vertical for -V variants)
 *   - CMap.hasCIDMappings()       (cidrange/cidchar present)
 *   - CMap.hasUnicodeMappings()   (bfrange/bfchar present — true for *-UCS2)
 *   - CMap.getSpaceMapping()      (code mapped to U+0020, -1 if none)
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> PredefCMapInfoProbe <name> [<name> ...]
 *
 * Output, UTF-8, one block per CMap (no extra framing):
 *   CMAP <name>
 *   REGISTRY <registry>
 *   ORDERING <ordering>
 *   SUPPLEMENT <supplement>
 *   WMODE <wmode>
 *   HASCID <true|false>
 *   HASUNICODE <true|false>
 *   SPACE <spaceMapping>
 */
public final class PredefCMapInfoProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        for (String name : args) {
            CMap cmap = new CMapParser().parsePredefined(name);
            out.println("CMAP " + cmap.getName());
            out.println("REGISTRY " + cmap.getRegistry());
            out.println("ORDERING " + cmap.getOrdering());
            out.println("SUPPLEMENT " + cmap.getSupplement());
            out.println("WMODE " + cmap.getWMode());
            out.println("HASCID " + cmap.hasCIDMappings());
            out.println("HASUNICODE " + cmap.hasUnicodeMappings());
            out.println("SPACE " + cmap.getSpaceMapping());
        }
    }
}
