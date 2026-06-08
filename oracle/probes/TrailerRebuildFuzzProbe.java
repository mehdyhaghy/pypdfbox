import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Differential parse-leniency fuzz probe for the TRAILER / {@code startxref}
 * RECOVERY and BRUTE-FORCE REBUILD path, Apache PDFBox 3.0.7 (wave 1517,
 * agent B).
 *
 * <h2>How this complements {@code XrefTableFuzzProbe}</h2>
 * {@code XrefTableFuzzProbe} (wave 1516) drives the classic {@code xref}
 * keyword table parse + its subsection / 20-byte-entry framing edge cases and
 * the {@code /Prev} chain. This probe targets the DISTINCT recovery machinery
 * that fires when the cross-reference data is unusable and PDFBox must rebuild
 * the xref + trailer from a raw object scan:
 * {@code COSParser.retrieveTrailer} → {@code BruteForceParser.rebuildTrailer},
 * {@code bfSearchForObjects}, {@code bfSearchForObjStreams},
 * {@code searchForTrailerItems}, {@code bfSearchForXRef}, and
 * {@code parseStartXref}.
 *
 * <h2>Surface exercised</h2>
 * <ul>
 *   <li>FULL brute-force rebuild: {@code startxref} missing/garbage with NO
 *       parseable xref section — recovery must scan {@code n g obj} headers,
 *       relocate the {@code /Type /Catalog} as {@code /Root}, and derive
 *       {@code /Size} = max(objnum)+1.</li>
 *   <li>{@code rebuildTrailer} candidate selection: {@code /Info} via info
 *       keys, {@code /Encrypt} / {@code /ID} copy-through, FDF root (no
 *       {@code /Type} but {@code /FDF} key), catalog vs info disambiguation,
 *       duplicate {@code n g obj} (later wins).</li>
 *   <li>Catalog packed inside an {@code /Type /ObjStm} object stream (lost
 *       xref-stream trailer) — recovered via {@code bfSearchForObjStreams}.</li>
 *   <li>Trailer dictionary corruption: {@code trailer} keyword absent, the
 *       dict unterminated, two {@code trailer} keywords, leading garbage that
 *       shoves the {@code %PDF-} header past byte 0.</li>
 *   <li>{@code startxref} recovery: points at whitespace, points into an
 *       object body, points one byte off the {@code xref} keyword, a valid
 *       table reachable only by {@code bfSearchForXRef}.</li>
 *   <li>No recoverable object at all (header + trailing garbage) — must FAIL,
 *       not silently yield an empty document.</li>
 * </ul>
 *
 * <h2>Input grammar (file-driven, SAME bytes drive both sides)</h2>
 * The pypdfbox sibling
 * (tests/pdfparser/oracle/test_trailer_rebuild_fuzz_wave1517.py) hand-crafts
 * the raw PDF bytes per case, writes each {@code <case>.pdf} into a directory
 * plus a {@code manifest.txt} (one case name per line, in order). This probe
 * reads the manifest and loads each {@code <case>.pdf} with the empty password.
 *
 * <h2>Output grammar (one line per case, manifest order)</h2>
 * <pre>
 *   CASE &lt;name&gt; loaded=&lt;1|ERR:&lt;ExcSimpleName&gt;&gt; pages=&lt;n|?&gt; root=&lt;present|absent|?&gt; nobj=&lt;count|?&gt;
 * </pre>
 * {@code loaded=ERR:&lt;X&gt;} means {@code Loader.loadPDF} threw exception class
 * X (then pages/root/nobj are all {@code ?}). On success {@code loaded=1};
 * {@code pages} is {@code getNumberOfPages()} (or {@code ?} if that throws),
 * {@code root} is {@code present} when the catalog resolves else {@code absent}
 * (or {@code ?} on throw), and {@code nobj} is the count of resolved object keys
 * in the COS xref table — the size of the recovered/parsed object set.
 *
 * <p>Exception CLASS names differ across runtimes (Java {@code IOException}
 * family vs pypdfbox {@code PDFParseError} // {@code OSError}); the sibling
 * compares the {@code ERR} arm on the THROW BOOLEAN only and asserts the
 * success-arm fields verbatim. Defensible robustness divergences are pinned
 * both-sides with a CHANGES.md citation.
 */
public final class TrailerRebuildFuzzProbe {

    static PrintStream out;

    static String pages(PDDocument doc) {
        try {
            return Integer.toString(doc.getNumberOfPages());
        } catch (Throwable t) {
            return "?";
        }
    }

    static String root(PDDocument doc) {
        try {
            return doc.getDocumentCatalog() != null ? "present" : "absent";
        } catch (Throwable t) {
            return "?";
        }
    }

    static String nobj(PDDocument doc) {
        try {
            COSDocument cos = doc.getDocument();
            int n = 0;
            for (COSObjectKey ignored : cos.getXrefTable().keySet()) {
                n++;
            }
            return Integer.toString(n);
        } catch (Throwable t) {
            return "?";
        }
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf, "");
            sb.append("loaded=1");
            sb.append(" pages=").append(pages(doc));
            sb.append(" root=").append(root(doc));
            sb.append(" nobj=").append(nobj(doc));
        } catch (Throwable t) {
            sb.append("loaded=ERR:").append(t.getClass().getSimpleName());
            sb.append(" pages=? root=? nobj=?");
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
