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
 * Live oracle probe for the *combined* fontbox CFF charset + built-in
 * encoding + name->GID surface of a **non-CID** CFF that carries a
 * custom charset (GIDs mapped to custom SIDs >= 391) AND a custom
 * embedded /Encoding (Format0 sparse or Format1 range) in the same
 * font.
 *
 * The sibling probes own one surface each: CffCharsetProbe owns the
 * full CFFCharset contract in isolation; CffEncodingProbe owns the
 * predefined-vs-embedded encoding *class* + per-code map in isolation.
 * This probe is the cross-product — it asserts that on a single font
 * the three resolutions (charset GID->name/SID, encoding code->name,
 * and the CFFType1Font.nameToGID round-trip that ties an encoded code
 * back to a glyph index through the charset) all agree with the same
 * Java engine. The load-bearing line is ENC: fontTools collapses both
 * on-disk encoding formats into one name list, so the Format0 vs
 * Format1 class identity is the high-value differential here.
 *
 * <pre>
 *   java -cp ... CffCharsetEncodingProbe &lt;input.cff&gt;
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order):
 *
 *   FONT     \t baseFontClass            CFFFont.getClass().getSimpleName()
 *   CID      \t isCIDFont                CFFCharset.isCIDFont()
 *   NGLYPH   \t count                    number of charstrings (GID range)
 *   ENC      \t encodingClass            CFFType1Font.getEncoding().getClass().getSimpleName()
 *   MAP   \t code \t glyphName           enc.getName(code) for non-".notdef" codes
 *   NAME  \t gid  \t name                charset.getNameForGID(gid)
 *   SID   \t gid  \t sid                 charset.getSIDForGID(gid)
 *   N2G   \t name \t gid                 CFFType1Font.nameToGID(name) for each charset glyph
 *   E2G   \t code \t gid                 nameToGID(enc.getName(code)) for non-".notdef" codes
 *
 * Never mutates the input; closes the stream via try-with-resources.
 */
public final class CffCharsetEncodingProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 1) {
            out.println("usage: CffCharsetEncodingProbe <input.cff>");
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

        if (!(font instanceof CFFType1Font)) {
            out.printf("ENC\tNONE%n");
            return;
        }
        CFFType1Font t1 = (CFFType1Font) font;
        CFFEncoding enc = t1.getEncoding();
        if (enc == null) {
            out.printf("ENC\tNULL%n");
            return;
        }
        out.printf("ENC\t%s%n", enc.getClass().getSimpleName());

        // Per-code encoding map (skip .notdef to keep the diff small).
        for (int code = 0; code <= 255; code++) {
            String name = enc.getName(code);
            if (name == null || ".notdef".equals(name)) {
                continue;
            }
            out.printf("MAP\t%d\t%s%n", code, name);
        }

        // Per-GID charset facts.
        for (int gid = 0; gid < nGlyphs; gid++) {
            String name = charset.getNameForGID(gid);
            out.printf("NAME\t%d\t%s%n", gid, name);
            out.printf("SID\t%d\t%d%n", gid, charset.getSIDForGID(gid));
            if (name != null) {
                out.printf("N2G\t%s\t%d%n", name, t1.nameToGID(name));
            }
        }

        // Encoded-code -> GID round-trip: an encoded byte resolves to a
        // glyph name via the encoding, then to a GID via the charset.
        for (int code = 0; code <= 255; code++) {
            String name = enc.getName(code);
            if (name == null || ".notdef".equals(name)) {
                continue;
            }
            out.printf("E2G\t%d\t%d%n", code, t1.nameToGID(name));
        }
    }
}
