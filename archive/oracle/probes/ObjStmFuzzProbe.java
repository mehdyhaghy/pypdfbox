import java.io.File;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Differential parse-leniency fuzz probe for compressed object-stream
 * ({@code /Type /ObjStm}) decoding, Apache PDFBox 3.0.7 (wave 1516, agent C).
 *
 * <p>Complements the well-formed xref-stream / hybrid oracle suites (which pin
 * VALID compressed-object resolution) — none of those exercise the MALFORMED
 * object-stream metadata subset this probe targets:
 * <ul>
 *   <li>{@code /N} (object count): missing, zero, negative, larger- and
 *       smaller-than-actual, non-integer (a real);</li>
 *   <li>{@code /First} (byte offset of the first packed object): missing
 *       (covered by the integer-default path), zero, negative, past the end of
 *       the decoded body, and smaller than the real header;</li>
 *   <li>the leading {@code <objnum> <offset>} integer-pair header table:
 *       truncated, non-numeric, offsets out of order, an offset past the
 *       payload, and duplicate object numbers;</li>
 *   <li>the packed body truncated mid-object, and a packed object that is
 *       itself malformed;</li>
 *   <li>the {@code /Extends} chain: valid, dangling, wrong-type, cyclic;</li>
 *   <li>a wrong / missing {@code /Type}, and a {@code /Length} that
 *       under- / over-states the encoded stream body.</li>
 * </ul>
 *
 * <p><b>Driver model.</b> The pypdfbox sibling
 * (tests/pdfparser/oracle/test_objstm_fuzz_wave1516.py) hand-crafts the raw
 * PDF bytes for every case — each is a tiny but well-formed document with an
 * xref STREAM whose {@code Root} is a normal (uncompressed) catalog that
 * references {@code /Probe 4 0 R}. Object {@code 4 0} is the lone fuzz target:
 * it lives compressed inside the mutated ObjStm (object {@code 2 0}). Keeping
 * the catalog uncompressed means {@code Loader.loadPDF} always succeeds (the
 * malformation only bites at the LAZY resolution of object 4), which isolates
 * the object-stream-parser contract from the surrounding container. The sibling
 * writes every {@code <case>.pdf} plus a {@code manifest.txt} (one case name
 * per line, in order) into a directory; this probe reads the exact same bytes.
 *
 * <p><b>Output grammar</b> — exactly one line per case, in manifest order:
 * <pre>
 *   CASE &lt;name&gt; loaded=ERR exc=&lt;ExcSimpleName&gt;       (Loader.loadPDF threw)
 *   CASE &lt;name&gt; loaded=1 obj4=&lt;proj&gt;                  (load ok; object 4 resolved)
 * </pre>
 * where {@code <proj>} is a stable projection of the resolved value of object
 * {@code 4 0}:
 * <ul>
 *   <li>{@code null} — the object resolved to null / COSNull (the lenient
 *       outcome PDFBox produces when the object-stream parse fails);</li>
 *   <li>{@code dict:ProbeVal=<int|?>} — a COSDictionary; {@code <int>} is the
 *       integer value of its {@code /ProbeVal} entry (the marker the corpus
 *       packs into object 4), or {@code ?} when {@code /ProbeVal} is absent;</li>
 *   <li>{@code <SimpleName>} — any other COSBase (e.g. {@code COSInteger}
 *       when a malformed header mis-locates the payload);</li>
 *   <li>{@code ERR:<ExcSimpleName>} — resolving object 4 itself threw.</li>
 * </ul>
 *
 * <p>The sibling rebuilds the identical corpus, drives
 * {@code pypdfbox.loader.Loader.load_pdf} + {@code COSDocument.get_object_from_pool},
 * emits the identical grammar, and asserts line-for-line parity. Intentional
 * robustness divergences are pinned both-sides there with a CHANGES.md citation.
 */
public final class ObjStmFuzzProbe {

    static PrintStream out;

    static String project(COSBase b) {
        if (b == null) {
            return "null";
        }
        if (b instanceof COSObject) {
            b = ((COSObject) b).getObject();
        }
        if (b == null) {
            return "null";
        }
        if (b instanceof COSDictionary) {
            COSBase pv = ((COSDictionary) b)
                    .getDictionaryObject(COSName.getPDFName("ProbeVal"));
            if (pv == null) {
                return "dict:ProbeVal=?";
            }
            if (pv instanceof COSInteger) {
                return "dict:ProbeVal=" + ((COSInteger) pv).intValue();
            }
            return "dict:ProbeVal=" + pv;
        }
        return b.getClass().getSimpleName();
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf, "");
            COSDocument cd = doc.getDocument();
            COSObject o = cd.getObjectFromPool(new COSObjectKey(4, 0));
            String proj;
            try {
                proj = project(o.getObject());
            } catch (Throwable t) {
                proj = "ERR:" + t.getClass().getSimpleName();
            }
            sb.append("loaded=1 obj4=").append(proj);
        } catch (Throwable t) {
            sb.append("loaded=ERR exc=").append(t.getClass().getSimpleName());
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
        String[] names = new String(Files.readAllBytes(manifest.toPath()),
                StandardCharsets.UTF_8).split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(name -> runCase(dir, name));
    }
}
