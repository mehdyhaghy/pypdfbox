import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Differential parse-leniency fuzz probe for the BRUTE-FORCE OBJECT RECOVERY +
 * ROOT / PAGES RECOVERY path of Apache PDFBox 3.0.7 (wave 1532, agent D).
 *
 * <h2>How this complements {@code TrailerRebuildFuzzProbe}</h2>
 * {@code TrailerRebuildFuzzProbe} (wave 1517) drives the TRAILER /
 * {@code startxref} rebuild candidate selection ({@code rebuildTrailer},
 * {@code /Info} / {@code /Encrypt} / {@code /ID} copy-through, the located-xref
 * vs full-rebuild branch). This probe targets the DISTINCT first half of the
 * recovery machinery: the raw byte scan that finds {@code n g obj} object
 * headers ({@code BruteForceParser.bfSearchForObjects}), how it copes with
 * malformed / abutting / at-EOF headers and garbage between objects, the
 * duplicate-definition "last wins" precedence verified by recovered CONTENT,
 * and the {@code /Root} (via {@code /Type /Catalog}) + {@code /Pages} +
 * {@code checkPages} recovery that {@code initialParse} performs on the rebuilt
 * document. Upstream: {@code COSParser.bfSearchForObjects} /
 * {@code BruteForceParser.bfSearchForObjStreams} /
 * {@code BruteForceParser.rebuildTrailer} / {@code COSParser.isCatalog} /
 * {@code PDFParser.initialParse} → {@code checkPages}.
 *
 * <h2>Surface exercised</h2>
 * <ul>
 *   <li>Object-header scan robustness: object header at EOF (no trailing
 *       {@code endobj}), header preceded/followed only by garbage, abutting
 *       integer literals before the object number, {@code obj} as a substring
 *       of {@code endobj} (must NOT be picked up).</li>
 *   <li>Entirely header-less file (header bytes + freeform text, zero
 *       {@code n g obj}) — must FAIL, not recover an empty document.</li>
 *   <li>Duplicate {@code n g obj} for the same (num,gen): the LAST definition
 *       wins; verified by which catalog's recovered /Pages target survives.</li>
 *   <li>{@code /Root} recovery: catalog reachable only via the brute-force
 *       scan, catalog WITHOUT {@code /Type /Catalog} (no root candidate →
 *       fail), catalog whose {@code /Pages} points at a missing object.</li>
 *   <li>{@code /Pages} recovery + {@code checkPages}: a /Kids entry pointing at
 *       a missing/truncated page is pruned and /Count rewritten; a page tree
 *       with a valid kid recovers the page.</li>
 *   <li>Object stream content recovery: a catalog packed in {@code /Type
 *       /ObjStm} whose members must be parsed to find /Root, plus a corrupt
 *       ObjStm (bad /First) that yields nothing.</li>
 *   <li>Garbage interleaved between otherwise-valid object definitions.</li>
 * </ul>
 *
 * <h2>Input grammar (file-driven, SAME bytes drive both sides)</h2>
 * The pypdfbox sibling
 * (tests/pdfparser/oracle/test_brute_force_recovery_fuzz_wave1532.py)
 * hand-crafts the raw PDF bytes per case, writes each {@code <case>.pdf} into a
 * directory plus a {@code manifest.txt} (one case name per line, in order).
 * This probe reads the manifest and loads each {@code <case>.pdf} with the
 * empty password.
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
 * in the COS xref table — the size of the recovered object set.
 *
 * <p>Exception CLASS names differ across runtimes (Java {@code IOException}
 * family vs pypdfbox {@code PDFParseError} // {@code OSError}); the sibling
 * compares the {@code ERR} arm on the THROW BOOLEAN only and asserts the
 * success-arm fields verbatim. Defensible robustness divergences are pinned
 * both-sides with a CHANGES.md citation.
 */
public final class BruteForceRecoveryFuzzProbe {

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
