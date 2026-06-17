import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import java.util.Calendar;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.interactive.digitalsignature.PDSignature;

/**
 * Differential fuzz probe for {@link PDSignature} signature-dictionary IDENTITY
 * + DATE accessors, Apache PDFBox 3.0.7 (wave 1551, agent E). READ / PARSE path
 * only — no cryptographic verification.
 *
 * <p>Deliberately disjoint from {@code SigDictFuzzProbe} (wave 1517), which
 * already pinned {@code getByteRange} / {@code getContents} /
 * {@code getSignedContent(byte[])} / {@code getContents(byte[])} and the
 * filter/subfilter/name/reason name-vs-string corners. This probe targets the
 * accessors that wave 1517 did NOT cover and adds the date-parse path:
 * <ul>
 *   <li>{@code getLocation()} / {@code getContactInfo()} — string vs name
 *       storage, wrong types, absent. (Both use {@code COSDictionary.getString}
 *       upstream, so a {@code COSName} value yields {@code null}.)</li>
 *   <li>{@code getFilter()} / {@code getSubFilter()} — wrong types
 *       ({@code COSInteger}, {@code COSArray}), name vs string, absent. (Both
 *       use {@code getNameAsString}, so a name OR a string coerces to text and
 *       a non-name/non-string yields {@code null}.)</li>
 *   <li>{@code getName()} / {@code getReason()} — name-stored (yields
 *       {@code null} since {@code getString} ignores names), array, integer.</li>
 *   <li>{@code getSignDate()} — the {@code DateConverter.toCalendar} parse over
 *       well-formed, partial, malformed, name-stored, wrong-type and 60-second
 *       {@code /M} values; projected as the {@code Calendar.getTimeInMillis()}
 *       epoch-ms (UTC) or {@code null}.</li>
 * </ul>
 *
 * <p>File-driven, mirroring {@code SigDictFuzzProbe}: the pypdfbox sibling
 * writes a one-page PDF per case whose document catalog carries the mutated
 * signature dictionary under the custom key {@code /SigProbe}, plus a
 * {@code manifest.txt} (one case name per line, in order). This probe loads each
 * {@code <case>.pdf}, reads the catalog {@code /SigProbe} entry, wraps it in
 * {@code new PDSignature(dict)} and projects a stable framed line.
 *
 * <p>Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; filter=&lt;v|null&gt; subfilter=&lt;v|null&gt; name=&lt;v|null&gt; location=&lt;v|null&gt; reason=&lt;v|null&gt; contact=&lt;v|null&gt; signdate=&lt;epochMs|null|ERR:Exc&gt;
 * </pre>
 */
public final class SignatureDictFuzzProbe {

    static PrintStream out;

    static final COSName SIG_PROBE = COSName.getPDFName("SigProbe");

    static String nz(String s) {
        return s == null ? "null" : s;
    }

    static String dateOf(PDSignature sig) {
        try {
            Calendar cal = sig.getSignDate();
            if (cal == null) {
                return "null";
            }
            return Long.toString(cal.getTimeInMillis());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            PDDocumentCatalog cat = doc.getDocumentCatalog();
            COSDictionary catDict = cat.getCOSObject();
            COSBase base = catDict.getDictionaryObject(SIG_PROBE);
            COSDictionary sigDict = (COSDictionary) base;
            PDSignature sig = new PDSignature(sigDict);

            sb.append("filter=").append(nz(sig.getFilter()));
            sb.append(" subfilter=").append(nz(sig.getSubFilter()));
            sb.append(" name=").append(nz(sig.getName()));
            sb.append(" location=").append(nz(sig.getLocation()));
            sb.append(" reason=").append(nz(sig.getReason()));
            sb.append(" contact=").append(nz(sig.getContactInfo()));
            sb.append(" signdate=").append(dateOf(sig));
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
