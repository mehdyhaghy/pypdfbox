import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdfparser.PDFXrefStreamParser;
import org.apache.pdfbox.pdfparser.XrefTrailerResolver;
import org.apache.pdfbox.pdfparser.XrefTrailerResolver.XRefType;

/**
 * Differential parse-leniency fuzz probe for the PDF 1.5+ cross-reference
 * STREAM decoder {@code org.apache.pdfbox.pdfparser.PDFXrefStreamParser},
 * Apache PDFBox 3.0.7 (wave 1512, agent D).
 *
 * Complements the existing well-formed xref-stream oracle suite
 * (XrefWFieldsProbe / XrefIndexSubsectionsProbe / XRefStreamTrailerProbe /
 * HybridXrefProbe — all value-pinned on VALID streams) and the wave-1503
 * file-structure mutation fuzz (MutationFuzzProbe — which mutates the PDF
 * container, not the xref-stream /W//Index//Size geometry vs the decoded body
 * length). None of those exercise the MALFORMED /W//Index//Size + truncated-
 * body subset this probe targets: wrong-arity /W, negative or zero widths,
 * the PDFBOX-6037 sum&gt;20 cap, /W[0]==0 type-defaulting, odd/empty /Index,
 * missing /Index (default [0 /Size]), /Index counts that overrun the decoded
 * body, free (type 0) and unknown (type&gt;=3) entry types, generation //
 * stream-index recovery, and a body shorter than W*entryCount.
 *
 * Driven by a single input file (so the SAME bytes drive both sides). File
 * grammar — one case per line, TAB-separated:
 *   {@code <name> \t <W:comma-ints-or-"-"> \t <Index:comma-ints-or-"-"> \t
 *          <Size:int-or-"-"> \t <base64-of-body-bytes>}
 * A {@code "-"} for /W omits the /W key entirely; {@code "-"} for /Index omits
 * /Index; {@code "-"} for Size omits /Size. Blank lines and lines starting
 * with {@code #} are ignored.
 *
 * Output grammar — exactly one line per case, in input order:
 *   {@code CASE <name> EXC <ExcSimpleName>}        (constructor or parse threw)
 *   {@code CASE <name> OK <entryToken>;<entryToken>;...}   (parse succeeded)
 * where each {@code entryToken} (from the resolver's merged xref table) is
 *   {@code <objNum>,<gen>,<streamIndex>,<offset>}
 * Tokens are sorted ascending by (objNum, gen, streamIndex). {@code OK -}
 * means the parse produced zero in-use entries. PDFBox's
 * {@code getXrefTable()} (a {@code Map<COSObjectKey,Long>}) only holds in-use
 * (type 1) and compressed (type 2) entries — free (type 0) entries are never
 * inserted — so this projection captures exactly the surviving recovery set.
 *
 * The pypdfbox sibling
 * (tests/pdfparser/oracle/test_xref_stream_fuzz_wave1512.py) rebuilds the
 * identical corpus, drives pypdfbox.pdfparser.PDFXrefStreamParser through the
 * same XrefTrailerResolver, emits the identical grammar, and asserts
 * line-for-line parity. Intentional robustness divergences are pinned both-
 * sides there with a CHANGES.md citation.
 */
public final class XrefStreamFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        List<String> lines = Files.readAllLines(
                Paths.get(args[0]), StandardCharsets.UTF_8);
        for (String line : lines) {
            if (line.isEmpty() || line.charAt(0) == '#') {
                continue;
            }
            String[] parts = line.split("\t", -1);
            String name = parts[0];
            out.println("CASE " + name + " "
                    + run(parts[1], parts[2], parts[3], parts[4]));
        }
    }

    private static COSArray intArray(String spec) {
        COSArray a = new COSArray();
        for (String tok : spec.split(",")) {
            a.add(COSInteger.get(Long.parseLong(tok.trim())));
        }
        return a;
    }

    private static String run(String wSpec, String indexSpec, String sizeSpec,
            String bodyB64) {
        COSDocument doc = new COSDocument();
        COSStream stream = doc.createCOSStream();
        try {
            if (!"-".equals(wSpec)) {
                stream.setItem(COSName.W, intArray(wSpec));
            }
            if (!"-".equals(indexSpec)) {
                stream.setItem(COSName.INDEX, intArray(indexSpec));
            }
            if (!"-".equals(sizeSpec)) {
                stream.setInt(COSName.SIZE, Integer.parseInt(sizeSpec));
            }
            byte[] body = Base64.getDecoder().decode(bodyB64);
            try (OutputStream os = stream.createOutputStream()) {
                os.write(body);
            }

            XrefTrailerResolver resolver = new XrefTrailerResolver();
            resolver.nextXrefObj(0L, XRefType.STREAM);
            PDFXrefStreamParser parser = new PDFXrefStreamParser(stream, doc);
            parser.parse(resolver);
            // getXrefTable() reads resolvedXrefTrailer, which is null until
            // setStartxref resolves the section registered at byte-pos 0 —
            // mirror the real load path's resolve step.
            resolver.setStartxref(0L);
            return "OK " + dump(resolver.getXrefTable());
        } catch (Throwable t) {
            return "EXC " + t.getClass().getSimpleName();
        } finally {
            try {
                doc.close();
            } catch (Exception ignore) {
                // best effort
            }
        }
    }

    private static String dump(Map<COSObjectKey, Long> table) {
        if (table == null || table.isEmpty()) {
            return "-";
        }
        List<long[]> rows = new ArrayList<>();
        for (Map.Entry<COSObjectKey, Long> e : table.entrySet()) {
            COSObjectKey k = e.getKey();
            rows.add(new long[] {
                    k.getNumber(), k.getGeneration(), k.getStreamIndex(),
                    e.getValue() });
        }
        rows.sort((x, y) -> {
            for (int i = 0; i < 3; i++) {
                int c = Long.compare(x[i], y[i]);
                if (c != 0) {
                    return c;
                }
            }
            return 0;
        });
        List<String> tokens = new ArrayList<>();
        for (long[] r : rows) {
            tokens.add(r[0] + "," + r[1] + "," + r[2] + "," + r[3]);
        }
        Collections.sort(tokens);
        return String.join(";", tokens);
    }
}
