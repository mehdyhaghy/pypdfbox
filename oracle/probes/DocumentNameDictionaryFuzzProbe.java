import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDocumentNameDictionary;

/**
 * Differential fuzz probe for {@link PDDocumentNameDictionary} accessor
 * leniency over a MALFORMED catalog {@code /Names} sub-dictionary, Apache
 * PDFBox 3.0.7 (wave 1529, agent E).
 *
 * <p>Apache PDFBox 3.0.7 only exposes three sub-entry accessors on this class —
 * {@code getDests}, {@code getEmbeddedFiles}, {@code getJavaScript} — plus
 * {@code getCOSObject}. (pypdfbox additionally surfaces getPages / getTemplates
 * / getIDS / getURLS / getRenditions / getAP as forward-looking extensions;
 * those have no upstream counterpart and are exercised by the value-based unit
 * suite, not this oracle.) Each accessor reads its sub-entry via
 * {@code COSDictionary.getCOSDictionary(KEY)} — returning a wrapped name-tree
 * node when the value resolves to a {@code COSDictionary}, and {@code null}
 * otherwise (entry absent, or present as a wrong-typed name / string / array /
 * number). {@code getDests} additionally falls back to the catalog's legacy
 * direct {@code /Dests} entry when {@code /Names /Dests} is absent or
 * wrong-typed, wrapping that fallback as a {@code PDDestinationNameTreeNode}
 * (NOT the flat-dict wrapper).
 *
 * <p>Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/oracle/test_document_name_dictionary_fuzz_wave1529.py) writes a
 * deterministic corpus of one-page PDFs whose catalog {@code /Names} sub-dict IS
 * the fuzzed dict (and, for the catalog-fallback cases, a direct catalog
 * {@code /Dests}), plus a {@code manifest.txt} (one case name per line, in
 * order) into a tmp dir. This probe loads each {@code <case>.pdf}, resolves
 * {@code catalog.getNames()}, and projects a stable framed line. Both sides read
 * the exact same bytes on disk.
 *
 * <p>Line grammar (one per case, manifest order):
 *
 * <pre>
 *   CASE &lt;name&gt; names=&lt;cls|null|ERR:X&gt; dests=&lt;cls|null|ERR:X&gt; embed=&lt;cls|null|ERR:X&gt; js=&lt;cls|null|ERR:X&gt; cos=&lt;int|null|ERR:X&gt;
 * </pre>
 *
 * <p>{@code names} is the {@code PDDocumentNameDictionary} wrapper class (or
 * "null" when {@code /Names} is absent / non-dict, in which case every other
 * cell is "null" because no wrapper exists). {@code cos} is the entry count of
 * {@code getNames().getCOSObject()} (round-trip check). All wrapper cells report
 * the resolved node's simple class name, "null", or "ERR:&lt;ExcSimpleName&gt;".
 */
public final class DocumentNameDictionaryFuzzProbe {

    static PrintStream out;

    static String exc(Exception e) {
        return "ERR:" + e.getClass().getSimpleName();
    }

    static String cls(Object o) {
        return o == null ? "null" : o.getClass().getSimpleName();
    }

    static String dests(PDDocumentNameDictionary nd) {
        try {
            return cls(nd.getDests());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String embed(PDDocumentNameDictionary nd) {
        try {
            return cls(nd.getEmbeddedFiles());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String js(PDDocumentNameDictionary nd) {
        try {
            return cls(nd.getJavaScript());
        } catch (Exception e) {
            return exc(e);
        }
    }

    static String cos(PDDocumentNameDictionary nd) {
        try {
            return nd.getCOSObject() == null
                    ? "null"
                    : Integer.toString(nd.getCOSObject().size());
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
            PDDocumentCatalog cat = doc.getDocumentCatalog();
            PDDocumentNameDictionary nd = cat.getNames();
            if (nd == null) {
                sb.append("names=null dests=null embed=null js=null cos=null");
            } else {
                sb.append("names=").append(cls(nd));
                sb.append(" dests=").append(dests(nd));
                sb.append(" embed=").append(embed(nd));
                sb.append(" js=").append(js(nd));
                sb.append(" cos=").append(cos(nd));
            }
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
