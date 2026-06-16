import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.PrintStream;
import org.apache.fontbox.cff.CFFCharset;
import org.apache.fontbox.cff.CFFEncoding;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.CFFParser;
import org.apache.fontbox.cff.CFFType1Font;

/**
 * Live oracle probe for the fontbox CFF charset + encoding *lookup* surface
 * driven over **edge / out-of-range** keys — wave 1555 differential fuzz.
 *
 * Unlike the sibling whole-font probes (CffCharsetProbe / CffEncodingProbe /
 * CffCharsetEncodingProbe), which sweep only the *in-range* GID space
 * (0..nGlyphs) and the resolved per-code map, this probe hammers the
 * resolvers with hostile keys: negative GIDs, GIDs past nGlyphs, SIDs past
 * the Standard-String + STRING-INDEX bound, glyph names that are not in the
 * charset, codes outside 0..255, and (for CID fonts) CIDs with no GID. It
 * also covers the wave 1525 byte-level reader's *missing* counterpart: the
 * predefined ISOAdobe / Standard / Expert tables reached through
 * CFFParser.parse() and their lookup behaviour at the boundaries.
 *
 * The wave-1525 fuzz probe drove the private read_charset / read_encoding
 * readers by reflection on raw bytes; this probe instead pins the *public*
 * CFFCharset.getNameForGID / getSIDForGID / getGIDForSID / getSID /
 * getCIDForGID / getGIDForCID and CFFType1Font.nameToGID surface that
 * pypdfbox folds onto CFFFont — the API a renderer actually calls.
 *
 * <pre>
 *   java -cp ... CffCharsetEdgeLookupProbe &lt;input.cff&gt;
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order). Every cell is
 * exception-safe: a throw from the resolver renders as the literal token
 * {@code THROW} so divergence in *whether* a key throws is itself pinned.
 *
 *   FONT  \t baseFontClass
 *   CID   \t isCIDFont
 *   NGLYPH\t nGlyphs
 *   NAME  \t gid  \t getNameForGID(gid)            (or NULL / THROW)
 *   SID   \t gid  \t getSIDForGID(gid)             (or THROW)
 *   GFS   \t sid  \t getGIDForSID(sid)             (or THROW)
 *   GSID  \t name \t getSID(name)                  (or THROW)
 *   N2G   \t name \t nameToGID(name)   (Type1 only, or THROW)
 *   ENAME \t code \t encoding.getName(code) (Type1, or NULL / THROW)
 *   CIDG  \t gid  \t getCIDForGID(gid)  (CID only, or THROW)
 *   GFC   \t cid  \t getGIDForCID(cid)  (CID only, or THROW)
 *
 * Never mutates the input; closes the stream via try-with-resources.
 */
public final class CffCharsetEdgeLookupProbe {

    private static final int[] EDGE_GIDS = {-1, 0, 1, 2, 3, 1000, 65535, 70000};
    private static final int[] EDGE_SIDS = {-1, 0, 1, 2, 229, 390, 391, 99999};
    private static final String[] EDGE_NAMES = {
        "", ".notdef", "space", "A", "alpha", "h0000", "no_such_glyph",
        "exclamsmall"
    };
    private static final int[] EDGE_CODES = {-1, 0, 32, 65, 97, 255, 256, 1000};
    private static final int[] EDGE_CIDS = {-1, 0, 1, 2, 3, 1000, 99999};

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 1) {
            out.println("usage: CffCharsetEdgeLookupProbe <input.cff>");
            return;
        }
        read(out, args[0]);
    }

    private static void read(PrintStream out, String path) throws Exception {
        byte[] data;
        try (FileInputStream fis = new FileInputStream(new File(path))) {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = fis.read(buf)) > 0) {
                bos.write(buf, 0, n);
            }
            data = bos.toByteArray();
        }
        final byte[] payload = data;
        CFFFont font = new CFFParser().parse(payload,
                new CFFParser.ByteSource() {
                    @Override
                    public byte[] getBytes() {
                        return payload;
                    }
                }).get(0);
        out.printf("FONT\t%s%n", font.getClass().getSimpleName());

        CFFCharset charset = font.getCharset();
        out.printf("CID\t%s%n", charset.isCIDFont());

        int nGlyphs = font.getCharStringBytes().size();
        out.printf("NGLYPH\t%d%n", nGlyphs);

        for (int gid : EDGE_GIDS) {
            out.printf("NAME\t%d\t%s%n", gid, safeName(charset, gid));
            out.printf("SID\t%d\t%s%n", gid, safeSidForGid(charset, gid));
        }
        for (int sid : EDGE_SIDS) {
            out.printf("GFS\t%d\t%s%n", sid, safeGidForSid(charset, sid));
        }
        for (String name : EDGE_NAMES) {
            out.printf("GSID\t%s\t%s%n", name, safeSid(charset, name));
        }

        if (font instanceof CFFType1Font) {
            CFFType1Font t1 = (CFFType1Font) font;
            for (String name : EDGE_NAMES) {
                out.printf("N2G\t%s\t%s%n", name, safeNameToGid(t1, name));
            }
            CFFEncoding enc = t1.getEncoding();
            out.printf("ENC\t%s%n",
                    enc == null ? "NULL" : enc.getClass().getSimpleName());
            for (int code : EDGE_CODES) {
                out.printf("ENAME\t%d\t%s%n", code, safeEncName(enc, code));
            }
        }

        if (charset.isCIDFont()) {
            for (int gid : EDGE_GIDS) {
                out.printf("CIDG\t%d\t%s%n", gid, safeCidForGid(charset, gid));
            }
            for (int cid : EDGE_CIDS) {
                out.printf("GFC\t%d\t%s%n", cid, safeGidForCid(charset, cid));
            }
        }
    }

    private static String safeName(CFFCharset cs, int gid) {
        try {
            String name = cs.getNameForGID(gid);
            return name == null ? "NULL" : name;
        } catch (Throwable t) {
            return "THROW";
        }
    }

    private static String safeSidForGid(CFFCharset cs, int gid) {
        try {
            return Integer.toString(cs.getSIDForGID(gid));
        } catch (Throwable t) {
            return "THROW";
        }
    }

    private static String safeGidForSid(CFFCharset cs, int sid) {
        try {
            return Integer.toString(cs.getGIDForSID(sid));
        } catch (Throwable t) {
            return "THROW";
        }
    }

    private static String safeSid(CFFCharset cs, String name) {
        try {
            return Integer.toString(cs.getSID(name));
        } catch (Throwable t) {
            return "THROW";
        }
    }

    private static String safeNameToGid(CFFType1Font t1, String name) {
        try {
            return Integer.toString(t1.nameToGID(name));
        } catch (Throwable t) {
            return "THROW";
        }
    }

    private static String safeEncName(CFFEncoding enc, int code) {
        if (enc == null) {
            return "NULL";
        }
        try {
            String name = enc.getName(code);
            return name == null ? "NULL" : name;
        } catch (Throwable t) {
            return "THROW";
        }
    }

    private static String safeCidForGid(CFFCharset cs, int gid) {
        try {
            return Integer.toString(cs.getCIDForGID(gid));
        } catch (Throwable t) {
            return "THROW";
        }
    }

    private static String safeGidForCid(CFFCharset cs, int cid) {
        try {
            return Integer.toString(cs.getGIDForCID(cid));
        } catch (Throwable t) {
            return "THROW";
        }
    }
}
