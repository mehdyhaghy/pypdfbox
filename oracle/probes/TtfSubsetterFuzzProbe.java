import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.fontbox.ttf.TTFSubsetter;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Live oracle probe for {@code org.apache.fontbox.ttf.TTFSubsetter} — the
 * subsetter *driver*. Exercises the public surface
 * ({@code add}/{@code addAll}/{@code addGlyphIds}/{@code setPrefix}/
 * {@code getGIDMap}/{@code writeToStream}) over a battery of glyph-selection
 * cases against a real embedded TTF, and emits canonical, deterministic facts
 * that the pypdfbox port mirrors.
 *
 * <pre>
 *   java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; TtfSubsetterFuzzProbe &lt;ttf&gt; &lt;case&gt; [args...]
 * </pre>
 *
 * Cases (args after the ttf path):
 *   empty                       — add nothing (subset = {.notdef}).
 *   notdef                      — addGlyphIds {0}.
 *   gids   g1,g2,...            — addGlyphIds of the listed (decimal) gids.
 *   uni    cp1,cp2,...          — add() of the listed (decimal) Unicode codepoints.
 *   full                        — addGlyphIds {0 .. numGlyphs-1} (whole font).
 *   prefix PREFIX gids g1,...   — setPrefix then addGlyphIds.
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order):
 *   SRCGLYPHS \t numGlyphsOfSource
 *   GIDMAP    \t newGid:oldGid,newGid:oldGid,...     (ascending newGid)
 *   NUMGLYPHS \t subsetNumGlyphs                     (maxp of the rebuilt font)
 *   TABLE     \t tag \t present(true|false)          for glyf/loca/cmap/hmtx/post/head/maxp/hhea/name
 *   LENBUCKET \t bucket                              (len/1000, coarse size bucket)
 *   PREFIXED  \t baseFontPrefix|NONE                 (6-letter tag on name id 6, or NONE)
 * On any thrown exception the whole run is collapsed to a single line:
 *   ERR \t SimpleExceptionName
 *
 * Never mutates the source font on disk; closes everything via try-with-resources.
 */
public final class TtfSubsetterFuzzProbe {
    private static final String[] PROBED_TABLES = {
        "glyf", "loca", "cmap", "hmtx", "post", "head", "maxp", "hhea", "name"
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 2) {
            out.println("usage: TtfSubsetterFuzzProbe <ttf> <case> [args...]");
            return;
        }
        try {
            run(out, args);
        } catch (Throwable t) {
            out.printf("ERR\t%s%n", t.getClass().getSimpleName());
        }
    }

    private static void run(PrintStream out, String[] args) throws Exception {
        byte[] raw = Files.readAllBytes(new File(args[0]).toPath());
        try (TrueTypeFont src = new TTFParser(true)
                .parse(new RandomAccessReadBuffer(raw))) {
            int srcGlyphs = src.getNumberOfGlyphs();
            TTFSubsetter subsetter = new TTFSubsetter(src);

            String mode = args[1];
            int argi = 2;
            if ("prefix".equals(mode)) {
                subsetter.setPrefix(args[2]);
                mode = args[3];
                argi = 4;
            }
            switch (mode) {
                case "empty":
                case "notdef":
                    if ("notdef".equals(mode)) {
                        subsetter.addGlyphIds(setOf(new int[] {0}));
                    }
                    break;
                case "gids":
                    subsetter.addGlyphIds(parseSet(args[argi]));
                    break;
                case "uni":
                    for (int cp : parseInts(args[argi])) {
                        subsetter.add(cp);
                    }
                    break;
                case "full": {
                    TreeSet<Integer> all = new TreeSet<>();
                    for (int g = 0; g < srcGlyphs; g++) {
                        all.add(g);
                    }
                    subsetter.addGlyphIds(all);
                    break;
                }
                default:
                    out.printf("ERR\tBadMode_%s%n", mode);
                    return;
            }

            out.printf("SRCGLYPHS\t%d%n", srcGlyphs);

            Map<Integer, Integer> gidMap = new TreeMap<>(subsetter.getGIDMap());
            StringBuilder mb = new StringBuilder();
            for (Map.Entry<Integer, Integer> e : gidMap.entrySet()) {
                if (mb.length() > 0) {
                    mb.append(',');
                }
                mb.append(e.getKey()).append(':').append(e.getValue());
            }
            out.printf("GIDMAP\t%s%n", mb.toString());

            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            subsetter.writeToStream(bos);
            byte[] sub = bos.toByteArray();

            try (TrueTypeFont rebuilt = new TTFParser(true)
                    .parse(new RandomAccessReadBuffer(
                            new ByteArrayInputStream(sub)))) {
                out.printf("NUMGLYPHS\t%d%n", rebuilt.getNumberOfGlyphs());
                for (String tag : PROBED_TABLES) {
                    boolean present = rebuilt.getTableMap().containsKey(tag);
                    out.printf("TABLE\t%s\t%b%n", tag, present);
                }
                out.printf("PREFIXED\t%s%n", prefixOf(rebuilt));
            }
            out.printf("LENBUCKET\t%d%n", sub.length / 1000);
        }
    }

    private static String prefixOf(TrueTypeFont ttf) {
        try {
            String ps = ttf.getName();
            if (ps != null && ps.length() >= 7 && ps.charAt(6) == '+'
                    && ps.substring(0, 6).matches("[A-Z]{6}")) {
                return ps.substring(0, 6);
            }
        } catch (Exception e) {
            return "NONE";
        }
        return "NONE";
    }

    private static Set<Integer> parseSet(String csv) {
        TreeSet<Integer> s = new TreeSet<>();
        for (int v : parseInts(csv)) {
            s.add(v);
        }
        return s;
    }

    private static Set<Integer> setOf(int[] vals) {
        TreeSet<Integer> s = new TreeSet<>();
        for (int v : vals) {
            s.add(v);
        }
        return s;
    }

    private static int[] parseInts(String csv) {
        if (csv == null || csv.isEmpty()) {
            return new int[0];
        }
        String[] parts = csv.split(",");
        int[] out = new int[parts.length];
        for (int i = 0; i < parts.length; i++) {
            out[i] = Integer.parseInt(parts[i].trim());
        }
        return out;
    }
}
