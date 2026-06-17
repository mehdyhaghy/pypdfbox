import java.io.ByteArrayInputStream;
import java.io.PrintStream;
import org.apache.fontbox.cmap.CMap;
import org.apache.fontbox.cmap.CMapParser;

/**
 * Live oracle probe: predefined-CMap *registry* fuzz — the facet the sibling
 * probes (PredefCMapProbe / PredefCMapInfoProbe / PredefCMapType0Probe) leave
 * thin.
 *
 * Those probes pin getName / getWMode / toCID / readCode length on a handful of
 * Japan1/GB1 CMaps and the CIDSystemInfo triple on a fixed shortlist. This probe
 * sweeps the registry lookup across ALL FOUR Adobe orderings (Japan1, GB1, CNS1,
 * Korea1) plus Identity, exercising:
 *
 *   - the predefined name -> CMap resolution itself (the registry),
 *   - the ``usecmap`` chain a -V variant resolves through its -H base,
 *   - WMode for the full set of -V CMaps,
 *   - the CIDSystemInfo (registry/ordering/supplement) carried by each,
 *   - has_cid / has_unicode classification across mapping shapes,
 *   - an UNKNOWN predefined name -> error (caught and reported, not crashed).
 *
 * Two modes:
 *
 *   info <name> [<name> ...]
 *     One block per CMap (UTF-8, no extra framing):
 *       CMAP <getName>
 *       REGISTRY <registry>
 *       ORDERING <ordering>
 *       SUPPLEMENT <supplement>
 *       WMODE <wmode>
 *       HASCID <true|false>
 *       HASUNICODE <true|false>
 *     or, when CMapParser.parsePredefined throws (unknown name):
 *       CMAP <requestedName>
 *       ERROR <exceptionSimpleName>
 *
 *   cid <name> <hexcode> [<hexcode> ...]
 *     CMAP <getName> followed by one line per code:
 *       CID <hexcode> -> <cid> len=<codeLength>
 */
public final class PredefinedCMapFuzzProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("info".equals(mode)) {
            for (int i = 1; i < args.length; i++) {
                emitInfo(out, args[i]);
            }
        } else if ("cid".equals(mode)) {
            String name = args[1];
            CMap cmap = new CMapParser().parsePredefined(name);
            out.println("CMAP " + cmap.getName());
            for (int i = 2; i < args.length; i++) {
                byte[] code = hexToBytes(args[i]);
                int cid = cmap.toCID(toInt(code));
                int len = codeLength(cmap, code);
                out.println("CID " + args[i].toUpperCase() + " -> " + cid
                        + " len=" + len);
            }
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void emitInfo(PrintStream out, String name) {
        CMap cmap;
        try {
            cmap = new CMapParser().parsePredefined(name);
        } catch (Exception e) {
            out.println("CMAP " + name);
            out.println("ERROR " + e.getClass().getSimpleName());
            return;
        }
        out.println("CMAP " + cmap.getName());
        out.println("REGISTRY " + cmap.getRegistry());
        out.println("ORDERING " + cmap.getOrdering());
        out.println("SUPPLEMENT " + cmap.getSupplement());
        out.println("WMODE " + cmap.getWMode());
        out.println("HASCID " + cmap.hasCIDMappings());
        out.println("HASUNICODE " + cmap.hasUnicodeMappings());
    }

    /** Number of bytes readCode consumes from the given buffer. */
    private static int codeLength(CMap cmap, byte[] code) throws Exception {
        ByteArrayInputStream in = new ByteArrayInputStream(code);
        int before = in.available();
        cmap.readCode(in);
        return before - in.available();
    }

    private static int toInt(byte[] data) {
        int code = 0;
        for (byte b : data) {
            code = (code << 8) | (b & 0xFF);
        }
        return code;
    }

    private static byte[] hexToBytes(String hex) {
        int n = hex.length() / 2;
        byte[] out = new byte[n];
        for (int i = 0; i < n; i++) {
            out[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }
}
