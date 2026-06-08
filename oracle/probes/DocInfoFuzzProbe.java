import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import java.util.Calendar;
import java.util.Set;
import java.util.TreeSet;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;

/**
 * Differential fuzz probe for {@link PDDocumentInformation} (the trailer
 * {@code /Info} dictionary) accessor leniency over a MALFORMED Info dict,
 * Apache PDFBox 3.0.7 (wave 1516, agent E).
 *
 * <p>Complements the well-formed info-accessor oracle suite
 * ({@code test_info_accessor_round_trip_oracle}, {@code test_info_xmp_oracle},
 * {@code test_metadata_oracle}) — none of which exercise the mistyped /
 * malformed {@code /Info} subset this probe targets:
 *
 * <ul>
 *   <li>{@code /Title} {@code /Author} {@code /Subject} {@code /Keywords}
 *       {@code /Creator} {@code /Producer} as a string (spec form) vs a name
 *       vs a wrong type (number / array / dict) vs missing —
 *       {@code getTitle()} &amp;c. delegate to {@code COSDictionary.getString},
 *       which accepts ONLY a COSString and returns null for a name / number /
 *       array / dict / absent entry;</li>
 *   <li>{@code /CreationDate} {@code /ModDate} as a valid PDF date string
 *       ({@code D:20240101120000+05'00'}), a partial date, a malformed date,
 *       a non-string (number / name), and missing — {@code getCreationDate()}
 *       / {@code getModificationDate()} delegate to
 *       {@code COSDictionary.getDate} -&gt; {@code DateConverter.toCalendar}
 *       (lenient parse; null for a non-COSString or an unparseable date);</li>
 *   <li>{@code /Trapped} name enum ({@code /True} / {@code /False} /
 *       {@code /Unknown} / unknown name / as a COSString / wrong type /
 *       missing) — {@code getTrapped()} delegates to
 *       {@code COSDictionary.getNameAsString}, which accepts a COSName OR a
 *       COSString and returns null otherwise;</li>
 *   <li>custom metadata ({@code getCustomMetadataValue} /
 *       {@code getMetadataKeys}) including a custom key colliding with a
 *       standard one and a non-string custom value.</li>
 * </ul>
 *
 * <p>Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/oracle/test_doc_info_fuzz_wave1516.py) writes a deterministic
 * corpus of one-page PDFs whose trailer {@code /Info} dictionary IS the fuzzed
 * dict, plus a {@code manifest.txt} (one case name per line, in order), into a
 * tmp dir. This probe loads each {@code <case>.pdf}, resolves the document
 * information, and projects a stable framed line. Both sides read the exact
 * same bytes on disk.
 *
 * <p>Line grammar (one per case, manifest order):
 *
 * <pre>
 *   CASE &lt;name&gt; title=&lt;str|null|ERR:X&gt; author=&lt;str|null|ERR:X&gt; producer=&lt;str|null|ERR:X&gt; creationdate=&lt;epochMillis|null|ERR:X&gt; moddate=&lt;epochMillis|null|ERR:X&gt; trapped=&lt;str|null|ERR:X&gt; customkeys=&lt;k1,k2,...|-&gt; custom_Foo=&lt;str|null|ERR:X&gt; custom_Title=&lt;str|null|ERR:X&gt;
 * </pre>
 *
 * <p>{@code creationdate} / {@code moddate} report
 * {@code getCreationDate().getTimeInMillis()} (UTC epoch millis) — directly
 * comparable to the Python sibling's timezone-aware
 * {@code datetime.timestamp() * 1000}. {@code customkeys} is the sorted
 * {@code getMetadataKeys()} (a TreeSet, already sorted) joined by commas, or
 * {@code -} when empty. {@code custom_Foo} / {@code custom_Title} probe
 * {@code getCustomMetadataValue} for a non-standard key and for a standard key
 * name routed through the custom accessor (which is just {@code getString}, so
 * a standard COSString collides identically).
 */
public final class DocInfoFuzzProbe {

    static PrintStream out;

    static String exc(Exception e) {
        return "ERR:" + e.getClass().getSimpleName();
    }

    static String str(String s) {
        return s == null ? "null" : s;
    }

    static String title(PDDocumentInformation info) {
        try {
            return str(info.getTitle());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String author(PDDocumentInformation info) {
        try {
            return str(info.getAuthor());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String producer(PDDocumentInformation info) {
        try {
            return str(info.getProducer());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String creationDate(PDDocumentInformation info) {
        try {
            Calendar c = info.getCreationDate();
            return c == null ? "null" : Long.toString(c.getTimeInMillis());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String modDate(PDDocumentInformation info) {
        try {
            Calendar c = info.getModificationDate();
            return c == null ? "null" : Long.toString(c.getTimeInMillis());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String trapped(PDDocumentInformation info) {
        try {
            return str(info.getTrapped());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String customKeys(PDDocumentInformation info) {
        try {
            Set<String> keys = new TreeSet<>(info.getMetadataKeys());
            if (keys.isEmpty()) {
                return "-";
            }
            return String.join(",", keys);
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String custom(PDDocumentInformation info, String field) {
        try {
            return str(info.getCustomMetadataValue(field));
        } catch (Exception e) {
            return exc(e);
        }
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            PDDocumentInformation info = doc.getDocumentInformation();
            sb.append("title=").append(title(info));
            sb.append(" author=").append(author(info));
            sb.append(" producer=").append(producer(info));
            sb.append(" creationdate=").append(creationDate(info));
            sb.append(" moddate=").append(modDate(info));
            sb.append(" trapped=").append(trapped(info));
            sb.append(" customkeys=").append(customKeys(info));
            sb.append(" custom_Foo=").append(custom(info, "Foo"));
            sb.append(" custom_Title=").append(custom(info, "Title"));
        } catch (Exception e) {
            sb.append("LOAD:").append(e.getClass().getSimpleName());
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
