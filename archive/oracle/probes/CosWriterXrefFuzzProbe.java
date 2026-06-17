import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.pdfwriter.COSWriter;

/**
 * Live oracle probe: the EXACT bytes / structure Apache PDFBox's {@code COSWriter}
 * emits for the CROSS-REFERENCE {@code xref} TABLE + {@code trailer} dictionary +
 * {@code startxref} / {@code %%EOF} epilogue when saving a {@code COSDocument}
 * through the CLASSIC (non-stream) write path
 * ({@code doWriteXRefTable} / {@code doWriteTrailer}).
 *
 * <p>This complements {@code CosWriterObjectFuzzProbe} (wave 1528, per-OBJECT
 * {@code visitFromXxx} serialization). Here the angle is the xref-table /
 * trailer ASSEMBLY: the subsection grouping of contiguous object-number runs,
 * the mandatory free-list head ({@code 0000000000 65535 f}), the fixed 20-byte
 * entry rows ({@code offset%010d gen%05d " n"/" f"}), {@code /Size} =
 * (max object number + 1), and the trailer keys ({@code /Root} / {@code /Info} /
 * {@code /ID} / {@code /Prev}).
 *
 * <p>Each case builds a small {@code COSDocument} from raw COS primitives (using
 * {@code COSObject(base, COSObjectKey)} so explicit, possibly NON-CONTIGUOUS
 * object numbers are preserved by the writer), drives it through a fresh
 * {@code COSWriter} over a {@code ByteArrayOutputStream}, then projects the
 * normalized xref+trailer region. {@code /ID} synthesis is time/random based, so
 * we project only the PRESENCE of {@code /ID} (not its bytes); everything else
 * (subsection ranges, every entry's {@code gen flag}, the 20-byte row width, the
 * trailer key set, the {@code /Size} value) is byte/structure deterministic.
 *
 * <p>Output grammar — one line per case:
 * <pre>
 *   CASE &lt;name&gt; xref=&lt;1|0&gt; ranges=&lt;f:c,f:c,...&gt; entries=&lt;g/flag,...&gt; rowlen=&lt;n&gt; size=&lt;n&gt; root=&lt;0|1&gt; info=&lt;0|1&gt; id=&lt;0|1&gt; prev=&lt;0|1&gt; startxref=&lt;1|0&gt; eof=&lt;1|0&gt;
 * </pre>
 * The pypdfbox sibling builds the equivalent document with its own COSWriter and
 * asserts byte/structure-identical projections.
 *
 * <p>Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; CosWriterXrefFuzzProbe
 */
public final class CosWriterXrefFuzzProbe {

    static PrintStream out;

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---- minimal: catalog only, contiguous (1) ----
        emit("min_catalog", buildContiguous(1));

        // ---- contiguous small graph (catalog + pages + page) ----
        emit("contig_3", buildContiguous(3));
        emit("contig_5", buildContiguous(5));

        // ---- empty document: trailer only, no indirect objects ----
        emitEmpty("empty_doc");

        // ---- non-contiguous object numbers -> xref subsection splitting ----
        // numbers {1,2,3,7,8,10}: ranges 0/4 (with free head), then gaps
        emit("noncontig_gap", buildExplicit(new int[]{1, 2, 3, 7, 8, 10}));
        // numbers {5,6,7}: a single late run -> object 0..4 are all free
        emit("noncontig_late", buildExplicit(new int[]{5, 6, 7}));
        // single sparse object far out: {1, 50}
        emit("noncontig_far", buildExplicit(new int[]{1, 50}));
        // every-other: {1,3,5,7} -> many subsections
        emit("noncontig_alt", buildExplicit(new int[]{1, 3, 5, 7}));

        // ---- trailer with /Info present ----
        emit("with_info", buildWithInfo());

        // ---- non-zero generation entry ----
        emit("gen_nonzero", buildGenNonzero());
    }

    // ---- builders ----

    /** Build a doc with `n` indirect dicts numbered 1..n; obj 1 = catalog (Root). */
    static COSDocument buildContiguous(int n) {
        int[] nums = new int[n];
        for (int i = 0; i < n; i++) {
            nums[i] = i + 1;
        }
        return buildExplicit(nums);
    }

    /**
     * Build a doc whose indirect objects carry exactly the given object numbers
     * (generation 0). The FIRST number is wired as /Root (a /Catalog dict); the
     * rest are simple dicts referenced from an array on the catalog so the
     * writer's reachability walk emits every one.
     */
    static COSDocument buildExplicit(int[] nums) {
        COSDocument doc = new COSDocument();
        COSDictionary trailer = new COSDictionary();

        COSDictionary catalog = new COSDictionary();
        catalog.setItem(COSName.TYPE, COSName.getPDFName("Catalog"));
        COSObject rootObj =
                new COSObject(catalog, new COSObjectKey(nums[0], 0));

        // Hang the remaining objects off an array on the catalog so they are
        // reachable from /Root and get emitted.
        COSArray kids = new COSArray();
        for (int i = 1; i < nums.length; i++) {
            COSDictionary d = new COSDictionary();
            d.setItem(COSName.getPDFName("N"), COSInteger.get(nums[i]));
            COSObject o = new COSObject(d, new COSObjectKey(nums[i], 0));
            kids.add(o);
        }
        if (kids.size() > 0) {
            catalog.setItem(COSName.getPDFName("Kids"), kids);
        }

        trailer.setItem(COSName.ROOT, rootObj);
        doc.setTrailer(trailer);
        return doc;
    }

    /** Empty document: a trailer with no /Root and no indirect objects. */
    static void emitEmpty(String name) throws Exception {
        COSDocument doc = new COSDocument();
        doc.setTrailer(new COSDictionary());
        emit(name, doc);
    }

    /** Catalog + an /Info indirect dict in the trailer. */
    static COSDocument buildWithInfo() {
        COSDocument doc = new COSDocument();
        COSDictionary trailer = new COSDictionary();

        COSDictionary catalog = new COSDictionary();
        catalog.setItem(COSName.TYPE, COSName.getPDFName("Catalog"));
        COSObject rootObj = new COSObject(catalog, new COSObjectKey(1, 0));

        COSDictionary info = new COSDictionary();
        info.setItem(COSName.getPDFName("Producer"),
                new org.apache.pdfbox.cos.COSString("probe"));
        COSObject infoObj = new COSObject(info, new COSObjectKey(2, 0));

        trailer.setItem(COSName.ROOT, rootObj);
        trailer.setItem(COSName.getPDFName("Info"), infoObj);
        doc.setTrailer(trailer);
        return doc;
    }

    /** Catalog at (1,0) referencing a dict at (2,3) — non-zero generation. */
    static COSDocument buildGenNonzero() {
        COSDocument doc = new COSDocument();
        COSDictionary trailer = new COSDictionary();

        COSDictionary catalog = new COSDictionary();
        catalog.setItem(COSName.TYPE, COSName.getPDFName("Catalog"));
        COSObject rootObj = new COSObject(catalog, new COSObjectKey(1, 0));

        COSDictionary d = new COSDictionary();
        d.setItem(COSName.getPDFName("N"), COSInteger.get(2));
        COSObject o = new COSObject(d, new COSObjectKey(2, 3));
        catalog.setItem(COSName.getPDFName("Ref"), o);

        trailer.setItem(COSName.ROOT, rootObj);
        doc.setTrailer(trailer);
        return doc;
    }

    // ---- save + project ----

    static void emit(String name, COSDocument doc) throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter w = new COSWriter(baos);
        w.write(doc);
        byte[] full = baos.toByteArray();
        out.println(project(name, full));
        doc.close();
    }

    static String project(String name, byte[] full) {
        String s = new String(full, java.nio.charset.StandardCharsets.ISO_8859_1);

        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name);

        // Locate the LAST `xref` keyword line (classic table). It must be a
        // line of its own: preceded by EOL and followed by EOL.
        int xrefKw = lastXrefKeyword(s);
        boolean hasXref = xrefKw >= 0;
        sb.append(" xref=").append(hasXref ? 1 : 0);

        int trailerKw = s.lastIndexOf("trailer");
        int startxrefKw = s.lastIndexOf("startxref");
        int eofKw = s.lastIndexOf("%%EOF");

        // Parse the xref table body (between xref keyword and trailer keyword).
        String ranges = "";
        String entries = "";
        int rowlen = -1;
        if (hasXref && trailerKw > xrefKw) {
            int bodyStart = s.indexOf('\n', xrefKw) + 1;
            String body = s.substring(bodyStart, trailerKw);
            String[] lines = body.split("\n", -1);
            StringBuilder rsb = new StringBuilder();
            StringBuilder esb = new StringBuilder();
            for (String raw : lines) {
                String line = raw;
                // strip a trailing CR (rows end CRLF; subsection headers EOL)
                if (line.endsWith("\r")) {
                    line = line.substring(0, line.length() - 1);
                }
                if (line.isEmpty()) {
                    continue;
                }
                if (isSubsectionHeader(line)) {
                    String[] p = line.trim().split("\\s+");
                    if (rsb.length() > 0) {
                        rsb.append(',');
                    }
                    rsb.append(p[0]).append(':').append(p[1]);
                } else if (isEntryRow(line)) {
                    // 20-byte fixed rows: offset(10) sp gen(5) sp flag, +CRLF.
                    // measure the raw row length (incl trailing CR we stripped)
                    int len = raw.length() + 1; // +1 for the '\n' delimiter
                    if (rowlen < 0) {
                        rowlen = len;
                    }
                    String[] p = line.trim().split("\\s+");
                    String gen = p[1];
                    String flag = p[2];
                    if (esb.length() > 0) {
                        esb.append(',');
                    }
                    esb.append(Integer.parseInt(gen)).append('/').append(flag);
                }
            }
            ranges = rsb.toString();
            entries = esb.toString();
        }
        sb.append(" ranges=").append(ranges);
        sb.append(" entries=").append(entries);
        sb.append(" rowlen=").append(rowlen);

        // Trailer key projection.
        int size = -1;
        boolean root = false;
        boolean info = false;
        boolean id = false;
        boolean prev = false;
        if (trailerKw >= 0) {
            int trailerEnd = startxrefKw > trailerKw ? startxrefKw : s.length();
            String td = s.substring(trailerKw, trailerEnd);
            size = intValueOf(td, "/Size");
            root = td.contains("/Root");
            info = td.contains("/Info");
            id = td.contains("/ID");
            prev = td.contains("/Prev");
        }
        sb.append(" size=").append(size);
        sb.append(" root=").append(root ? 1 : 0);
        sb.append(" info=").append(info ? 1 : 0);
        sb.append(" id=").append(id ? 1 : 0);
        sb.append(" prev=").append(prev ? 1 : 0);
        sb.append(" startxref=").append(startxrefKw >= 0 ? 1 : 0);
        sb.append(" eof=").append(eofKw >= 0 ? 1 : 0);
        return sb.toString();
    }

    static int lastXrefKeyword(String s) {
        // Find a `xref` token that begins a line and is not part of `startxref`.
        int idx = s.length();
        while (true) {
            idx = s.lastIndexOf("xref", idx - 1);
            if (idx < 0) {
                return -1;
            }
            // must start a line
            if (idx == 0 || s.charAt(idx - 1) == '\n' || s.charAt(idx - 1) == '\r') {
                // followed by EOL (the keyword line is just "xref")
                int after = idx + 4;
                if (after < s.length()
                        && (s.charAt(after) == '\n' || s.charAt(after) == '\r')) {
                    return idx;
                }
            }
        }
    }

    static boolean isSubsectionHeader(String line) {
        String[] p = line.trim().split("\\s+");
        if (p.length != 2) {
            return false;
        }
        return isDigits(p[0]) && isDigits(p[1]);
    }

    static boolean isEntryRow(String line) {
        String[] p = line.trim().split("\\s+");
        if (p.length != 3) {
            return false;
        }
        return isDigits(p[0]) && isDigits(p[1])
                && (p[2].equals("n") || p[2].equals("f"));
    }

    static boolean isDigits(String x) {
        if (x.isEmpty()) {
            return false;
        }
        for (int i = 0; i < x.length(); i++) {
            if (!Character.isDigit(x.charAt(i))) {
                return false;
            }
        }
        return true;
    }

    static int intValueOf(String dict, String key) {
        int k = dict.indexOf(key);
        if (k < 0) {
            return -1;
        }
        int i = k + key.length();
        while (i < dict.length() && !Character.isDigit(dict.charAt(i))
                && dict.charAt(i) != '-') {
            i++;
        }
        int j = i;
        if (j < dict.length() && dict.charAt(j) == '-') {
            j++;
        }
        while (j < dict.length() && Character.isDigit(dict.charAt(j))) {
            j++;
        }
        if (j == i) {
            return -1;
        }
        try {
            return Integer.parseInt(dict.substring(i, j));
        } catch (NumberFormatException e) {
            return -1;
        }
    }
}
