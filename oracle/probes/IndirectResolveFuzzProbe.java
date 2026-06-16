import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Differential fuzz probe for Apache PDFBox 3.0.7 INDIRECT-OBJECT / COSObject
 * lazy resolution — the on-demand dereferencing surface of
 * {@code COSParser.parseObjectDynamically} + {@code COSObject.getObject} +
 * the object-pool. Wave 1549, agent A.
 *
 * <p>Complements {@code CosLazyResolveProbe} (which pins object-pool dedup
 * IDENTITY and cycle closure on a single hand-built catalog) and
 * {@code CosObjectParseFuzzProbe} (which fuzzes the BODY parse of a single
 * object). This probe instead drives the CROSS-OBJECT resolution edges from a
 * corpus of ~30 whole PDFs, each isolating one resolution hazard:
 *
 * <ul>
 *   <li>a reference to a MISSING object number (no xref entry) → null;</li>
 *   <li>a reference with a WRONG generation number;</li>
 *   <li>a reference to a FREE / deleted object (xref {@code f} entry);</li>
 *   <li>a SELF-referential indirect object ({@code 5 0 obj << /Me 5 0 R >>});</li>
 *   <li>an object whose {@code X Y obj} header generation MISMATCHES the xref;</li>
 *   <li>a reference cycle A→B→A resolved via {@code getObject};</li>
 *   <li>an object-stream member referenced by an OUT-OF-RANGE / wrong index;</li>
 *   <li>a DANGLING reference inside an array / dict value.</li>
 * </ul>
 *
 * <h2>Input (file-driven manifest, same pattern as CosObjectParseFuzzProbe)</h2>
 * The pypdfbox sibling
 * ({@code tests/pdfparser/oracle/test_indirect_resolve_fuzz_wave1549.py})
 * writes each whole {@code <case>.pdf} into a tmp dir plus a {@code manifest.txt}
 * (one case name + one or more probe TARGET tokens per line). Both sides read
 * the identical bytes from disk.
 *
 * <h2>Manifest line grammar</h2>
 * <pre>
 *   &lt;case&gt; &lt;target&gt; [&lt;target&gt; ...]
 * </pre>
 * Each {@code target} is one of:
 * <pre>
 *   pool:N:G          resolve via COSDocument.getObjectFromPool(N,G).getObject()
 *   dictobj:N:G:/K    resolve catalog-of-N's /K via getDictionaryObject (null collapse)
 *   item:N:G:/K       raw catalog-of-N's /K via getItem (ref stays a placeholder)
 *   arr:N:G:/K:I      resolve element I of array N's /K via COSArray.getObject(I)
 * </pre>
 *
 * <h2>Output grammar (one UTF-8 LF-terminated line per target)</h2>
 * <pre>
 *   R &lt;case&gt; &lt;target&gt; &lt;projection&gt;
 * </pre>
 * where {@code projection} is one of:
 * <pre>
 *   null                          resolved to null / COSNull / absent
 *   bool(true|false) | int(d) | real(f32-bits-hex) | name(/x)
 *   str(hex) | ref(n,g) | array[..] | dict{..} | stream{..}
 *   isnull(true|false)            for a {@code pool:} target, COSObject.isObjectNull
 *   ERR:&lt;Exc&gt;                     resolving threw
 *   LOAD:&lt;Exc&gt;                     Loader.loadPDF threw (emitted once, target "*")
 * </pre>
 * For {@code pool:} targets the line carries BOTH the type tag AND the
 * isObjectNull flag, joined by a "+", so the test pins both the resolved value
 * and the dereference-state contract.
 */
public final class IndirectResolveFuzzProbe {

    static PrintStream out;

    static String exc(Throwable e) {
        return e.getClass().getSimpleName();
    }

    static String hex(byte[] data) {
        StringBuilder sb = new StringBuilder();
        for (byte b : data) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }

    /** Coarse, repr-independent type tag of a resolved COSBase. */
    static String tag(COSBase base) {
        if (base == null || base instanceof COSNull) {
            return "null";
        }
        if (base instanceof COSObject) {
            COSObject o = (COSObject) base;
            return "ref(" + o.getObjectNumber() + "," + o.getGenerationNumber() + ")";
        }
        if (base instanceof COSBoolean) {
            return "bool(" + (((COSBoolean) base).getValue() ? "true" : "false") + ")";
        }
        if (base instanceof COSInteger) {
            return "int(" + ((COSInteger) base).longValue() + ")";
        }
        if (base instanceof COSFloat) {
            return "real(" + Integer.toHexString(
                    Float.floatToIntBits(((COSFloat) base).floatValue())) + ")";
        }
        if (base instanceof COSName) {
            return "name(/" + ((COSName) base).getName() + ")";
        }
        if (base instanceof COSString) {
            return "str(" + hex(((COSString) base).getBytes()) + ")";
        }
        if (base instanceof COSStream) {
            return "stream";
        }
        if (base instanceof COSArray) {
            return "array[" + ((COSArray) base).size() + "]";
        }
        if (base instanceof COSDictionary) {
            return "dict[" + ((COSDictionary) base).size() + "]";
        }
        return "unknown(" + base.getClass().getSimpleName() + ")";
    }

    static String runTarget(PDDocument pd, String target) {
        COSDocument cos = pd.getDocument();
        String[] p = target.split(":");
        try {
            if (p[0].equals("pool")) {
                int n = Integer.parseInt(p[1]);
                int g = Integer.parseInt(p[2]);
                COSObject obj = cos.getObjectFromPool(new COSObjectKey(n, g));
                if (obj == null) {
                    return "null+isnull(true)";
                }
                COSBase resolved = obj.getObject();
                return tag(resolved) + "+isnull(" + obj.isObjectNull() + ")";
            }
            if (p[0].equals("dictobj")) {
                int n = Integer.parseInt(p[1]);
                int g = Integer.parseInt(p[2]);
                COSObject holder = cos.getObjectFromPool(new COSObjectKey(n, g));
                COSDictionary d = (COSDictionary) holder.getObject();
                return tag(d.getDictionaryObject(COSName.getPDFName(p[3].substring(1))));
            }
            if (p[0].equals("item")) {
                int n = Integer.parseInt(p[1]);
                int g = Integer.parseInt(p[2]);
                COSObject holder = cos.getObjectFromPool(new COSObjectKey(n, g));
                COSDictionary d = (COSDictionary) holder.getObject();
                return tag(d.getItem(COSName.getPDFName(p[3].substring(1))));
            }
            if (p[0].equals("arr")) {
                int n = Integer.parseInt(p[1]);
                int g = Integer.parseInt(p[2]);
                int idx = Integer.parseInt(p[4]);
                COSObject holder = cos.getObjectFromPool(new COSObjectKey(n, g));
                COSDictionary d = (COSDictionary) holder.getObject();
                COSArray a = (COSArray) d.getDictionaryObject(
                        COSName.getPDFName(p[3].substring(1)));
                if (idx < 0 || idx >= a.size()) {
                    return "OOR";
                }
                return tag(a.getObject(idx));
            }
        } catch (Throwable e) {
            return "ERR:" + exc(e);
        }
        return "BADTARGET";
    }

    static void runCase(File dir, String line) {
        String[] toks = line.trim().split("\\s+");
        String name = toks[0];
        File pdf = new File(dir, name + ".pdf");
        PDDocument pd = null;
        try {
            pd = Loader.loadPDF(pdf);
        } catch (Throwable e) {
            out.println("R " + name + " * LOAD:" + exc(e));
            return;
        }
        try {
            for (int i = 1; i < toks.length; i++) {
                out.println("R " + name + " " + toks[i] + " " + runTarget(pd, toks[i]));
            }
        } finally {
            try {
                pd.close();
            } catch (Exception ignored) {
                // best-effort close
            }
        }
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] lines =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        Arrays.stream(lines)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(line -> runCase(dir, line));
    }
}
