import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSignature;

/**
 * Differential fuzz probe for {@link PDSignature} signature-dictionary read /
 * parse leniency over malformed {@code /ByteRange}, {@code /Contents} and the
 * identity-field accessors, Apache PDFBox 3.0.7 (wave 1517, agent E). This is
 * the READ / PARSE path only — no cryptographic verification.
 *
 * <p>Complements the well-formed signature parity suites (round-trip field
 * accessors, byte-range arithmetic of a genuinely signed PDF) — none of which
 * exercise the MALFORMED subset this probe targets:
 * <ul>
 *   <li>{@code getByteRange()}: absent (returns {@code int[0]}); odd length;
 *       2 / 6 entries; element a float (truncated via {@code intValue()}); a
 *       non-number element (substituted with {@code -1}); negative values; an
 *       empty array.</li>
 *   <li>{@code getContents()}: absent / a {@code COSString} (hex or literal) /
 *       a wrong type ({@code COSName}, {@code COSInteger}, {@code COSArray}) —
 *       wrong type yields an empty array.</li>
 *   <li>{@code getSignedContent(byte[])}: the monotonic-cursor
 *       {@code COSFilterInputStream} stitch over the document's own bytes for
 *       in-bounds, out-of-bounds, overlapping and out-of-order ranges, plus
 *       odd-length ranges (the trailing lone entry is dropped by the
 *       {@code length/2} pairing).</li>
 *   <li>{@code getContents(byte[])}: the {@code begin = a+b+1},
 *       {@code len = c-begin-1} hex-window arithmetic over the document bytes
 *       and its {@code <...>} delimiter strip.</li>
 *   <li>identity accessors {@code getFilter} {@code getSubFilter}
 *       {@code getName} {@code getReason} {@code getSignDate} — name vs string
 *       storage, wrong types, absent.</li>
 * </ul>
 *
 * <p>Driven file-based, mirroring {@code FileSpecFuzzProbe}: the pypdfbox
 * sibling writes a one-page PDF per case whose document catalog carries the
 * mutated signature dictionary under the custom key {@code /SigProbe}, plus a
 * {@code manifest.txt} (one case name per line, in order). This probe loads
 * each {@code <case>.pdf}, reads the catalog {@code /SigProbe} entry, wraps it
 * in {@code new PDSignature(dict)} and projects a stable framed line over the
 * document's own raw bytes. Both sides read the exact same bytes on disk.
 *
 * <p>Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; br=&lt;csv|null|empty&gt; contents=&lt;hex|empty&gt; filter=&lt;v|null&gt; subfilter=&lt;v|null&gt; name=&lt;v|null&gt; reason=&lt;v|null&gt; signed=&lt;len|ERR:Exc&gt; window=&lt;hex|ERR:Exc&gt;
 * </pre>
 *
 * <p>{@code br} = {@code getByteRange()} joined by {@code ,} ("empty" for a
 * zero-length array — note that's both the absent case and a literal empty
 * COSArray). {@code contents} = {@code getContents()} as lowercase hex
 * ("empty" for a zero-length array). {@code signed} =
 * {@code getSignedContent(fileBytes).length} or {@code ERR:&lt;Exc&gt;}.
 * {@code window} = {@code getContents(fileBytes)} as lowercase hex or
 * {@code ERR:&lt;Exc&gt;}.
 */
public final class SigDictFuzzProbe {

    static PrintStream out;

    static final COSName SIG_PROBE = COSName.getPDFName("SigProbe");

    static String nz(String s) {
        return s == null ? "null" : s;
    }

    static String hex(byte[] b) {
        if (b.length == 0) {
            return "empty";
        }
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) {
            sb.append(Character.forDigit((x >> 4) & 0xF, 16));
            sb.append(Character.forDigit(x & 0xF, 16));
        }
        return sb.toString();
    }

    static String brOf(PDSignature sig) {
        int[] br = sig.getByteRange();
        if (br.length == 0) {
            return "empty";
        }
        StringBuilder sb = new StringBuilder();
        for (int j = 0; j < br.length; j++) {
            if (j > 0) {
                sb.append(',');
            }
            sb.append(br[j]);
        }
        return sb.toString();
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        PDDocument doc = null;
        try {
            byte[] fileBytes = java.nio.file.Files.readAllBytes(pdf.toPath());
            doc = Loader.loadPDF(pdf);
            PDDocumentCatalog cat = doc.getDocumentCatalog();
            COSDictionary catDict = cat.getCOSObject();
            COSBase base = catDict.getDictionaryObject(SIG_PROBE);
            COSDictionary sigDict = (COSDictionary) base;
            PDSignature sig = new PDSignature(sigDict);

            sb.append("br=").append(brOf(sig));
            sb.append(" contents=").append(hex(sig.getContents()));
            sb.append(" filter=").append(nz(sig.getFilter()));
            sb.append(" subfilter=").append(nz(sig.getSubFilter()));
            sb.append(" name=").append(nz(sig.getName()));
            sb.append(" reason=").append(nz(sig.getReason()));

            String signed;
            try {
                signed = Integer.toString(sig.getSignedContent(fileBytes).length);
            } catch (Exception e) {
                signed = "ERR:" + e.getClass().getSimpleName();
            }
            sb.append(" signed=").append(signed);

            String window;
            try {
                window = hex(sig.getContents(fileBytes));
            } catch (Exception e) {
                window = "ERR:" + e.getClass().getSimpleName();
            }
            sb.append(" window=").append(window);
        } catch (Exception e) {
            sb.append("ERR:").append(e.getClass().getSimpleName());
        } finally {
            if (doc != null) {
                try {
                    doc.close();
                } catch (Exception ignored) {
                    // best-effort close
                }
            }
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(name -> runCase(dir, name));
    }
}
