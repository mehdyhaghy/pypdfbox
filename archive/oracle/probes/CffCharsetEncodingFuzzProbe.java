import java.io.PrintStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Paths;
import org.apache.fontbox.cff.CFFCharset;
import org.apache.fontbox.cff.CFFEncoding;
import org.apache.fontbox.cff.CFFParser;

/**
 * Live oracle probe for the FontBox CFF **charset + encoding table reader**
 * methods under hostile / malformed input — wave 1525 differential fuzz.
 *
 * Unlike the sibling charset/encoding probes (which feed well-formed,
 * fontTools-compiled whole fonts through {@code CFFParser.parse}), this probe
 * drives the *private table readers* directly via reflection on raw, possibly
 * truncated/overflowing byte buffers:
 *
 *   CFFParser.readCharset(DataInput, nGlyphs, isCID)
 *   CFFParser.readEncoding(DataInput, charset)
 *
 * This pins the exact byte-level recovery / error behaviour of the hand-ported
 * pypdfbox mirrors {@code CFFParser.read_charset} / {@code read_encoding} and
 * their format-0/1/2 helpers — the surface {@code parse()} delegates to
 * fontTools and therefore never exercises directly.
 *
 * Custom SIDs are kept in the CFF Standard-String range (<= 390) so
 * {@code readString} resolves identically on both engines without a populated
 * STRING INDEX.
 *
 * <pre>
 *   java -cp ... CffCharsetEncodingFuzzProbe charset &lt;nGlyphs&gt; &lt;isCID&gt; &lt;bytes.bin&gt;
 *   java -cp ... CffCharsetEncodingFuzzProbe encoding &lt;nGlyphs&gt; &lt;bytes.bin&gt;
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order). On any throw
 * from the reader the sole line is {@code ERR}. Otherwise:
 *
 * charset mode:
 *   OK
 *   CID    \t isCIDFont
 *   SID    \t gid \t getSIDForGID(gid)        for gid in [0, nGlyphs)
 *   NAME   \t gid \t getNameForGID(gid)       for gid in [0, nGlyphs)  (non-CID)
 *   CIDG   \t gid \t getCIDForGID(gid)        for gid in [0, nGlyphs)  (CID)
 *
 * encoding mode:
 *   OK
 *   ECLS   \t encodingClass.getSimpleName()
 *   ENAME  \t code \t getName(code)           for code in [0, 256) where non-null
 */
public final class CffCharsetEncodingFuzzProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 1) {
            out.println("usage: CffCharsetEncodingFuzzProbe charset|encoding ...");
            return;
        }
        String mode = args[0];
        try {
            if ("charset".equals(mode)) {
                int nGlyphs = Integer.parseInt(args[1]);
                boolean isCid = Boolean.parseBoolean(args[2]);
                byte[] data = Files.readAllBytes(Paths.get(args[3]));
                charset(out, nGlyphs, isCid, data);
            } else if ("encoding".equals(mode)) {
                int nGlyphs = Integer.parseInt(args[1]);
                byte[] data = Files.readAllBytes(Paths.get(args[2]));
                encoding(out, nGlyphs, data);
            } else {
                out.println("usage: CffCharsetEncodingFuzzProbe charset|encoding ...");
            }
        } catch (Throwable t) {
            // Argument / reflection plumbing failures are not the SUT; surface
            // them so the harness fails loudly rather than masquerading as ERR.
            if (t instanceof ReaderError) {
                out.print("ERR\n");
            } else {
                throw t;
            }
        }
    }

    /** Marker so genuine reader throws are distinguishable from plumbing bugs. */
    private static final class ReaderError extends RuntimeException {
        ReaderError(Throwable cause) {
            super(cause);
        }
    }

    private static Object newDataInput(byte[] data) throws Exception {
        Class<?> dib = Class.forName("org.apache.fontbox.cff.DataInputByteArray");
        Constructor<?> ctor = dib.getConstructor(byte[].class);
        return ctor.newInstance((Object) data);
    }

    private static void charset(PrintStream out, int nGlyphs, boolean isCid,
            byte[] data) throws Exception {
        Object din = newDataInput(data);
        Class<?> diIface = Class.forName("org.apache.fontbox.cff.DataInput");
        CFFParser parser = new CFFParser();
        Method m = CFFParser.class.getDeclaredMethod(
                "readCharset", diIface, int.class, boolean.class);
        m.setAccessible(true);
        CFFCharset cs;
        try {
            cs = (CFFCharset) m.invoke(parser, din, nGlyphs, isCid);
        } catch (InvocationTargetException ite) {
            throw new ReaderError(ite.getTargetException());
        }
        out.print("OK\n");
        out.printf("CID\t%s%n", cs.isCIDFont());
        for (int gid = 0; gid < nGlyphs; gid++) {
            out.printf("SID\t%d\t%d%n", gid, safeSid(cs, gid));
            if (isCid) {
                out.printf("CIDG\t%d\t%d%n", gid, safeCid(cs, gid));
            } else {
                out.printf("NAME\t%d\t%s%n", gid, safeName(cs, gid));
            }
        }
    }

    private static void encoding(PrintStream out, int nGlyphs, byte[] data)
            throws Exception {
        // Build a non-CID charset that maps each gid to a standard-range SID so
        // the encoding reader's charset.getSIDForGID(gid) succeeds.
        CFFCharset cs = buildType1Charset(nGlyphs);
        Object din = newDataInput(data);
        Class<?> diIface = Class.forName("org.apache.fontbox.cff.DataInput");
        CFFParser parser = new CFFParser();
        Method m = CFFParser.class.getDeclaredMethod(
                "readEncoding", diIface, CFFCharset.class);
        m.setAccessible(true);
        CFFEncoding enc;
        try {
            enc = (CFFEncoding) m.invoke(parser, din, cs);
        } catch (InvocationTargetException ite) {
            throw new ReaderError(ite.getTargetException());
        }
        out.print("OK\n");
        out.printf("ECLS\t%s%n", enc.getClass().getSimpleName());
        for (int code = 0; code < 256; code++) {
            String name = enc.getName(code);
            if (name == null || ".notdef".equals(name)) {
                continue;
            }
            out.printf("ENAME\t%d\t%s%n", code, name);
        }
    }

    private static CFFCharset buildType1Charset(int nGlyphs) throws Exception {
        Class<?> t1 = Class.forName("org.apache.fontbox.cff.CFFCharsetType1");
        Constructor<?> ctor = t1.getDeclaredConstructor();
        ctor.setAccessible(true);
        CFFCharset cs = (CFFCharset) ctor.newInstance();
        cs.addSID(0, 0, ".notdef");
        for (int gid = 1; gid < nGlyphs; gid++) {
            // Map gid -> a deterministic standard-range SID (1..390).
            int sid = ((gid - 1) % 390) + 1;
            cs.addSID(gid, sid, "sid" + sid);
        }
        return cs;
    }

    private static int safeSid(CFFCharset cs, int gid) {
        try {
            return cs.getSIDForGID(gid);
        } catch (Throwable t) {
            return -1;
        }
    }

    private static String safeName(CFFCharset cs, int gid) {
        try {
            return cs.getNameForGID(gid);
        } catch (Throwable t) {
            return "-1";
        }
    }

    private static int safeCid(CFFCharset cs, int gid) {
        try {
            return cs.getCIDForGID(gid);
        } catch (Throwable t) {
            return -1;
        }
    }
}
